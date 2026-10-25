import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
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
async def test_NTF_071_dead_letter_queue(async_session):
    """
    NTF-071: Dead-letter queue.
    Tests routing permanently failed notifications to DLQ with diagnostic audit trail.
    """
    dlq_mgr = DeadLetterQueueManager(async_session)

    # Route exhausted notification to DLQ
    entry = await dlq_mgr.send_to_dlq(
        notification_id="ntf-exhausted-001",
        tenant_id="tenant-dlq",
        failure_reason="Max retries (3) exceeded: 503 SERVICE_UNAVAILABLE from all providers",
        attempt_count=3
    )

    assert entry.id == "dlq_ntf-exhausted-001"
    assert entry.notification_id == "ntf-exhausted-001"
    assert entry.attempt_count == 3

    # Query DLQ records for tenant
    items = await dlq_mgr.list_dlq("tenant-dlq")
    assert len(items) == 1
    assert "Max retries" in items[0].failure_reason
