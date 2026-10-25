"""
Delivery Metrics Collection and Analytics (NTF-116, NTF-117).
- NTF-116: Delivery success metrics (counts, latency distributions, success rates per channel & provider).
- NTF-117: Delivery failure metrics (failure counts, error classification breakdown, failure rates).
"""

from typing import Dict, Any, Optional, List
import statistics
from collections import defaultdict


class DeliveryMetricsTracker:
    def __init__(self):
        # channel -> list of latency ms for successful sends
        self._success_latencies: Dict[str, List[int]] = defaultdict(list)
        # channel -> provider -> count
        self._provider_successes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # channel -> provider -> count
        self._provider_failures: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # channel -> error_code -> count
        self._failure_causes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_success(
        self,
        channel: str,
        provider_id: str,
        latency_ms: int = 0
    ) -> None:
        """
        Records a successful delivery attempt (NTF-116).
        """
        ch = channel.upper()
        self._success_latencies[ch].append(max(0, latency_ms))
        self._provider_successes[ch][provider_id] += 1

    def record_failure(
        self,
        channel: str,
        provider_id: str,
        error_code: str,
        latency_ms: int = 0
    ) -> None:
        """
        Records a failed delivery attempt (NTF-117).
        """
        ch = channel.upper()
        self._provider_failures[ch][provider_id] += 1
        self._failure_causes[ch][error_code.upper()] += 1

    def get_success_metrics(self, channel: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates delivery success metrics (NTF-116).
        """
        channels = [channel.upper()] if channel else list(self._provider_successes.keys())
        total_success = 0
        total_attempts = 0
        all_latencies = []

        by_channel = {}
        for ch in channels:
            succ = sum(self._provider_successes[ch].values())
            fail = sum(self._provider_failures[ch].values())
            attempts = succ + fail
            lats = self._success_latencies[ch]
            all_latencies.extend(lats)
            total_success += succ
            total_attempts += attempts

            p50 = statistics.median(lats) if lats else 0.0
            p95 = statistics.quantiles(lats, n=20)[18] if len(lats) >= 20 else (max(lats) if lats else 0.0)

            by_channel[ch] = {
                "success_count": succ,
                "total_attempts": attempts,
                "success_rate": round(succ / attempts, 4) if attempts > 0 else 1.0,
                "avg_latency_ms": round(statistics.mean(lats), 2) if lats else 0.0,
                "p50_latency_ms": p50,
                "p95_latency_ms": p95,
                "provider_breakdown": dict(self._provider_successes[ch])
            }

        overall_p50 = statistics.median(all_latencies) if all_latencies else 0.0
        overall_p95 = statistics.quantiles(all_latencies, n=20)[18] if len(all_latencies) >= 20 else (max(all_latencies) if all_latencies else 0.0)

        return {
            "total_success": total_success,
            "total_attempts": total_attempts,
            "overall_success_rate": round(total_success / total_attempts, 4) if total_attempts > 0 else 1.0,
            "overall_p50_latency_ms": overall_p50,
            "overall_p95_latency_ms": overall_p95,
            "channels": by_channel
        }

    def get_failure_metrics(self, channel: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates delivery failure metrics (NTF-117).
        """
        channels = [channel.upper()] if channel else list(self._provider_failures.keys())
        total_failures = 0
        total_attempts = 0

        by_channel = {}
        for ch in channels:
            fail = sum(self._provider_failures[ch].values())
            succ = sum(self._provider_successes[ch].values())
            attempts = succ + fail
            total_failures += fail
            total_attempts += attempts

            by_channel[ch] = {
                "failure_count": fail,
                "total_attempts": attempts,
                "failure_rate": round(fail / attempts, 4) if attempts > 0 else 0.0,
                "error_code_breakdown": dict(self._failure_causes[ch]),
                "provider_failures": dict(self._provider_failures[ch])
            }

        return {
            "total_failures": total_failures,
            "total_attempts": total_attempts,
            "overall_failure_rate": round(total_failures / total_attempts, 4) if total_attempts > 0 else 0.0,
            "channels": by_channel
        }

    def to_prometheus_format(self) -> str:
        lines = [
            "# HELP notification_delivery_success_total Number of successful delivery attempts",
            "# TYPE notification_delivery_success_total counter"
        ]
        for ch, provs in self._provider_successes.items():
            for prov, cnt in provs.items():
                lines.append(f'notification_delivery_success_total{{channel="{ch}",provider="{prov}"}} {cnt}')

        lines.extend([
            "# HELP notification_delivery_failure_total Number of failed delivery attempts",
            "# TYPE notification_delivery_failure_total counter"
        ])
        for ch, provs in self._provider_failures.items():
            for prov, cnt in provs.items():
                lines.append(f'notification_delivery_failure_total{{channel="{ch}",provider="{prov}"}} {cnt}')

        return "\n".join(lines) + "\n"
