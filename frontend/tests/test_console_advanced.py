"""
Tests for Advanced Operations Console (NTF-139, NTF-141, NTF-146, NTF-148, NTF-150).
- NTF-139: Delivery overview
- NTF-141: Provider dashboard
- NTF-146: Queue monitoring
- NTF-148: Dead-letter viewer
- NTF-150: Delivery detail view
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base, get_db
from api.app import app
from models.store import NotificationStoreManager, NotificationStatus, NotificationPriority


@pytest_asyncio.fixture
async def console_client_and_session():
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
async def test_NTF_139_delivery_overview(console_client_and_session):
    """
    NTF-139: Delivery overview.
    Tests /api/v1/console/overview returning aggregated status counts and recent items.
    """
    client, session_maker = console_client_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        await store.create_notification(
            notification_id="ntf-ov-1",
            tenant_id="tenant-ov",
            user_id="user-1",
            channel="EMAIL",
            body="Overview test 1",
            idempotency_key="key-ov-1"
        )
        await store.create_notification(
            notification_id="ntf-ov-2",
            tenant_id="tenant-ov",
            user_id="user-2",
            channel="SMS",
            body="Overview test 2",
            idempotency_key="key-ov-2"
        )

    res = await client.get("/api/v1/console/overview")
    assert res.status_code == 200
    data = res.json()
    assert "status_counts" in data
    assert data["status_counts"]["total"] >= 2
    assert len(data["recent_deliveries"]) >= 2


@pytest.mark.asyncio
async def test_NTF_141_provider_dashboard(console_client_and_session):
    """
    NTF-141: Provider dashboard.
    Tests /api/v1/console/providers returning provider health and latency metrics.
    """
    client, _ = console_client_and_session

    res = await client.get("/api/v1/console/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert len(data["providers"]) >= 3
    channels = [p["channel"] for p in data["providers"]]
    assert "EMAIL" in channels
    assert "SMS" in channels
    assert "WEBHOOK" in channels


@pytest.mark.asyncio
async def test_NTF_146_queue_monitoring(console_client_and_session):
    """
    NTF-146: Queue monitoring.
    Tests /api/v1/console/queues reporting queue depth and active worker leases.
    """
    client, session_maker = console_client_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        await store.enqueue_item(
            item_id="item-q-1",
            queue_name="priority",
            payload={"notification_id": "ntf-1"},
            priority=50
        )

    res = await client.get("/api/v1/console/queues")
    assert res.status_code == 200
    data = res.json()
    assert "queues" in data
    assert data["total_enqueued"] >= 1
    priority_q = next((q for q in data["queues"] if q["queue_name"] == "priority"), None)
    assert priority_q is not None
    assert priority_q["depth"] >= 1


@pytest.mark.asyncio
async def test_NTF_148_dead_letter_viewer(console_client_and_session):
    """
    NTF-148: Dead-letter viewer.
    Tests /api/v1/console/dlq listing failed notifications for manual inspection.
    """
    client, session_maker = console_client_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        notif = await store.create_notification(
            notification_id="ntf-dlq-view-1",
            tenant_id="tenant-dlq",
            user_id="user-dlq",
            channel="SMS",
            body="Failed message",
            idempotency_key="dlq-view-key"
        )
        from sqlalchemy import update
        from models.store import NotificationRecord
        await session.execute(
            update(NotificationRecord)
            .where(NotificationRecord.id == "ntf-dlq-view-1")
            .values(status=NotificationStatus.FAILED.value)
        )
        await session.commit()

    res = await client.get("/api/v1/console/dlq")
    assert res.status_code == 200
    data = res.json()
    assert "dead_letters" in data
    assert any(d["id"] == "ntf-dlq-view-1" for d in data["dead_letters"])


@pytest.mark.asyncio
async def test_NTF_150_delivery_detail_view(console_client_and_session):
    """
    NTF-150: Delivery detail view.
    Tests /api/v1/console/notifications/{id} returning payload, attempts, and lifecycle timeline.
    """
    client, session_maker = console_client_and_session

    async with session_maker() as session:
        store = NotificationStoreManager(session)
        notif = await store.create_notification(
            notification_id="ntf-detail-150",
            tenant_id="tenant-detail",
            user_id="user-detail-1",
            channel="EMAIL",
            body="Detailed delivery inspection",
            idempotency_key="detail-key-150"
        )
        await store.record_delivery_attempt(
            attempt_id="att-detail-1",
            notification_id="ntf-detail-150",
            provider_id="email-default",
            status="SUCCESS",
            latency_ms=28
        )

    res = await client.get("/api/v1/console/notifications/ntf-detail-150")
    assert res.status_code == 200
    data = res.json()
    assert data["notification"]["id"] == "ntf-detail-150"
    assert len(data["delivery_attempts"]) >= 1
    assert data["delivery_attempts"][0]["provider_id"] == "email-default"
    assert len(data["timeline"]) >= 2
