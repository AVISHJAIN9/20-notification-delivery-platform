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
async def test_NTF_099_notification_status_api(client):
    """
    NTF-099: Notification status API.
    Tests querying notification status and delivery attempt history via GET /v1/notifications/{id}.
    """
    # 1. Dispatch first
    res = await client.post("/v1/notifications", json={
        "tenant_id": "tenant-saas",
        "user_id": "user-stat",
        "channel": "SMS",
        "recipient": "+14155551234",
        "body": "SMS Verification: 994012",
        "idempotency_key": "status-key-999"
    })
    nid = res.json()["notification_id"]

    # 2. Query status
    status_res = await client.get(f"/v1/notifications/{nid}")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["notification"]["id"] == nid
    assert data["notification"]["status"] == "DELIVERED"
    assert len(data["delivery_attempts"]) >= 1
    assert data["delivery_attempts"][0]["status"] == "SUCCESS"
