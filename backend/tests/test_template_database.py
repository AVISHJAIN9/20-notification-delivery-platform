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
async def test_NTF_002_template_database(async_session):
    """
    NTF-002: Template database.
    Tests storing templates with versioning and retrieving active versions.
    """
    mgr = NotificationStoreManager(async_session)

    # Version 1
    t1 = await mgr.create_template(
        template_id="tmpl-v1",
        tenant_id="tenant-saas",
        name="password_reset",
        channel="EMAIL",
        subject_template="Reset your password",
        body_template="Hi {{name}}, your reset code is {{code}}.",
        version=1
    )
    assert t1.version == 1

    # Version 2
    t2 = await mgr.create_template(
        template_id="tmpl-v2",
        tenant_id="tenant-saas",
        name="password_reset",
        channel="EMAIL",
        subject_template="Password Reset Request",
        body_template="Hi {{name}}, click here to reset: {{link}}.",
        version=2
    )
    assert t2.version == 2

    # Query latest version
    latest = await mgr.get_template("tenant-saas", "password_reset")
    assert latest is not None
    assert latest.version == 2
    assert "{{link}}" in latest.body_template

    # Query specific version 1
    v1 = await mgr.get_template("tenant-saas", "password_reset", version=1)
    assert v1.version == 1
    assert "{{code}}" in v1.body_template
