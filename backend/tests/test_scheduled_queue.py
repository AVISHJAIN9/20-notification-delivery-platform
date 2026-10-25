import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager
from queues.dispatcher import ScheduledQueueManager

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
async def test_NTF_057_scheduled_queue(async_session):
    """
    NTF-057: Scheduled queue.
    Tests holding scheduled notifications until their release timestamp arrives.
    """
    store = NotificationStoreManager(async_session)
    sq = ScheduledQueueManager(async_session)

    notif = await store.create_notification(
        notification_id="ntf-future-1",
        tenant_id="tenant-sched",
        user_id="user-1",
        channel="EMAIL",
        body="Future Alert",
        idempotency_key="key-sched-1"
    )

    base_time = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    future_time = base_time + timedelta(hours=2)

    await sq.schedule(
        job_id="job-future",
        notification_id="ntf-future-1",
        tenant_id="tenant-sched",
        run_at=future_time
    )

    # 1. Polling at base_time: Nothing due yet
    due_early = await sq.poll_due_jobs(current_time=base_time)
    assert len(due_early) == 0

    # 2. Polling at future_time + 10 mins: Job is released
    due_later = await sq.poll_due_jobs(current_time=future_time + timedelta(minutes=10))
    assert len(due_later) == 1
    assert due_later[0] == "ntf-future-1"

@pytest.mark.asyncio
async def test_NTF_059_scheduled_queue_real_time_and_clock(async_session):
    """
    NTF-059: Scheduled queue.
    Tests due-time release with both injected clock and a real-time async sleep test.
    """
    import asyncio
    store = NotificationStoreManager(async_session)
    sq = ScheduledQueueManager(async_session)

    # 1. Injected clock test
    notif1 = await store.create_notification(
        notification_id="ntf-clock-1",
        tenant_id="tenant-time",
        user_id="user-t1",
        channel="EMAIL",
        body="Clock test",
        idempotency_key="key-clock-1"
    )
    t0 = datetime(2026, 11, 1, 9, 0, 0, tzinfo=timezone.utc)
    t_due = t0 + timedelta(seconds=30)
    await sq.schedule("job-clk-1", "ntf-clock-1", "tenant-time", t_due)

    # Poll before due time
    assert len(await sq.poll_due_jobs(current_time=t0 + timedelta(seconds=20))) == 0
    # Poll after due time
    due = await sq.poll_due_jobs(current_time=t0 + timedelta(seconds=35))
    assert len(due) == 1
    assert due[0] == "ntf-clock-1"

    # 2. Real-time test with asyncio.sleep
    notif2 = await store.create_notification(
        notification_id="ntf-realtime-1",
        tenant_id="tenant-time",
        user_id="user-t2",
        channel="EMAIL",
        body="Realtime test",
        idempotency_key="key-clock-2"
    )
    now_real = datetime.now(timezone.utc)
    due_real = now_real + timedelta(milliseconds=100)
    await sq.schedule("job-real-1", "ntf-realtime-1", "tenant-time", due_real)

    # Immediately poll -> not due yet
    assert len(await sq.poll_due_jobs()) == 0

    # Sleep 150ms -> now due!
    await asyncio.sleep(0.15)
    real_due = await sq.poll_due_jobs()
    assert len(real_due) == 1
    assert real_due[0] == "ntf-realtime-1"
