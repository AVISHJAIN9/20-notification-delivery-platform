import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from core.engine import NotificationCoreEngine, NotificationRequestPayload, ChannelType
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
async def test_NTF_023_tenant_attribution(async_session):
    """
    NTF-023: Tenant attribution.
    Tests strict tenant isolation across ingestion and querying.
    """
    engine = NotificationCoreEngine(async_session)
    store = NotificationStoreManager(async_session)

    # Ingest for Tenant A
    res_a = await engine.ingest_request(NotificationRequestPayload(
        tenant_id="tenant-acme",
        user_id="user-1",
        channel=ChannelType.EMAIL,
        recipient="user1@acme.com",
        body="Acme notification",
        idempotency_key="key-acme-1"
    ))

    # Ingest for Tenant B
    res_b = await engine.ingest_request(NotificationRequestPayload(
        tenant_id="tenant-globex",
        user_id="user-2",
        channel=ChannelType.EMAIL,
        recipient="user2@globex.com",
        body="Globex notification",
        idempotency_key="key-globex-1"
    ))

    # Query with tenant attribution check
    notif_a = await store.get_notification_scoped(tenant_id="tenant-acme", notification_id=res_a.notification_id)
    assert notif_a is not None
    assert notif_a.tenant_id == "tenant-acme"

    # Cross-tenant attempt: Globex cannot query Acme notification
    cross_notif = await store.get_notification_scoped(tenant_id="tenant-globex", notification_id=res_a.notification_id)
    assert cross_notif is None

    # List scoped by tenant
    acme_list = await store.list_notifications_by_tenant(tenant_id="tenant-acme")
    assert len(acme_list) == 1
    assert acme_list[0].id == res_a.notification_id

    globex_list = await store.list_notifications_by_tenant(tenant_id="tenant-globex")
    assert len(globex_list) == 1
    assert globex_list[0].id == res_b.notification_id
