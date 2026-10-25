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
async def test_NTF_098_notification_dispatch_api(client):
    """
    NTF-098: Notification dispatch API.
    Tests POST /v1/notifications dispatching messages to channels.
    """
    payload = {
        "tenant_id": "tenant-saas",
        "user_id": "user-api-1",
        "channel": "EMAIL",
        "recipient": "dispatch@example.com",
        "subject": "System Alert",
        "body": "API Dispatch working cleanly.",
        "idempotency_key": "dispatch-key-998"
    }

    # Dispatch notification
    res = await client.post("/v1/notifications", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "DELIVERED"
    assert data["notification_id"].startswith("ntf_")
    assert data["is_duplicate"] is False

    # Idempotent re-send
    dup_res = await client.post("/v1/notifications", json=payload)
    assert dup_res.status_code == 200
    assert dup_res.json()["is_duplicate"] is True
