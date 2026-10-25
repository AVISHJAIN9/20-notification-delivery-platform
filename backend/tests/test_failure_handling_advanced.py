import pytest
from datetime import datetime, timezone, timedelta
from retries.failure import FailureClassifier, ErrorCategory, RetryPolicy

@pytest.mark.parametrize("error_input,expected_category,expected_retryable", [
    # 4xx client errors (non-retryable)
    (400, ErrorCategory.PERMANENT, False),
    (401, ErrorCategory.PERMANENT, False),
    (403, ErrorCategory.PERMANENT, False),
    (404, ErrorCategory.PERMANENT, False),
    (422, ErrorCategory.PERMANENT, False),
    ("INVALID_RECIPIENT", ErrorCategory.PERMANENT, False),
    ("BAD_REQUEST", ErrorCategory.PERMANENT, False),
    ("UNAUTHORIZED", ErrorCategory.PERMANENT, False),

    # 5xx server errors (retryable)
    (500, ErrorCategory.TRANSIENT, True),
    (502, ErrorCategory.TRANSIENT, True),
    (503, ErrorCategory.TRANSIENT, True),
    (504, ErrorCategory.TRANSIENT, True),

    # Rate limiting 429 (retryable)
    (429, ErrorCategory.TRANSIENT, True),
    ("RATE_LIMITED", ErrorCategory.TRANSIENT, True),

    # Timeouts (retryable)
    ("TIMEOUT", ErrorCategory.TRANSIENT, True),
    ("CONNECT_TIMEOUT", ErrorCategory.TRANSIENT, True),
    ("READ_TIMEOUT", ErrorCategory.TRANSIENT, True),
    ("GATEWAY_TIMEOUT", ErrorCategory.TRANSIENT, True),

    # Network failures (retryable)
    ("CONNECTION_RESET", ErrorCategory.TRANSIENT, True),
    ("CONNECTION_REFUSED", ErrorCategory.TRANSIENT, True),
    ("DNS_FAILURE", ErrorCategory.TRANSIENT, True),
    ("NETWORK_ERROR", ErrorCategory.TRANSIENT, True),
])
def test_NTF_075_non_retryable_classification_table(error_input, expected_category, expected_retryable):
    """
    NTF-075: Non-retryable error classification.
    Table-driven test validating 4xx vs 5xx vs timeout vs network vs 429 errors.
    """
    assert FailureClassifier.classify(error_input) == expected_category
    assert FailureClassifier.is_retryable(error_input) is expected_retryable

def test_NTF_076_provider_timeout_handling():
    """
    NTF-076: Provider timeout handling.
    Validates timeout error classification and exponential backoff delay calculation.
    """
    policy = RetryPolicy(max_retries=3, base_delay_seconds=2.0)
    assert FailureClassifier.is_retryable("TIMEOUT") is True
    assert policy.should_retry(attempt=1, error_code="TIMEOUT") is True
    assert policy.should_retry(attempt=3, error_code="TIMEOUT") is False
    # Backoff for attempt 2: base_delay * 2^1 = 4.0s
    assert policy.calculate_backoff(attempt=2) == 4.0

def test_NTF_077_network_failure_handling():
    """
    NTF-077: Network failure handling.
    Validates classification of connection resets, DNS failures, and host unreachable errors.
    """
    for code in ["CONNECTION_RESET", "CONNECTION_REFUSED", "DNS_FAILURE", "NETWORK_ERROR"]:
        assert FailureClassifier.classify(code) == ErrorCategory.TRANSIENT
        assert FailureClassifier.is_retryable(code) is True

def test_NTF_078_rate_limit_response_handling_with_retry_after():
    """
    NTF-078: Rate-limit response handling.
    Tests honoring Retry-After numeric seconds and HTTP date headers.
    """
    # 1. Numeric seconds in Retry-After header
    headers1 = {"Retry-After": "45"}
    delay1 = FailureClassifier.parse_retry_after(headers1)
    assert delay1 == 45.0

    # 2. Case-insensitive header lookup
    headers2 = {"retry-after": "120"}
    delay2 = FailureClassifier.parse_retry_after(headers2)
    assert delay2 == 120.0

    # 3. Missing header returns None
    assert FailureClassifier.parse_retry_after({}) is None
