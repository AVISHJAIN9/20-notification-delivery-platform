import pytest
from retries.failure import FailureClassifier, ErrorCategory

def test_NTF_073_failure_classification():
    """
    NTF-073: Failure classification.
    Validates classification into TRANSIENT (retryable) vs PERMANENT (non-retryable).
    """
    # 1. Transient / Retryable errors
    assert FailureClassifier.classify("RATE_LIMITED") == ErrorCategory.TRANSIENT
    assert FailureClassifier.classify("TIMEOUT") == ErrorCategory.TRANSIENT
    assert FailureClassifier.classify(503) == ErrorCategory.TRANSIENT
    assert FailureClassifier.classify(429) == ErrorCategory.TRANSIENT
    assert FailureClassifier.is_retryable("RATE_LIMITED") is True
    assert FailureClassifier.is_retryable(503) is True

    # 2. Permanent / Non-retryable errors
    assert FailureClassifier.classify("INVALID_RECIPIENT") == ErrorCategory.PERMANENT
    assert FailureClassifier.classify("UNAUTHORIZED") == ErrorCategory.PERMANENT
    assert FailureClassifier.classify(400) == ErrorCategory.PERMANENT
    assert FailureClassifier.classify(404) == ErrorCategory.PERMANENT
    assert FailureClassifier.is_retryable("INVALID_RECIPIENT") is False
    assert FailureClassifier.is_retryable(404) is False
