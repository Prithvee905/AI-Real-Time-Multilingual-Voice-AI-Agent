"""
Latency tracker for measuring and logging pipeline stage timings.
Ensures total latency stays under 450ms target.
"""
import time
from typing import Dict, Optional
from loguru import logger


class LatencyTracker:
    """Tracks latency across pipeline stages."""

    def __init__(self, request_id: str = ""):
        self.request_id = request_id
        self.stages: Dict[str, float] = {}
        self._start_times: Dict[str, float] = {}
        self.pipeline_start: Optional[float] = None
        self.pipeline_end: Optional[float] = None

    def start_pipeline(self):
        """Mark the start of the entire pipeline."""
        self.pipeline_start = time.perf_counter()

    def end_pipeline(self):
        """Mark the end of the entire pipeline."""
        self.pipeline_end = time.perf_counter()

    def start_stage(self, stage_name: str):
        """Start timing a specific stage."""
        self._start_times[stage_name] = time.perf_counter()

    def end_stage(self, stage_name: str) -> float:
        """End timing a stage and return duration in ms."""
        if stage_name not in self._start_times:
            return 0.0
        duration_ms = (time.perf_counter() - self._start_times[stage_name]) * 1000
        self.stages[stage_name] = duration_ms
        return duration_ms

    @property
    def total_latency_ms(self) -> float:
        """Total pipeline latency in milliseconds."""
        if self.pipeline_start and self.pipeline_end:
            return (self.pipeline_end - self.pipeline_start) * 1000
        return sum(self.stages.values())

    def get_report(self) -> Dict:
        """Generate a latency report."""
        total = self.total_latency_ms
        return {
            "request_id": self.request_id,
            "stages": {k: round(v, 2) for k, v in self.stages.items()},
            "total_ms": round(total, 2),
            "target_ms": 450,
            "within_target": total < 450,
        }

    def log_report(self):
        """Log the latency report."""
        report = self.get_report()
        status = "✅ WITHIN TARGET" if report["within_target"] else "⚠️ EXCEEDS TARGET"

        logger.info(f"───── Latency Report [{self.request_id}] ─────")
        for stage, duration in report["stages"].items():
            logger.info(f"  {stage:.<30} {duration:>8.2f} ms")
        logger.info(f"  {'TOTAL':.<30} {report['total_ms']:>8.2f} ms  {status}")
        logger.info(f"─────────────────────────────────────────────")
