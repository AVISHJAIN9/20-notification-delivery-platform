import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base, get_db
from api.app import app

@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()

@pytest.mark.asyncio
async def test_NTF_101_template_management_api(client):
    """
    NTF-101: Template management API.
    Tests POST /v1/templates and GET /v1/templates/{name}.
    """
    # 1. Create template
    create_payload = {
        "template_id": "tmpl-api-001",
        "tenant_id": "tenant-saas",
        "name": "welcome_email",
        "channel": "EMAIL",
        "subject_template": "Welcome {{name}}!",
        "body_template": "Hello {{name}}, welcome to our platform.",
        "version": 1
    }
    res = await client.post("/v1/templates", json=create_payload)
    assert res.status_code == 200
    assert res.json()["name"] == "welcome_email"

    # 2. Get template
    get_res = await client.get("/v1/templates/welcome_email", params={"tenant_id": "tenant-saas"})
    assert get_res.status_code == 200
    tmpl = get_res.json()
    assert tmpl["id"] == "tmpl-api-001"
    assert tmpl["channel"] == "EMAIL"
