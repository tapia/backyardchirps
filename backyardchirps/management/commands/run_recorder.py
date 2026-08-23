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
from backyardchirps.features.recording.audio.consistency_filter import ConsistencyFilter
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import discard_non_birds
from backyardchirps.features.recording.audio.queue_monitor import QueueMonitor
from backyardchirps.features.recording.audio.recorder import AudioRecorder
from backyardchirps.features.recording.logic import discard_blacklisted
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
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

        recorder = AudioRecorder(
            sample_rate=settings.RECORDING["sample_rate"],
            clip_duration=settings.RECORDING["clip_duration"],
            step_duration=settings.RECORDING["step_duration"],
            device=Settings.get(SettingsKey.AUDIO_DEVICE),
        )
        analyzer = BirdNet3Analyzer(
            latitude=Settings.get(SettingsKey.LOCATION_LAT) or 0.0,
            longitude=Settings.get(SettingsKey.LOCATION_LON) or 0.0,
            min_confidence=Settings.get(SettingsKey.ANALYSIS_LOW_CONFIDENCE),
        )
        consistency_filter = ConsistencyFilter(
            window_size=settings.CONSISTENCY_FILTER["window_size"],
            min_detections=settings.CONSISTENCY_FILTER["min_detections"],
            bypass_confidence=settings.CONSISTENCY_FILTER["bypass_confidence"],
            overlap_time=settings.RECORDING["clip_duration"] - settings.RECORDING["step_duration"],
        )
        notifier = Notifier()
        queue_monitor = QueueMonitor(budget_ms=round(settings.RECORDING["step_duration"] * 1000))

        self._log_initialization_messages()

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
                # process for. The clip is lost, the consistency window survives, and the
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
                    confirmed_results = consistency_filter.add(
                        clip, analysis_results, analysis.raw_candidates, analysis_time_ms
                    )
                    logger.info(
                        f"Clip processed in {analysis_time_ms}ms. {len(analysis_results)} BirdNET result(s), "
                        f"{len(confirmed_results)} confirmed"
                    )

                    for confirmed in confirmed_results:
                        # None when a record for this block already exists and is at least
                        # as confident, so there is nothing to update and nothing to say.
                        detection = detection_queries.upsert(
                            confirmed.clip,
                            confirmed.result,
                            analysis_time_ms=confirmed.analysis_time_ms,
                            raw_candidates=confirmed.raw_candidates,
                        )
                        if detection:
                            notifier.maybe_notify(detection, confirmed.clip)
                        self._log(confirmed.result, detection)
                except Exception:
                    logger.exception("Could not process the clip recorded at %s", clip.recorded_at)

    def _log_initialization_messages(self) -> None:
        overlap_pct = (1 - settings.RECORDING["step_duration"] / settings.RECORDING["clip_duration"]) * 100

        logger.info(
            "Recording started. lat=%s, lon=%s",
            Settings.get(SettingsKey.LOCATION_LAT),
            Settings.get(SettingsKey.LOCATION_LON),
        )
        logger.info(f"Min confidence: {Settings.get(SettingsKey.ANALYSIS_LOW_CONFIDENCE)}")
        logger.info(f"Detection time buffer: {settings.RECORDING['detection_time_buffer_in_minutes']} min")
        logger.info(
            f"Sliding window: clip={settings.RECORDING['clip_duration']:.1f}s, "
            f"step={settings.RECORDING['step_duration']:.1f}s ({overlap_pct:.0f}% overlap)"
        )
        logger.info(
            f"Consistency filter: window={settings.CONSISTENCY_FILTER['window_size']} clips, "
            f"min_detections={settings.CONSISTENCY_FILTER['min_detections']}, "
            f"bypass_confidence={settings.CONSISTENCY_FILTER['bypass_confidence']}"
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
