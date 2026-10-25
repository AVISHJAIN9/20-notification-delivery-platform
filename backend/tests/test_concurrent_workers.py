import pytest
import pytest_asyncio
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from queues.dispatcher import PriorityQueueManager

import tempfile
import os
from sqlalchemy import text

@pytest_asyncio.fixture
async def async_session_factory():
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    db_url = f"sqlite+aiosqlite:///{tmp_path}"
    engine = create_async_engine(
        db_url,
        connect_args={"timeout": 30.0},
        echo=False
    )
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA busy_timeout=5000;"))
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_maker
    await engine.dispose()
    for ext in ("", "-wal", "-shm"):
        f = tmp_path + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass

@pytest.mark.asyncio
async def test_NTF_068_worker_polling(async_session_factory):
    """
    NTF-068: Worker polling.
    Tests worker polling with lease acquisition and status checks.
    """
    async with async_session_factory() as session:
        qm = PriorityQueueManager(session)
        await qm.enqueue(item_id="poll-item-1", queue_name="poll_q", payload={"task": "poll_1"}, priority=10)

        # Worker 1 polls and leases item
        item = await qm.dequeue(queue_name="poll_q", lock_token="worker-p1", lease_seconds=10)
        assert item is not None
        assert item.item_id == "poll-item-1"
        assert item.lock_token == "worker-p1"

        # Worker 2 polls same queue immediately -> queue empty because item is locked
        item2 = await qm.dequeue(queue_name="poll_q", lock_token="worker-p2", lease_seconds=10)
        assert item2 is None

@pytest.mark.asyncio
async def test_NTF_069_20_concurrent_workers_drain_without_duplicates(async_session_factory):
    """
    NTF-069: Concurrent workers.
    Tests 20 concurrent workers draining a shared queue.
    Asserts every job is processed exactly once with zero duplicates.
    """
    TOTAL_JOBS = 100
    NUM_WORKERS = 20

    # 1. Enqueue 100 jobs
    async with async_session_factory() as session:
        qm = PriorityQueueManager(session)
        for i in range(TOTAL_JOBS):
            await qm.enqueue(
                item_id=f"job-{i}",
                queue_name="concurrent_drain",
                payload={"job_index": i},
                priority=i % 10
            )

    processed_jobs = []
    lock = asyncio.Lock()

    async def worker_loop(worker_id: str):
        while True:
            async with async_session_factory() as session:
                qm = PriorityQueueManager(session)
                item = await qm.dequeue(queue_name="concurrent_drain", lock_token=worker_id, lease_seconds=30)
                if not item:
                    # No more items available right now
                    break

                async with lock:
                    processed_jobs.append(item.item_id)

                await qm.acknowledge(item.item_id)
            await asyncio.sleep(0.001)

    # 2. Run 20 concurrent workers
    workers = [worker_loop(f"worker-{w}") for w in range(NUM_WORKERS)]
    await asyncio.gather(*workers)

    # 3. Assert exactly TOTAL_JOBS processed and no duplicate processing
    assert len(processed_jobs) == TOTAL_JOBS
    assert len(set(processed_jobs)) == TOTAL_JOBS
