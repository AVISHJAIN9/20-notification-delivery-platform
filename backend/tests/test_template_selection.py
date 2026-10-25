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
async def test_NTF_017_template_selection(async_session):
    """
    NTF-017: Template selection.
    Tests dynamic selection of active template based on tenant, template name, channel, and version.
    """
    engine = TemplateEngine(async_session)

    # Register email template v1 and v2
    await engine.register_template(
        template_id="tmpl-email-1",
        tenant_id="tenant-alpha",
        name="order_confirmation",
        channel="EMAIL",
        subject_template="Order {{order_id}} confirmed",
        body_template="Thank you for your order {{order_id}}",
        version=1
    )
    await engine.register_template(
        template_id="tmpl-email-2",
        tenant_id="tenant-alpha",
        name="order_confirmation",
        channel="EMAIL",
        subject_template="Order {{order_id}} confirmed!",
        body_template="Thanks for order {{order_id}}. Track here: {{link}}",
        version=2
    )

    # Register SMS template v1
    await engine.register_template(
        template_id="tmpl-sms-1",
        tenant_id="tenant-alpha",
        name="order_confirmation",
        channel="SMS",
        body_template="Order {{order_id}} confirmed. Track: {{link}}",
        version=1
    )

    # 1. Select latest EMAIL template -> should be version 2
    selected_email = await engine.select_template(tenant_id="tenant-alpha", name="order_confirmation", channel="EMAIL")
    assert selected_email is not None
    assert selected_email.version == 2
    assert selected_email.channel == "EMAIL"

    # 2. Select explicit version 1 EMAIL template
    v1_email = await engine.select_template(tenant_id="tenant-alpha", name="order_confirmation", channel="EMAIL", version=1)
    assert v1_email is not None
    assert v1_email.version == 1

    # 3. Select SMS template -> should be version 1
    selected_sms = await engine.select_template(tenant_id="tenant-alpha", name="order_confirmation", channel="SMS")
    assert selected_sms is not None
    assert selected_sms.channel == "SMS"
    assert selected_sms.version == 1

    # 4. Non-existent channel for this template returns None
    missing = await engine.select_template(tenant_id="tenant-alpha", name="order_confirmation", channel="PUSH")
    assert missing is None
