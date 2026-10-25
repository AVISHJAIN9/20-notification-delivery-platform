import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager, NotificationStatus, NotificationPriority
from preferences.routing import PreferenceRoutingEngine, SuppressionReason

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
async def test_NTF_087_frequency_capping(async_session):
    """
    NTF-087: Frequency capping.
    Tests suppressing notifications when daily limit is reached, while allowing URGENT to bypass.
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    # User configured with max 2 notifications per day
    await store.set_user_preference(
        tenant_id="tenant-freq",
        user_id="user-freq-1",
        max_daily_limit=2
    )

    now = datetime.now(timezone.utc)

    # Record 2 delivered notifications today
    n1 = await store.create_notification(
        notification_id="ntf-d1",
        tenant_id="tenant-freq",
        user_id="user-freq-1",
        channel="EMAIL",
        body="Daily notif 1",
        idempotency_key="k-d-1"
    )
    n2 = await store.create_notification(
        notification_id="ntf-d2",
        tenant_id="tenant-freq",
        user_id="user-freq-1",
        channel="EMAIL",
        body="Daily notif 2",
        idempotency_key="k-d-2"
    )

    # Set status to DELIVERED
    from models.store import NotificationRecord
    from sqlalchemy import update
    await async_session.execute(
        update(NotificationRecord)
        .where(NotificationRecord.id.in_(["ntf-d1", "ntf-d2"]))
        .values(status=NotificationStatus.DELIVERED.value)
    )
    await async_session.commit()

    # 3rd Normal notification: FREQUENCY_CAPPED
    dec_norm = await engine.evaluate_dispatch(
        tenant_id="tenant-freq",
        user_id="user-freq-1",
        channel="EMAIL",
        priority=NotificationPriority.NORMAL.value,
        current_time=now
    )
    assert dec_norm.allowed is False
    assert dec_norm.suppression_reason == SuppressionReason.FREQUENCY_CAPPED

    # 3rd URGENT notification: BYPASSES limit
    dec_urgent = await engine.evaluate_dispatch(
        tenant_id="tenant-freq",
        user_id="user-freq-1",
        channel="EMAIL",
        priority=NotificationPriority.URGENT.value,
        current_time=now
    )
    assert dec_urgent.allowed is True
