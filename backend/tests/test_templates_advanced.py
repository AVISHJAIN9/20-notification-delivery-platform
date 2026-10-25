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
async def test_NTF_037_language_selection_fallback_chain(async_session):
    """
    NTF-037: Language selection.
    Tests locale resolution with fallback chain: fr-CA -> fr -> en (default).
    """
    engine = TemplateEngine(async_session)

    # 1. Register English (default fallback)
    await engine.register_template(
        template_id="tmpl-en",
        tenant_id="tenant-i18n",
        name="billing_receipt",
        channel="EMAIL",
        subject_template="Your receipt",
        body_template="Thank you for your payment of {{amount}}.",
        language="en",
        version=1
    )

    # 2. Register Generic French (fr)
    await engine.register_template(
        template_id="tmpl-fr",
        tenant_id="tenant-i18n",
        name="billing_receipt",
        channel="EMAIL",
        subject_template="Votre reçu",
        body_template="Merci pour votre paiement de {{amount}}.",
        language="fr",
        version=1
    )

    # Query with exact fr match
    res_fr = await engine.select_template(
        tenant_id="tenant-i18n",
        name="billing_receipt",
        channel="EMAIL",
        language="fr"
    )
    assert res_fr is not None
    assert res_fr.language == "fr"
    assert "Merci" in res_fr.body_template

    # Query with fr-CA -> should fall back to fr since fr-CA is not registered
    res_ca = await engine.select_template(
        tenant_id="tenant-i18n",
        name="billing_receipt",
        channel="EMAIL",
        language="fr-CA"
    )
    assert res_ca is not None
    assert res_ca.language == "fr"

    # Query with de-DE -> should fall back to en
    res_de = await engine.select_template(
        tenant_id="tenant-i18n",
        name="billing_receipt",
        channel="EMAIL",
        language="de-DE"
    )
    assert res_de is not None
    assert res_de.language == "en"

def test_NTF_039_conditional_template_blocks_and_ssti_protection():
    """
    NTF-039: Conditional template blocks.
    Tests if/else conditional blocks and ensures SSTI cannot execute arbitrary code.
    """
    engine = TemplateEngine

    # 1. Conditional block: true branch
    template_str = "Hello {{ user.name }}, {% if is_vip %}VIP Lounge Access Granted!{% else %}Standard Pass{% endif %}"
    rendered_vip = engine.render_template_text(
        template_str,
        context={"user": {"name": "Alice"}, "is_vip": True}
    )
    assert "VIP Lounge Access Granted!" in rendered_vip
    assert "Standard Pass" not in rendered_vip

    # 2. Conditional block: false branch
    rendered_regular = engine.render_template_text(
        template_str,
        context={"user": {"name": "Bob"}, "is_vip": False}
    )
    assert "Standard Pass" in rendered_regular
    assert "VIP Lounge Access" not in rendered_regular

    # 3. SSTI protection: Attempting to access __class__ or __subclasses__ must raise SecurityError or render safely without executing
    malicious_template = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
    with pytest.raises(Exception):
        engine.render_template_text(malicious_template, context={})
