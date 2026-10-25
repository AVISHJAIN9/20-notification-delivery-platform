import pytest
from core.engine import NotificationCoreEngine, NotificationPriority

def test_NTF_021_priority_handling():
    """
    NTF-021: Priority handling.
    Validates priority weighting hierarchy (URGENT > HIGH > NORMAL > LOW).
    """
    w_urgent = NotificationCoreEngine.get_priority_weight(NotificationPriority.URGENT.value)
    w_high = NotificationCoreEngine.get_priority_weight(NotificationPriority.HIGH.value)
    w_normal = NotificationCoreEngine.get_priority_weight(NotificationPriority.NORMAL.value)
    w_low = NotificationCoreEngine.get_priority_weight(NotificationPriority.LOW.value)

    assert w_urgent == 100
    assert w_high == 50
    assert w_normal == 10
    assert w_low == 0

    assert w_urgent > w_high > w_normal > w_low
