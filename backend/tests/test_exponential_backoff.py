import pytest
from retries.failure import RetryPolicy

def test_NTF_070_exponential_backoff_retry():
    """
    NTF-070: Exponential backoff retry.
    Validates exponential progression: base * factor^(attempt - 1) capped at max_delay.
    """
    policy = RetryPolicy(
        max_retries=4,
        base_delay_seconds=2.0,
        max_delay_seconds=30.0,
        factor=2.0
    )

    # Attempt 1: 2 * 2^0 = 2.0s
    assert policy.calculate_backoff(attempt=1) == 2.0

    # Attempt 2: 2 * 2^1 = 4.0s
    assert policy.calculate_backoff(attempt=2) == 4.0

    # Attempt 3: 2 * 2^2 = 8.0s
    assert policy.calculate_backoff(attempt=3) == 8.0

    # Attempt 4: 2 * 2^3 = 16.0s
    assert policy.calculate_backoff(attempt=4) == 16.0

    # Attempt 5: 2 * 2^4 = 32.0s -> capped at max_delay 30.0s
    assert policy.calculate_backoff(attempt=5) == 30.0

    # Retries cap check
    assert policy.should_retry(attempt=1, error_code="TIMEOUT") is True
    assert policy.should_retry(attempt=3, error_code="TIMEOUT") is True
    assert policy.should_retry(attempt=4, error_code="TIMEOUT") is False  # max_retries reached
