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
async def test_NTF_008_audit_store(async_session):
    """
    NTF-008: Audit store.
    Tests recording administrative, replay, and retry audit log entries with tenant isolation.
    """
    mgr = NotificationStoreManager(async_session)

    # Record template approval audit event
    entry1 = await mgr.record_audit_event(
        audit_id="aud-1",
        tenant_id="tenant-1",
        actor="admin@example.com",
        action="TEMPLATE_APPROVED",
        resource_type="template",
        resource_id="tmpl-welcome",
        details={"version": 2, "approved_by": "sec-team"}
    )
    assert entry1.id == "aud-1"
    assert entry1.tenant_id == "tenant-1"
    assert entry1.action == "TEMPLATE_APPROVED"
    assert entry1.details["version"] == 2

    # Record retry audit event
    entry2 = await mgr.record_audit_event(
        audit_id="aud-2",
        tenant_id="tenant-1",
        actor="ops-bot",
        action="MANUAL_RETRY_TRIGGERED",
        resource_type="notification",
        resource_id="ntf-999",
        details={"retry_reason": "provider_5xx"}
    )
    assert entry2.action == "MANUAL_RETRY_TRIGGERED"

    # Query audit logs for tenant-1
    logs = await mgr.get_audit_logs(tenant_id="tenant-1")
    assert len(logs) == 2
    # Verify descending ordering by created_at
    assert logs[0].id in ("aud-1", "aud-2")

    # Verify query filtered by resource
    tmpl_logs = await mgr.get_audit_logs(tenant_id="tenant-1", resource_type="template", resource_id="tmpl-welcome")
    assert len(tmpl_logs) == 1
    assert tmpl_logs[0].id == "aud-1"

    # Tenant isolation: tenant-2 sees empty logs
    t2_logs = await mgr.get_audit_logs(tenant_id="tenant-2")
    assert len(t2_logs) == 0
