import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager
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
async def test_NTF_085_channel_preferences(async_session):
    """
    NTF-085: Channel preferences.
    Tests user configuring channel opt-in (Email: ON, SMS: OFF), suppressing SMS and allowing Email.
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    await store.set_user_preference(
        tenant_id="tenant-ch",
        user_id="user-ch-1",
        channel_opt_in={"EMAIL": True, "SMS": False}
    )

    # 1. SMS notification: SUPPRESSED
    sms_decision = await engine.evaluate_dispatch(
        tenant_id="tenant-ch",
        user_id="user-ch-1",
        channel="SMS"
    )
    assert sms_decision.allowed is False
    assert sms_decision.suppression_reason == SuppressionReason.OPT_OUT_CHANNEL

    # 2. EMAIL notification: ALLOWED
    email_decision = await engine.evaluate_dispatch(
        tenant_id="tenant-ch",
        user_id="user-ch-1",
        channel="EMAIL"
    )
    assert email_decision.allowed is True
