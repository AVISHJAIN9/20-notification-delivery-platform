import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager, NotificationStatus
from retries.failure import DeadLetterQueueManager

@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_NTF_081_dead_letter_processing_with_audit(async_session):
    """
    NTF-081: Dead-letter processing.
    Tests reprocessing DLQ items: creates new attempt, writes audit entry, transitions to QUEUED.
    """
    store = NotificationStoreManager(async_session)
    dlq_mgr = DeadLetterQueueManager(async_session)

    # 1. Create a failed notification and send to DLQ
    notif = await store.create_notification(
        notification_id="ntf-dlq-001",
        tenant_id="tenant-ops",
        user_id="user-1",
        channel="EMAIL",
        body="DLQ Test Message",
        idempotency_key="dlq-idem-1"
    )
    # Transition to FAILED
    notif_rec = await store.get_notification("ntf-dlq-001")
    from sqlalchemy import update
    from models.store import NotificationRecord
    await async_session.execute(
        update(NotificationRecord)
        .where(NotificationRecord.id == "ntf-dlq-001")
        .values(status=NotificationStatus.FAILED.value)
    )
    await async_session.commit()

    dlq_entry = await dlq_mgr.send_to_dlq(
        notification_id="ntf-dlq-001",
        tenant_id="tenant-ops",
        failure_reason="500 Internal Error from upstream",
        attempt_count=3
    )
    assert dlq_entry.id == "dlq_ntf-dlq-001"

    # 2. Reprocess dead letter
    reprocessed = await dlq_mgr.reprocess_dead_letter(
        tenant_id="tenant-ops",
        dlq_id=dlq_entry.id,
        actor="ops-admin@example.com"
    )
    assert reprocessed.status == NotificationStatus.QUEUED.value

    # 3. Verify DLQ record removed
    remaining = await dlq_mgr.list_dlq("tenant-ops")
    assert len(remaining) == 0

    # 4. Verify new attempt record created
    attempts = await store.get_delivery_attempts("ntf-dlq-001")
    assert len(attempts) >= 1
    assert any("REPROCESS" in a.id for a in attempts)

    # 5. Verify audit log entry exists
    audit_logs = await store.get_audit_logs(tenant_id="tenant-ops", resource_type="dead_letter")
    assert len(audit_logs) >= 1
    assert audit_logs[0].action == "DLQ_REPROCESSED"

@pytest.mark.asyncio
async def test_NTF_082_manual_retry_and_delivered_protection(async_session):
    """
    NTF-082: Manual retry.
    Tests initiating manual retry, creating new attempt, writing audit log, and blocking retry on DELIVERED.
    """
    store = NotificationStoreManager(async_session)
    dlq_mgr = DeadLetterQueueManager(async_session)

    # 1. Create failed notification
    notif = await store.create_notification(
        notification_id="ntf-retry-001",
        tenant_id="tenant-retry",
        user_id="user-2",
        channel="SMS",
        body="Retry SMS",
        idempotency_key="retry-idem-1"
    )
    from sqlalchemy import update
    from models.store import NotificationRecord
    await async_session.execute(
        update(NotificationRecord)
        .where(NotificationRecord.id == "ntf-retry-001")
        .values(status=NotificationStatus.FAILED.value)
    )
    await async_session.commit()

    # 2. Trigger manual retry
    retried = await dlq_mgr.manual_retry(
        tenant_id="tenant-retry",
        notification_id="ntf-retry-001",
        actor="engineer@example.com"
    )
    assert retried.status == NotificationStatus.QUEUED.value

    # Check new attempt and audit entry
    attempts = await store.get_delivery_attempts("ntf-retry-001")
    assert len(attempts) >= 1
    assert any("MANUAL_RETRY" in a.id for a in attempts)

    audit_logs = await store.get_audit_logs(tenant_id="tenant-retry", resource_type="notification")
    assert len(audit_logs) >= 1
    assert any(a.action == "MANUAL_RETRY" for a in audit_logs)

    # 3. Invariant: Cannot retry a DELIVERED notification
    await async_session.execute(
        update(NotificationRecord)
        .where(NotificationRecord.id == "ntf-retry-001")
        .values(status=NotificationStatus.DELIVERED.value)
    )
    await async_session.commit()

    with pytest.raises(ValueError, match="Cannot retry already DELIVERED"):
        await dlq_mgr.manual_retry(
            tenant_id="tenant-retry",
            notification_id="ntf-retry-001",
            actor="engineer@example.com"
        )

@pytest.mark.asyncio
async def test_NTF_083_replay_failed_notification(async_session):
    """
    NTF-083: Replay failed notification.
    Tests replaying failed notifications with attempt tracking and audit trail.
    """
    store = NotificationStoreManager(async_session)
    dlq_mgr = DeadLetterQueueManager(async_session)

    # Create failed notification
    notif = await store.create_notification(
        notification_id="ntf-replay-001",
        tenant_id="tenant-replay",
        user_id="user-3",
        channel="EMAIL",
        body="Replay test",
        idempotency_key="replay-idem-1"
    )
    from sqlalchemy import update
    from models.store import NotificationRecord
    await async_session.execute(
        update(NotificationRecord)
        .where(NotificationRecord.id == "ntf-replay-001")
        .values(status=NotificationStatus.FAILED.value)
    )
    await async_session.commit()

    # Replay failed notification
    replayed = await dlq_mgr.replay_notification(
        tenant_id="tenant-replay",
        notification_id="ntf-replay-001",
        actor="support@example.com"
    )
    assert replayed.status == NotificationStatus.QUEUED.value

    # Verify attempt recorded
    attempts = await store.get_delivery_attempts("ntf-replay-001")
    assert any("REPLAY" in a.id for a in attempts)

    # Verify audit entry
    audit_logs = await store.get_audit_logs(tenant_id="tenant-replay", resource_type="notification")
    assert any(a.action == "NOTIFICATION_REPLAYED" for a in audit_logs)
