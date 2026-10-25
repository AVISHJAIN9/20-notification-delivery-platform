import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager, NotificationStatus
from channels.providers import ProviderRegistry, EmailChannelProvider
from queues.dispatcher import DispatcherWorker, PriorityQueueManager

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
async def test_NTF_060_dispatcher_worker(async_session):
    """
    NTF-060: Dispatcher worker.
    Tests worker cycle: dequeue item -> send via provider -> record attempt -> mark DELIVERED.
    """
    store = NotificationStoreManager(async_session)
    qm = PriorityQueueManager(async_session)

    # Setup provider registry
    registry = ProviderRegistry()
    registry.register(EmailChannelProvider(provider_id="email-main"))

    # Create notification and enqueue
    notif = await store.create_notification(
        notification_id="ntf-worker-test",
        tenant_id="tenant-prod",
        user_id="user-worker",
        channel="EMAIL",
        subject="Worker Dispatch Test",
        body="Message content",
        idempotency_key="key-worker-1",
        metadata={"recipient": "worker@example.com"}
    )

    await qm.enqueue(
        item_id="q-worker-1",
        queue_name="dispatch",
        payload={"notification_id": "ntf-worker-test"},
        priority=50
    )

    worker = DispatcherWorker(async_session, registry)
    result = await worker.process_next(queue_name="dispatch", worker_id="worker-node-1")

    assert result is not None
    assert result["status"] == "DELIVERED"
    assert result["notification_id"] == "ntf-worker-test"

    # Verify notification state updated in DB
    updated = await store.get_notification("ntf-worker-test")
    assert updated.status == NotificationStatus.DELIVERED.value
    assert updated.delivered_at is not None

    # Verify delivery attempt recorded
    attempts = await store.get_delivery_attempts("ntf-worker-test")
    assert len(attempts) == 1
    assert attempts[0].status == "SUCCESS"
