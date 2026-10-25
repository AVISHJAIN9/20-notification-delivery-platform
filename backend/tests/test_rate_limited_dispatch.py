import pytest
import time
from queues.dispatcher import TokenBucketRateLimiter

def test_NTF_062_rate_limited_dispatch():
    """
    NTF-062: Rate-limited dispatch.
    Tests token-bucket rate limiter enforcing RPS limits.
    """
    limiter = TokenBucketRateLimiter()

    # Rate: 5 RPS with burst capacity 5
    key = "tenant-sms-limit"

    # First 5 calls are permitted (burst)
    allowed_count = 0
    for _ in range(5):
        if limiter.allow(key, rate_rps=5.0, capacity=5.0):
            allowed_count += 1
    assert allowed_count == 5

    # 6th immediate call without waiting must be denied
    assert limiter.allow(key, rate_rps=5.0, capacity=5.0) is False
