import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
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
async def test_NTF_006_scheduled_job_store(async_session):
    """
    NTF-006: Scheduled-job store.
    Tests scheduling future notification jobs and querying due jobs by timestamp.
    """
    mgr = NotificationStoreManager(async_session)

    notif = await mgr.create_notification(
        notification_id="ntf-job-test",
        tenant_id="tenant-jobs",
        user_id="user-job",
        channel="EMAIL",
        body="Reminder tomorrow",
        idempotency_key="job-key-1"
    )

    now = datetime.now(timezone.utc)
    job_due_soon = now + timedelta(minutes=5)
    job_due_later = now + timedelta(days=2)

    # Schedule 2 jobs
    await mgr.schedule_job(
        job_id="job-1",
        notification_id="ntf-job-test",
        tenant_id="tenant-jobs",
        run_at=job_due_soon
    )
    await mgr.schedule_job(
        job_id="job-2",
        notification_id="ntf-job-test",
        tenant_id="tenant-jobs",
        run_at=job_due_later
    )

    # Check due jobs as of 10 minutes from now
    due = await mgr.get_due_jobs(current_time=now + timedelta(minutes=10))
    assert len(due) == 1
    assert due[0].job_id == "job-1"
