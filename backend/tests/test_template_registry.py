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
async def test_NTF_028_template_registry(async_session):
    """
    NTF-028: Template registry.
    Tests registering templates per tenant and querying by name and channel.
    """
    engine = TemplateEngine(async_session)

    # Register email template
    tmpl = await engine.register_template(
        template_id="reg-tmpl-01",
        tenant_id="tenant-acme",
        name="order_confirmation",
        channel="EMAIL",
        subject_template="Order #{{order_id}} Confirmed",
        body_template="Thank you for your order #{{order_id}} totaling ${{total}}."
    )

    assert tmpl.name == "order_confirmation"
    assert tmpl.channel == "EMAIL"
    assert tmpl.is_active is True

    # Retrieve from registry
    fetched = await engine.get_template_version("tenant-acme", "order_confirmation")
    assert fetched is not None
    assert fetched.subject_template == "Order #{{order_id}} Confirmed"
