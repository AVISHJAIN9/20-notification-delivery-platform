import pytest
from core.engine import NotificationCoreEngine

def test_NTF_018_notification_id_generation():
    """
    NTF-018: Notification ID generation.
    Tests generation of collision-resistant prefixed notification IDs.
    """
    ids = set()
    for _ in range(500):
        nid = NotificationCoreEngine.generate_notification_id()
        assert nid.startswith("ntf_")
        assert len(nid) >= 20
        ids.add(nid)

    # All 500 must be unique
    assert len(ids) == 500
