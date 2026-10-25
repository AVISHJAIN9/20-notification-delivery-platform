"""
Tests for Project 20 Backend APIs & Services (NTF-101, NTF-103, NTF-105, NTF-109, NTF-110).
- NTF-101: Delivery API
- NTF-103: Scheduling API
- NTF-105: Retry API
- NTF-109: Health endpoint
- NTF-110: Readiness endpoint
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base, get_db
from api.app import app
from models.store import NotificationStoreManager, NotificationStatus


@pytest_asyncio.fixture
async def client_and_session():
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
        yield ac, session_maker

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_NTF_101_delivery_api(client_and_session):
    """
    NTF-101: Delivery API.
    Tests POST /api/v1/delivery with real channel dispatch, idempotency, and status return.
    """
    client, session_maker = client_and_session

    payload = {
        "tenant_id": "tenant-deliv",
        "user_id": "user-deliv-1",
        "channel": "EMAIL",
        "recipient": "customer@company.com",
        "subject": "Monthly Statement",
        "body": "Here is your monthly invoice statement.",
        "priority": "HIGH",
        "idempotency_key": "deliv-key-101",
        "category": "billing"
    }

    # 1. First delivery request
    res = await client.post("/api/v1/delivery", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "DELIVERED"
    assert data["channel"] == "EMAIL"
    assert data["is_duplicate"] is False
    assert "notification_id" in data
    assert "X-Request-ID" in res.headers

    # 2. Duplicate delivery request with same idempotency key
    res_dup = await client.post("/api/v1/delivery", json=payload)
    assert res_dup.status_code == 200
    data_dup = res_dup.json()
    assert data_dup["notification_id"] == data["notification_id"]
    assert data_dup["is_duplicate"] is True


@pytest.mark.asyncio
async def test_NTF_103_scheduling_api(client_and_session):
    """
    NTF-103: Scheduling API.
    Tests scheduling a future notification job and querying due jobs.
    """
    client, session_maker = client_and_session

    run_time = datetime.now(timezone.utc) + timedelta(hours=2)
    payload = {
        "job_id": "job-sched-103",
        "notification_id": "ntf-sched-103",
        "tenant_id": "tenant-sched",
        "run_at": run_time.isoformat()
    }

    # 1. Schedule job
    res = await client.post("/api/v1/schedule", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == "job-sched-103"
    assert data["status"] == "PENDING"

    # 2. Query due jobs right now -> should not include future job
    res_due = await client.get("/api/v1/schedule/due")
    assert res_due.status_code == 200
    due_jobs = res_due.json()
    assert not any(j["job_id"] == "job-sched-103" for j in due_jobs)

    # 3. Query due jobs in the future -> should include job
    future_check = (run_time + timedelta(minutes=5)).isoformat()
    res_future = await client.get(f"/api/v1/schedule/due?check_time={future_check}")
    assert res_future.status_code == 200
    future_jobs = res_future.json()
    assert any(j["job_id"] == "job-sched-103" for j in future_jobs)


@pytest.mark.asyncio
async def test_NTF_105_retry_api(client_and_session):
    """
    NTF-105: Retry API.
    Tests retrying and replaying failed/dead-lettered notifications.
    """
    client, session_maker = client_and_session

    # Seed a failed notification
    async with session_maker() as session:
        store = NotificationStoreManager(session)
        notif = await store.create_notification(
            notification_id="ntf-retry-api-1",
            tenant_id="tenant-retry-api",
            user_id="user-r1",
            channel="SMS",
            body="Security code 123456",
            idempotency_key="retry-api-key-1"
        )
        from sqlalchemy import update
        from models.store import NotificationRecord
        await session.execute(
            update(NotificationRecord)
            .where(NotificationRecord.id == "ntf-retry-api-1")
            .values(status=NotificationStatus.FAILED.value)
        )
        await session.commit()

    # 1. Execute manual retry
    retry_payload = {
        "actor": "admin@tenant.com",
        "tenant_id": "tenant-retry-api"
    }
    res_retry = await client.post("/api/v1/notifications/ntf-retry-api-1/retry", json=retry_payload)
    assert res_retry.status_code == 200
    retry_data = res_retry.json()
    assert retry_data["status"] == "QUEUED"
    assert "scheduled for retry" in retry_data["message"]

    # 2. Execute replay
    res_replay = await client.post("/api/v1/notifications/ntf-retry-api-1/replay", json=retry_payload)
    assert res_replay.status_code == 200
    replay_data = res_replay.json()
    assert replay_data["status"] == "QUEUED"
    assert "replayed" in replay_data["message"]


@pytest.mark.asyncio
async def test_NTF_109_health_endpoint(client_and_session):
    """
    NTF-109: Health endpoint.
    Tests /healthz returning HTTP 200 and liveness payload.
    """
    client, _ = client_and_session

    res = await client.get("/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "20-notification-delivery-platform"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_NTF_110_readiness_endpoint(client_and_session):
    """
    NTF-110: Readiness endpoint.
    Tests /readyz validating live database connectivity.
    """
    client, _ = client_and_session

    res = await client.get("/readyz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["service"] == "20-notification-delivery-platform"
