from backyardchirps.features.recording.audio.queue_monitor import QueueMonitor


def test_fresh_monitor_reports_an_idle_empty_queue() -> None:
    heartbeat = QueueMonitor(budget_ms=1500).to_heartbeat()

    assert heartbeat.queue_depth == 0
    assert heartbeat.queue_depth_peak == 0
    assert heartbeat.analysis_ms_avg == 0
    assert heartbeat.budget_ms == 1500


def test_heartbeat_reports_the_latest_depth_and_windowed_peak() -> None:
    monitor = QueueMonitor(budget_ms=1500)

    monitor.record(queue_depth=2, analysis_ms=1000)
    monitor.record(queue_depth=7, analysis_ms=1000)
    monitor.record(queue_depth=3, analysis_ms=1000)

    heartbeat = monitor.to_heartbeat()
    assert heartbeat.queue_depth == 3
    assert heartbeat.queue_depth_peak == 7


def test_analysis_average_is_rounded_over_recorded_clips() -> None:
    monitor = QueueMonitor(budget_ms=1500)

    monitor.record(queue_depth=0, analysis_ms=1000)
    monitor.record(queue_depth=0, analysis_ms=1003)

    assert monitor.to_heartbeat().analysis_ms_avg == 1002  # 1001.5 rounded


def test_window_only_keeps_the_most_recent_clips() -> None:
    monitor = QueueMonitor(budget_ms=1500, window=2)

    monitor.record(queue_depth=9, analysis_ms=5000)  # evicted once the window fills
    monitor.record(queue_depth=1, analysis_ms=1000)
    monitor.record(queue_depth=2, analysis_ms=1000)

    heartbeat = monitor.to_heartbeat()
    assert heartbeat.queue_depth_peak == 2
    assert heartbeat.analysis_ms_avg == 1000
