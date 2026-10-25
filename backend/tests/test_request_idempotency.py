import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from core.engine import NotificationCoreEngine, NotificationRequestPayload, ChannelType

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
async def test_NTF_019_request_idempotency(async_session):
    """
    NTF-019: Request idempotency.
    Tests deduplication of identical requests using idempotency key per tenant.
    """
    engine = NotificationCoreEngine(async_session)

    payload = NotificationRequestPayload(
        tenant_id="tenant-alpha",
        user_id="user-idem",
        channel=ChannelType.EMAIL,
        recipient="idem@example.com",
        body="One-time passcode: 882199",
        idempotency_key="unique-idempotency-key-42"
    )

    # First request: new
    res1 = await engine.ingest_request(payload)
    assert res1.is_duplicate is False
    orig_id = res1.notification_id

    # Second request with SAME idempotency key: duplicate, returns original ID
    res2 = await engine.ingest_request(payload)
    assert res2.is_duplicate is True
    assert res2.notification_id == orig_id
