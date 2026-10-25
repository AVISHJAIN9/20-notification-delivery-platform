import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from db.database import Base
from queues.dispatcher import PriorityQueueManager

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
async def test_NTF_056_priority_queue(async_session):
    """
    NTF-056: Priority queue.
    Tests prioritizing higher weight items (URGENT > NORMAL > LOW) on dequeue.
    """
    qm = PriorityQueueManager(async_session)

    # Enqueue items in arbitrary order
    await qm.enqueue(item_id="item-normal", queue_name="main", payload={"id": "norm"}, priority=10)
    await qm.enqueue(item_id="item-urgent", queue_name="main", payload={"id": "urg"}, priority=100)
    await qm.enqueue(item_id="item-low", queue_name="main", payload={"id": "low"}, priority=0)

    # First dequeue must be URGENT (priority 100)
    d1 = await qm.dequeue(queue_name="main", lock_token="worker-1")
    assert d1.item_id == "item-urgent"
    await qm.acknowledge("item-urgent")

    # Second dequeue must be NORMAL (priority 10)
    d2 = await qm.dequeue(queue_name="main", lock_token="worker-1")
    assert d2.item_id == "item-normal"
    await qm.acknowledge("item-normal")

    # Third dequeue must be LOW (priority 0)
    d3 = await qm.dequeue(queue_name="main", lock_token="worker-1")
    assert d3.item_id == "item-low"

@pytest.mark.asyncio
async def test_NTF_057_priority_queue_starvation_protection(async_session):
    """
    NTF-057: Priority queue with starvation protection.
    Tests that aged lower-priority items are processed before new high-priority items when threshold exceeded.
    """
    from datetime import datetime, timezone, timedelta
    from models.store import QueueStateRecord
    qm = PriorityQueueManager(async_session)

    # 1. Enqueue low-priority item that arrived 120 seconds ago
    await qm.enqueue(item_id="item-starved-low", queue_name="starve_q", payload={"task": "old_low"}, priority=0)
    # Manually backdate enqueued_at to simulate aging
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    stmt = select(QueueStateRecord).where(QueueStateRecord.item_id == "item-starved-low")
    res = await async_session.execute(stmt)
    rec = res.scalar_one()
    rec.enqueued_at = old_time
    await async_session.commit()

    # 2. Enqueue brand new urgent item (priority 100)
    await qm.enqueue(item_id="item-fresh-urgent", queue_name="starve_q", payload={"task": "new_urgent"}, priority=100)

    # 3. Dequeue with starvation protection threshold of 60 seconds
    # The starved low-priority item (waited 120s > 60s) MUST be dequeued before the fresh urgent item
    d1 = await qm.dequeue(queue_name="starve_q", lock_token="w-1", starvation_threshold_seconds=60)
    assert d1.item_id == "item-starved-low"
    await qm.acknowledge("item-starved-low")

    # 4. Next dequeue is the urgent item
    d2 = await qm.dequeue(queue_name="starve_q", lock_token="w-1", starvation_threshold_seconds=60)
    assert d2.item_id == "item-fresh-urgent"
