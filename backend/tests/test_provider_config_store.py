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
async def test_NTF_005_provider_config_store(async_session):
    """
    NTF-005: Provider configuration store.
    Tests configuring multiple providers with priority and rate limit settings.
    """
    mgr = NotificationStoreManager(async_session)

    # Primary SMS provider (Priority 1)
    p1 = await mgr.configure_provider(
        config_id="prov-twilio",
        tenant_id="tenant-prod",
        channel="SMS",
        provider_name="Twilio",
        credentials={"account_sid": "AC123", "auth_token": "secret"},
        priority=1,
        rate_limit_rps=50
    )
    assert p1.priority == 1

    # Secondary SMS provider (Priority 2)
    p2 = await mgr.configure_provider(
        config_id="prov-aws-sns",
        tenant_id="tenant-prod",
        channel="SMS",
        provider_name="AWS_SNS",
        credentials={"region": "us-east-1"},
        priority=2,
        rate_limit_rps=100
    )
    assert p2.priority == 2

    # Query active providers ordered by priority
    providers = await mgr.list_providers_for_channel("tenant-prod", "SMS")
    assert len(providers) == 2
    assert providers[0].provider_name == "Twilio"
    assert providers[1].provider_name == "AWS_SNS"
