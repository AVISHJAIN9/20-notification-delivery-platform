import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from core.engine import NotificationCoreEngine, NotificationRequestPayload, ChannelType, NotificationStatus

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
async def test_NTF_020_notification_state_machine(async_session):
    """
    NTF-020: Notification state machine.
    Tests valid progression: PENDING -> QUEUED -> DISPATCHING -> DELIVERED,
    and rejection of illegal backward or invalid transitions.
    """
    engine = NotificationCoreEngine(async_session)

    res = await engine.ingest_request(NotificationRequestPayload(
        tenant_id="tenant-sm",
        user_id="user-sm",
        channel=ChannelType.EMAIL,
        recipient="sm@example.com",
        body="State machine test",
        idempotency_key="sm-key-1"
    ))
    nid = res.notification_id
    assert res.status == NotificationStatus.PENDING

    # 1. PENDING -> QUEUED (Valid)
    s1 = await engine.transition_state(nid, NotificationStatus.QUEUED)
    assert s1.status == NotificationStatus.QUEUED.value

    # 2. QUEUED -> DISPATCHING (Valid)
    s2 = await engine.transition_state(nid, NotificationStatus.DISPATCHING)
    assert s2.status == NotificationStatus.DISPATCHING.value

    # 3. DISPATCHING -> DELIVERED (Valid)
    s3 = await engine.transition_state(nid, NotificationStatus.DELIVERED)
    assert s3.status == NotificationStatus.DELIVERED.value
    assert s3.delivered_at is not None

    # 4. DELIVERED -> PENDING (Illegal transition from terminal state)
    with pytest.raises(ValueError, match="Invalid state transition"):
        await engine.transition_state(nid, NotificationStatus.PENDING)
