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
async def test_NTF_084_user_opt_out(async_session):
    """
    NTF-084: User opt-out management.
    Tests global opt-out suppressing promotional notifications while permitting critical/transactional ones.
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    # User opts out of all notifications
    await store.set_user_preference(
        tenant_id="tenant-opt",
        user_id="user-optout",
        opt_out_all=True
    )

    # 1. Promotional notification: SUPPRESSED
    decision_promo = await engine.evaluate_dispatch(
        tenant_id="tenant-opt",
        user_id="user-optout",
        channel="EMAIL",
        is_transactional=False
    )
    assert decision_promo.allowed is False
    assert decision_promo.suppression_reason == SuppressionReason.OPT_OUT_GLOBAL

    # 2. Transactional notification (e.g. Password Reset): ALLOWED
    decision_trans = await engine.evaluate_dispatch(
        tenant_id="tenant-opt",
        user_id="user-optout",
        channel="EMAIL",
        is_transactional=True
    )
    assert decision_trans.allowed is True
