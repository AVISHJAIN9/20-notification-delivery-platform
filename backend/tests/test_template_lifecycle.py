import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from templates.engine import TemplateEngine
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
async def test_NTF_030_template_approval(async_session):
    """
    NTF-030: Template approval.
    Enforces role checks, state transition from DRAFT to APPROVED, and writes audit log.
    """
    engine = TemplateEngine(async_session)
    store = NotificationStoreManager(async_session)

    tmpl = await engine.register_template(
        template_id="tmpl-approval-test",
        tenant_id="tenant-audit",
        name="newsletter",
        channel="EMAIL",
        subject_template="Monthly Update",
        body_template="Here is the newsletter.",
        version=1
    )

    # 1. Non-approver role gets PermissionError
    with pytest.raises(PermissionError, match="Unauthorized role"):
        await engine.approve_template(
            tenant_id="tenant-audit",
            template_id="tmpl-approval-test",
            actor="intern@example.com",
            role="viewer"
        )

    # 2. Approved by admin role
    approved = await engine.approve_template(
        tenant_id="tenant-audit",
        template_id="tmpl-approval-test",
        actor="sec_officer@example.com",
        role="admin"
    )
    assert approved.status == "APPROVED"
    assert approved.is_active is True

    # 3. Illegal transition: cannot re-approve an already APPROVED template directly
    with pytest.raises(ValueError, match="Illegal transition"):
        await engine.approve_template(
            tenant_id="tenant-audit",
            template_id="tmpl-approval-test",
            actor="sec_officer@example.com",
            role="admin"
        )

    # 4. Check audit log written
    audit_logs = await store.get_audit_logs(
        tenant_id="tenant-audit",
        resource_type="template",
        resource_id="tmpl-approval-test"
    )
    assert len(audit_logs) >= 1
    assert any(log.action == "TEMPLATE_APPROVED" for log in audit_logs)

@pytest.mark.asyncio
async def test_NTF_032_template_deactivation(async_session):
    """
    NTF-032: Template deactivation.
    Tests deactivating template, role checks, and audit entry generation.
    """
    engine = TemplateEngine(async_session)
    store = NotificationStoreManager(async_session)

    tmpl = await engine.register_template(
        template_id="tmpl-deact-test",
        tenant_id="tenant-deact",
        name="promo_blast",
        channel="SMS",
        body_template="50% off today only!",
        version=1
    )

    # First approve it
    await engine.approve_template(
        tenant_id="tenant-deact",
        template_id="tmpl-deact-test",
        actor="admin@example.com",
        role="admin"
    )

    # 1. Non-authorized role cannot deactivate
    with pytest.raises(PermissionError, match="Unauthorized role"):
        await engine.deactivate_template(
            tenant_id="tenant-deact",
            template_id="tmpl-deact-test",
            actor="guest@example.com",
            role="guest"
        )

    # 2. Authorized role (developer or admin) deactivates
    deactivated = await engine.deactivate_template(
        tenant_id="tenant-deact",
        template_id="tmpl-deact-test",
        actor="dev@example.com",
        role="developer"
    )
    assert deactivated.status == "DEACTIVATED"
    assert deactivated.is_active is False

    # 3. Deactivating already deactivated template raises ValueError
    with pytest.raises(ValueError, match="already DEACTIVATED"):
        await engine.deactivate_template(
            tenant_id="tenant-deact",
            template_id="tmpl-deact-test",
            actor="dev@example.com",
            role="developer"
        )

    # 4. Verify audit log entry exists
    audit_logs = await store.get_audit_logs(
        tenant_id="tenant-deact",
        resource_type="template",
        resource_id="tmpl-deact-test"
    )
    assert any(log.action == "TEMPLATE_DEACTIVATED" for log in audit_logs)
