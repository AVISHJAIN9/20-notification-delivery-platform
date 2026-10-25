import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager, NotificationStatus, NotificationPriority

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
async def test_NTF_001_notification_database(async_session):
    """
    NTF-001: Notification database.
    Tests recording notification requests, querying by ID, and enforcing idempotency.
    """
    mgr = NotificationStoreManager(async_session)

    # 1. Create notification
    notif = await mgr.create_notification(
        notification_id="ntf-001-test",
        tenant_id="tenant-acme",
        user_id="user-100",
        channel="EMAIL",
        subject="Welcome to Acme",
        body="Hello Alice, thanks for joining!",
        idempotency_key="idem-key-001",
        priority=NotificationPriority.HIGH.value,
        metadata={"campaign": "onboarding"}
    )

    assert notif.id == "ntf-001-test"
    assert notif.channel == "EMAIL"
    assert notif.priority == NotificationPriority.HIGH.value
    assert notif.status == NotificationStatus.PENDING.value
    assert notif.metadata["campaign"] == "onboarding"

    # 2. Query notification
    fetched = await mgr.get_notification("ntf-001-test")
    assert fetched is not None
    assert fetched.subject == "Welcome to Acme"

    # 3. Idempotent re-creation returns existing
    dup = await mgr.create_notification(
        notification_id="ntf-001-dup",
        tenant_id="tenant-acme",
        user_id="user-100",
        channel="EMAIL",
        subject="Different Subject",
        body="Different Body",
        idempotency_key="idem-key-001"
    )
    assert dup.id == "ntf-001-test"
    assert dup.subject == "Welcome to Acme"
