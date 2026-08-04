from collections import deque
from datetime import datetime
from datetime import timezone

from backyardchirps.shared.recorder_heartbeat import RecorderHeartbeat


class QueueMonitor:
    """
    Follows the recorder's clip backlog and turns it into a heartbeat snapshot.

    Both the average analysis time and the peak depth cover only the last `window`
    clips, so the snapshot says how the recorder is coping right now and not how it
    coped with a spike minutes ago.
    """

    def __init__(self, budget_ms: int, window: int = 40) -> None:
        self._budget_ms = budget_ms
        self._recent_analysis_ms: deque[int] = deque(maxlen=window)
        self._recent_queue_depth: deque[int] = deque(maxlen=window)

    def record(self, queue_depth: int, analysis_ms: int) -> None:
        """
        Add one processed clip: the queue depth seen after analyzing it, and how long
        that analysis took.
        """
        self._recent_queue_depth.append(queue_depth)
        self._recent_analysis_ms.append(analysis_ms)

    def to_heartbeat(self) -> RecorderHeartbeat:
        """
        Build a heartbeat from the current window. Before any clip arrives it reports an
        idle, empty queue.
        """
        current_depth = self._recent_queue_depth[-1] if self._recent_queue_depth else 0
        peak_depth = max(self._recent_queue_depth) if self._recent_queue_depth else 0
        average_ms = (
            round(sum(self._recent_analysis_ms) / len(self._recent_analysis_ms)) if self._recent_analysis_ms else 0
        )
        return RecorderHeartbeat(
            recorded_at=datetime.now(timezone.utc),
            queue_depth=current_depth,
            queue_depth_peak=peak_depth,
            analysis_ms_avg=average_ms,
            budget_ms=self._budget_ms,
        )
