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
async def test_NTF_014_notification_request_ingestion(async_session):
    """
    NTF-014: Notification request ingestion.
    Tests end-to-end ingestion pipeline creating pending notification records.
    """
    engine = NotificationCoreEngine(async_session)

    payload = NotificationRequestPayload(
        tenant_id="tenant-prod",
        user_id="user-ingest-1",
        channel=ChannelType.EMAIL,
        recipient="user@example.com",
        subject="Your Statement",
        body="Your statement is ready for download.",
        idempotency_key="key-ingest-101"
    )

    result = await engine.ingest_request(payload)
    assert result.is_duplicate is False
    assert result.status == NotificationStatus.PENDING
    assert result.notification_id.startswith("ntf_")

    stored = await engine.store.get_notification(result.notification_id)
    assert stored is not None
    assert stored.user_id == "user-ingest-1"
    assert stored.body == "Your statement is ready for download."
