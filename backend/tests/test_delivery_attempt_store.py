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
async def test_NTF_004_delivery_attempt_store(async_session):
    """
    NTF-004: Delivery attempt store.
    Tests recording sequential delivery attempts with latencies and error diagnostics.
    """
    mgr = NotificationStoreManager(async_session)

    # Need parent notification
    notif = await mgr.create_notification(
        notification_id="ntf-attempt-test",
        tenant_id="tenant-saas",
        user_id="user-1",
        channel="EMAIL",
        body="Verification email",
        idempotency_key="attempt-key-1"
    )

    # Attempt 1: Failed
    att1 = await mgr.record_delivery_attempt(
        attempt_id="att-1",
        notification_id="ntf-attempt-test",
        provider_id="provider-sendgrid",
        status="FAILED",
        error_code="RATE_LIMITED",
        error_message="Too many requests",
        latency_ms=120
    )
    assert att1.status == "FAILED"

    # Attempt 2: Success
    att2 = await mgr.record_delivery_attempt(
        attempt_id="att-2",
        notification_id="ntf-attempt-test",
        provider_id="provider-mailgun",
        status="SUCCESS",
        latency_ms=85
    )
    assert att2.status == "SUCCESS"

    # Query attempts
    history = await mgr.get_delivery_attempts("ntf-attempt-test")
    assert len(history) == 2
    assert history[0].provider_id == "provider-sendgrid"
    assert history[1].provider_id == "provider-mailgun"
