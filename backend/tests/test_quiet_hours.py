import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager, NotificationPriority
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
async def test_NTF_089_quiet_hours_suppression(async_session):
    """
    NTF-089: Quiet hours suppression.
    Tests suppressing non-urgent notifications during overnight quiet hours (22:00 to 08:00).
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    # Set quiet hours from 22:00 to 08:00
    await store.set_user_preference(
        tenant_id="tenant-qh",
        user_id="user-sleep",
        quiet_hours_start="22:00",
        quiet_hours_end="08:00"
    )

    # Time at 23:30 (inside quiet hours)
    night_time = datetime(2026, 10, 24, 23, 30, 0, tzinfo=timezone.utc)

    # Normal notification at night: SUPPRESSED
    dec_night = await engine.evaluate_dispatch(
        tenant_id="tenant-qh",
        user_id="user-sleep",
        channel="SMS",
        priority=NotificationPriority.NORMAL.value,
        current_time=night_time
    )
    assert dec_night.allowed is False
    assert dec_night.suppression_reason == SuppressionReason.QUIET_HOURS

    # URGENT notification at night: BYPASSES quiet hours
    dec_urgent = await engine.evaluate_dispatch(
        tenant_id="tenant-qh",
        user_id="user-sleep",
        channel="SMS",
        priority=NotificationPriority.URGENT.value,
        current_time=night_time
    )
    assert dec_urgent.allowed is True

    # Normal notification at 14:00 (outside quiet hours): ALLOWED
    day_time = datetime(2026, 10, 24, 14, 0, 0, tzinfo=timezone.utc)
    dec_day = await engine.evaluate_dispatch(
        tenant_id="tenant-qh",
        user_id="user-sleep",
        channel="SMS",
        priority=NotificationPriority.NORMAL.value,
        current_time=day_time
    )
    assert dec_day.allowed is True
