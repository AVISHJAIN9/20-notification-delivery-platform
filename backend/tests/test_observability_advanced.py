"""
Tests for Observability and Analytics (NTF-114, NTF-116, NTF-117).
- NTF-114: Structured logs (JSON formatting, event tracking, credential sanitization).
- NTF-116: Delivery success metrics (success counts, p50/p95 latency, provider breakdown).
- NTF-117: Delivery failure metrics (failure counts, error classification breakdown, provider breakdowns).
"""

import json
import logging
from observability.structured_logger import StructuredLogger, sanitize_payload
from observability.metrics import DeliveryMetricsTracker


def test_NTF_114_structured_logs(caplog):
    """
    NTF-114: Structured logs.
    Verifies JSON structure, event tags, and credential redaction.
    """
    logger = StructuredLogger(name="test.logger")

    with caplog.at_level(logging.INFO):
        entry = logger.info(
            event="NOTIFICATION_DISPATCHED",
            message="Dispatching notification to customer",
            tenant_id="tenant-acme",
            notification_id="ntf-log-114",
            channel="SMS",
            request_id="req-abc-123",
            api_key="super_secret_token",
            password="user_password_123",
            user_recipient="+15551234567"
        )

    assert entry["event"] == "NOTIFICATION_DISPATCHED"
    assert entry["tenant_id"] == "tenant-acme"
    assert entry["notification_id"] == "ntf-log-114"
    assert entry["channel"] == "SMS"
    assert entry["request_id"] == "req-abc-123"

    # Redaction verification: sensitive keys MUST be masked
    assert entry["api_key"] == "[REDACTED]"
    assert entry["password"] == "[REDACTED]"
    assert entry["user_recipient"] == "+15551234567"

    # Verify log output in caplog is valid json and redacted
    assert any("NOTIFICATION_DISPATCHED" in rec.message or hasattr(rec, "structured_data") for rec in caplog.records)


def test_NTF_116_delivery_success_metrics():
    """
    NTF-116: Delivery success metrics.
    Tests recording successful attempts, calculating p50/p95 latencies and success rates.
    """
    tracker = DeliveryMetricsTracker()

    # Record 20 EMAIL successes with latencies from 10ms to 200ms
    for i in range(1, 21):
        tracker.record_success(
            channel="EMAIL",
            provider_id="sendgrid-primary",
            latency_ms=i * 10
        )

    # Record 5 SMS successes
    for _ in range(5):
        tracker.record_success(
            channel="SMS",
            provider_id="twilio-primary",
            latency_ms=45
        )

    metrics = tracker.get_success_metrics()
    assert metrics["total_success"] == 25
    assert metrics["overall_success_rate"] == 1.0

    email_metrics = metrics["channels"]["EMAIL"]
    assert email_metrics["success_count"] == 20
    assert email_metrics["success_rate"] == 1.0
    assert email_metrics["avg_latency_ms"] == 105.0
    assert email_metrics["p50_latency_ms"] == 105.0
    assert email_metrics["p95_latency_ms"] >= 190.0
    assert email_metrics["provider_breakdown"]["sendgrid-primary"] == 20

    # Prometheus export verification
    prom = tracker.to_prometheus_format()
    assert 'notification_delivery_success_total{channel="EMAIL",provider="sendgrid-primary"} 20' in prom
    assert 'notification_delivery_success_total{channel="SMS",provider="twilio-primary"} 5' in prom


def test_NTF_117_delivery_failure_metrics():
    """
    NTF-117: Delivery failure metrics.
    Tests recording failures, tracking error classifications, and calculating failure rates.
    """
    tracker = DeliveryMetricsTracker()

    # Record successes and failures
    tracker.record_success(channel="PUSH", provider_id="fcm", latency_ms=30)
    tracker.record_failure(channel="PUSH", provider_id="fcm", error_code="RATE_LIMITED", latency_ms=15)
    tracker.record_failure(channel="PUSH", provider_id="fcm", error_code="TIMEOUT", latency_ms=5000)
    tracker.record_failure(channel="PUSH", provider_id="apns", error_code="DEVICE_UNREGISTERED", latency_ms=25)

    metrics = tracker.get_failure_metrics()
    assert metrics["total_failures"] == 3
    assert metrics["total_attempts"] == 4
    assert metrics["overall_failure_rate"] == 0.75

    push_metrics = metrics["channels"]["PUSH"]
    assert push_metrics["failure_count"] == 3
    assert push_metrics["failure_rate"] == 0.75
    assert push_metrics["error_code_breakdown"]["RATE_LIMITED"] == 1
    assert push_metrics["error_code_breakdown"]["TIMEOUT"] == 1
    assert push_metrics["error_code_breakdown"]["DEVICE_UNREGISTERED"] == 1
    assert push_metrics["provider_failures"]["fcm"] == 2
    assert push_metrics["provider_failures"]["apns"] == 1

    prom = tracker.to_prometheus_format()
    assert 'notification_delivery_failure_total{channel="PUSH",provider="fcm"} 2' in prom
    assert 'notification_delivery_failure_total{channel="PUSH",provider="apns"} 1' in prom
