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
async def test_NTF_003_user_preference_store(async_session):
    """
    NTF-003: User preference store.
    Tests recording user channel opt-ins, global opt-outs, and quiet hours.
    """
    mgr = NotificationStoreManager(async_session)

    pref = await mgr.set_user_preference(
        tenant_id="tenant-x",
        user_id="user-42",
        channel_opt_in={"EMAIL": True, "SMS": False, "PUSH": True},
        opt_out_all=False,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        max_daily_limit=20
    )

    assert pref.user_id == "user-42"
    assert pref.channel_opt_in["SMS"] is False
    assert pref.quiet_hours_start == "22:00"
    assert pref.max_daily_limit == 20

    # Query preference
    fetched = await mgr.get_user_preference("tenant-x", "user-42")
    assert fetched is not None
    assert fetched.channel_opt_in["EMAIL"] is True

    # Update to opt-out all
    updated = await mgr.set_user_preference(
        tenant_id="tenant-x",
        user_id="user-42",
        channel_opt_in={"EMAIL": False, "SMS": False},
        opt_out_all=True
    )
    assert updated.opt_out_all is True
