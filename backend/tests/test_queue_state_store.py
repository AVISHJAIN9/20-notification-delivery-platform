import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager

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
async def test_NTF_007_queue_state_store(async_session):
    """
    NTF-007: Queue state store.
    Tests enqueuing priority items and atomic dequeue with lease-based locking.
    """
    mgr = NotificationStoreManager(async_session)

    # 1. Enqueue low priority item
    await mgr.enqueue_item(
        item_id="q-low-1",
        queue_name="dispatch_queue",
        payload={"notif_id": "ntf-low"},
        priority=10
    )

    # 2. Enqueue urgent priority item
    await mgr.enqueue_item(
        item_id="q-urgent-1",
        queue_name="dispatch_queue",
        payload={"notif_id": "ntf-urgent"},
        priority=100
    )

    # 3. Dequeue: Should dequeue higher priority item first
    item = await mgr.dequeue_item(
        queue_name="dispatch_queue",
        lock_token="worker-token-alpha",
        lease_seconds=60
    )
    assert item is not None
    assert item.item_id == "q-urgent-1"
    assert item.priority == 100
    assert item.lock_token == "worker-token-alpha"

    # 4. Next dequeue yields the lower priority item
    next_item = await mgr.dequeue_item(
        queue_name="dispatch_queue",
        lock_token="worker-token-beta"
    )
    assert next_item is not None
    assert next_item.item_id == "q-low-1"
