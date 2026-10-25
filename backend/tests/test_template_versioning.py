import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from templates.engine import TemplateEngine

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
async def test_NTF_029_template_versioning(async_session):
    """
    NTF-029: Template versioning.
    Tests storing multiple versions of the same template and selecting explicit vs latest versions.
    """
    engine = TemplateEngine(async_session)

    # Version 1: Basic
    await engine.register_template(
        template_id="tmpl-v1",
        tenant_id="tenant-saas",
        name="billing_alert",
        channel="EMAIL",
        body_template="Payment due on {{due_date}}.",
        version=1
    )

    # Version 2: Rich HTML
    await engine.register_template(
        template_id="tmpl-v2",
        tenant_id="tenant-saas",
        name="billing_alert",
        channel="EMAIL",
        body_template="<b>Urgent:</b> Payment of ${{amount}} due on {{due_date}}.",
        version=2
    )

    # Query latest: returns v2
    latest = await engine.get_template_version("tenant-saas", "billing_alert")
    assert latest.version == 2
    assert "<b>Urgent:</b>" in latest.body_template

    # Query specific: v1
    v1 = await engine.get_template_version("tenant-saas", "billing_alert", version=1)
    assert v1.version == 1
    assert "Payment due on" in v1.body_template
