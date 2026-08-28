import logging
import queue
import signal
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.notifications.logic import Notifier
from backyardchirps.features.recording.audio.birdnet3.analyzer import BirdNet3Analyzer
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import discard_non_birds
from backyardchirps.features.recording.audio.detection_window import DetectionWindow
from backyardchirps.features.recording.audio.queue_monitor import QueueMonitor
from backyardchirps.features.recording.audio.recorder import AudioRecorder
from backyardchirps.features.recording.entity import RecorderStartupSettings
from backyardchirps.features.recording.logic import discard_blacklisted
from backyardchirps.features.recording.logic import recorder_startup_settings
from backyardchirps.shared.recorder_heartbeat import write_heartbeat

logger = logging.getLogger(__name__)

# Shortest gap between heartbeat writes. Only the write to disk is slowed down, to spare
# the Pi's SD card. The queue figures themselves are still updated on every clip, and the
# server-status page does not read them any faster than this anyway.
_HEARTBEAT_WRITE_INTERVAL_SECONDS = 3.0


class Command(BaseCommand):
    help = "Start continuous bird audio recording and species identification"
    running: bool = True

    def handle(self, *args: Any, **options: Any) -> None:
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        startup_settings = recorder_startup_settings()
        recorder = AudioRecorder(
            sample_rate=settings.RECORDING["sample_rate"],
            clip_duration=settings.RECORDING["clip_duration"],
            step_duration=settings.RECORDING["step_duration"],
            device=startup_settings.audio_device,
        )
        analyzer = BirdNet3Analyzer(
            latitude=startup_settings.latitude,
            longitude=startup_settings.longitude,
            min_confidence=startup_settings.min_confidence,
        )
        detection_window = DetectionWindow(
            window_size=settings.DETECTION_WINDOW["window_size"],
            min_clips_to_merge=settings.DETECTION_WINDOW["min_clips_to_merge"],
            overlap_time=settings.RECORDING["clip_duration"] - settings.RECORDING["step_duration"],
        )
        notifier = Notifier()
        queue_monitor = QueueMonitor(budget_ms=round(settings.RECORDING["step_duration"] * 1000))

        self._log_initialization_messages(startup_settings)

        self.running = True
        with recorder:
            # Write one heartbeat straight away, so the queue card says "running" while
            # the first clips are still being recorded and analyzed.
            write_heartbeat(queue_monitor.to_heartbeat())
            last_heartbeat_at = time.monotonic()

            while self.running:
                try:
                    clip = recorder.next_clip(timeout=1.0)
                except queue.Empty:
                    continue

                # A microphone that comes and goes, a model that chokes on one clip, a
                # database locked by the web process: none of those are worth ending the
                # process for. The clip is lost, the detection window survives, and the
                # next clip is already being recorded.
                try:
                    notifier.flush(detection_queries.get_block_time(clip.recorded_at))

                    started_at = time.perf_counter()
                    analysis = analyzer.analyze(clip)
                    analysis_time_ms = round((time.perf_counter() - started_at) * 1000)

                    queue_monitor.record(recorder.pending_clips(), analysis_time_ms)
                    if time.monotonic() - last_heartbeat_at >= _HEARTBEAT_WRITE_INTERVAL_SECONDS:
                        write_heartbeat(queue_monitor.to_heartbeat())
                        last_heartbeat_at = time.monotonic()

                    analysis_results = discard_non_birds(discard_blacklisted(analysis.results))
                    recorded_detections = detection_window.add(
                        clip, analysis_results, analysis.raw_candidates, analysis_time_ms
                    )
                    logger.info(f"Clip processed in {analysis_time_ms}ms. {len(analysis_results)} BirdNET result(s)")

                    for recorded in recorded_detections:
                        # None when a record for this block already exists and is at least
                        # as confident, so there is nothing to update and nothing to say.
                        detection = detection_queries.upsert(
                            recorded.clip,
                            recorded.result,
                            analysis_time_ms=recorded.analysis_time_ms,
                            raw_candidates=recorded.raw_candidates,
                        )
                        if detection:
                            notifier.maybe_notify(detection, recorded.clip)
                        self._log(recorded.result, detection)

                    if self._settings_have_moved_on(startup_settings):
                        self.running = False
                except Exception:
                    logger.exception("Could not process the clip recorded at %s", clip.recorded_at)

    def _settings_have_moved_on(self, startup_settings: RecorderStartupSettings) -> bool:
        """
        Whether this process is still the recorder the settings describe.

        The microphone and the analyzer are built once and never look again, so a change
        to any of the values behind them can only be picked up by starting over. Stopping
        is how that happens: the unit is Restart=always, so systemd brings the recorder
        straight back with the new values. Started by hand, it stays stopped, and the log
        line says why.
        """
        if recorder_startup_settings() == startup_settings:
            return False
        logger.info("A setting the recorder reads at startup has changed. Stopping so it starts again with it.")
        return True

    def _log_initialization_messages(self, startup_settings: RecorderStartupSettings) -> None:
        overlap_pct = (1 - settings.RECORDING["step_duration"] / settings.RECORDING["clip_duration"]) * 100

        logger.info(
            "Recording started. lat=%s, lon=%s",
            startup_settings.latitude,
            startup_settings.longitude,
        )
        logger.info(f"Min confidence: {startup_settings.min_confidence}")
        logger.info(f"Detection time buffer: {settings.RECORDING['detection_time_buffer_in_minutes']} min")
        logger.info(
            f"Sliding window: clip={settings.RECORDING['clip_duration']:.1f}s, "
            f"step={settings.RECORDING['step_duration']:.1f}s ({overlap_pct:.0f}% overlap)"
        )
        logger.info(
            f"Detection window: {settings.DETECTION_WINDOW['window_size']} clips, "
            f"merged from {settings.DETECTION_WINDOW['min_clips_to_merge']}"
        )

    def _log(
        self,
        analysis_result: AnalysisResult,
        detection: Detection | None,
    ) -> None:
        common_name = analysis_result.species.common_name(settings.LANGUAGE_CODE)
        confidence = analysis_result.confidence * 100
        if detection is None:
            suffix = "  [ignored. Species already detected recently]"
        elif detection.clip_path:
            suffix = "  [clip saved]"
        else:
            suffix = ""
        logger.info(
            f"[NEW DETECTION] {common_name} ({analysis_result.species.scientific_name}): {confidence:.0f}%{suffix}"
        )

    def _shutdown(self, sig: int, frame: object) -> None:
        logger.info("Shutting down...")
        self.running = False
