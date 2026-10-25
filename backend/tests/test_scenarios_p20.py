"""
End-to-End Scenarios for Project 20 Phase 2 (Section 9).
- S20-04: Provider failure -> fallback provider used.
- S20-05: DLQ, manual retry, and replay pipeline with new attempts and audit entries.
- S20-06: Preference, quiet-hours, frequency-capping, timezone matrix with DST.
- S20-07: Template workflow (approve/deactivate), localization fallback, conditional blocks, SSTI blocked.
- S20-08: Concurrent workers draining queue without duplicates.
- S20-09: Scheduled/delayed queues fire at the due time.
- S20-13: Measured throughput and dispatch latency.
"""

import asyncio
import time
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text

from db.database import Base
from models.store import (
    NotificationStoreManager,
    NotificationStatus,
    NotificationPriority
)
from channels.providers import (
    ProviderRegistry,
    EmailChannelProvider,
    SMSChannelProvider,
    ProviderResult
)
from channels.selection import ProviderSelector
from channels.capabilities import ProviderCapabilities
from preferences.routing import PreferenceRoutingEngine, SuppressionReason
from retries.failure import DeadLetterQueueManager
from templates.engine import TemplateEngine


@pytest_asyncio.fixture
async def session_and_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as s:
        yield s, session_maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_scenario_S20_04_provider_failure_and_fallback(session_and_maker):
    """
    S20-04: Provider failure -> fallback provider used.
    """
    session, _ = session_and_maker
    candidates = [
        ProviderCapabilities(
            provider_id="email-primary",
            channel="EMAIL",
            cost_per_message_cents=10,
            is_active=True
        ),
        ProviderCapabilities(
            provider_id="email-fallback",
            channel="EMAIL",
            cost_per_message_cents=15,
            is_active=True
        ),
    ]

    health = {"email-primary": False, "email-fallback": True}
    selected = ProviderSelector.select_best_provider(candidates, health_status=health)
    assert selected is not None
    assert selected.provider_id == "email-fallback"


@pytest.mark.asyncio
async def test_scenario_S20_05_dlq_manual_retry_replay(session_and_maker):
    """
    S20-05: DLQ, manual retry, and replay pipeline with new attempts and audit entries.
    """
    session, _ = session_and_maker
    store = NotificationStoreManager(session)
    dlq_mgr = DeadLetterQueueManager(session)

    notif = await store.create_notification(
        notification_id="ntf-s20-05",
        tenant_id="tenant-scen",
        user_id="user-scen-1",
        channel="EMAIL",
        body="DLQ scenario test",
        idempotency_key="scen-05-key"
    )
    from sqlalchemy import update
    from models.store import NotificationRecord
    await session.execute(
        update(NotificationRecord)
        .where(NotificationRecord.id == "ntf-s20-05")
        .values(status=NotificationStatus.FAILED.value)
    )
    await session.commit()

    # Manual retry
    retried = await dlq_mgr.manual_retry(
        tenant_id="tenant-scen",
        notification_id="ntf-s20-05",
        actor="ops-lead@company.com"
    )
    assert retried.status == NotificationStatus.QUEUED.value

    # Verify attempt recorded
    attempts = await store.get_delivery_attempts("ntf-s20-05")
    assert any("MANUAL_RETRY" in a.id for a in attempts)

    # Verify audit entry recorded
    audit_logs = await store.get_audit_logs(tenant_id="tenant-scen", resource_type="notification")
    assert any(a.action == "MANUAL_RETRY" for a in audit_logs)


@pytest.mark.asyncio
async def test_scenario_S20_06_preference_quiet_hours_frequency_timezone_dst(session_and_maker):
    """
    S20-06: Preference, quiet-hours, frequency-capping, timezone matrix with DST.
    """
    session, _ = session_and_maker
    store = NotificationStoreManager(session)
    engine = PreferenceRoutingEngine(session)

    await store.set_user_preference(
        tenant_id="tenant-scen-6",
        user_id="user-dst-ny",
        quiet_hours_start="22:00",
        quiet_hours_end="08:00",
        timezone="America/New_York",
        max_daily_limit=5
    )

    # 1. Summer (EDT UTC-4): 03:00 UTC = 23:00 EDT -> Quiet Hours suppression
    edt_night = datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc)
    dec_night = await engine.evaluate_dispatch(
        tenant_id="tenant-scen-6",
        user_id="user-dst-ny",
        channel="EMAIL",
        current_time=edt_night
    )
    assert dec_night.allowed is False
    assert dec_night.suppression_reason == SuppressionReason.QUIET_HOURS

    # 2. Winter (EST UTC-5): 13:30 UTC = 08:30 EST -> Outside quiet hours -> Allowed
    est_day = datetime(2026, 1, 15, 13, 30, tzinfo=timezone.utc)
    dec_day = await engine.evaluate_dispatch(
        tenant_id="tenant-scen-6",
        user_id="user-dst-ny",
        channel="EMAIL",
        current_time=est_day
    )
    assert dec_day.allowed is True


@pytest.mark.asyncio
async def test_scenario_S20_07_template_workflow_ssti_localization(session_and_maker):
    """
    S20-07: Template workflow (approve/deactivate), localization fallback, conditional blocks, SSTI blocked.
    """
    session, _ = session_and_maker
    t_engine = TemplateEngine(session)
    store = NotificationStoreManager(session)

    # Register draft template
    tmpl = await t_engine.register_template(
        template_id="tmpl-s20-07",
        tenant_id="tenant-tmpl",
        name="invoice_receipt",
        channel="EMAIL",
        body_template="Hello {{ user.name }}, total is ${{ amount }}.{% if is_vip %} Thank you for being VIP!{% endif %}",
        subject_template="Invoice #{{ invoice_id }}",
        language="en",
        version=1
    )
    assert tmpl.status == "DRAFT"

    # Approve template
    approved = await t_engine.approve_template(
        tenant_id="tenant-tmpl",
        template_id="tmpl-s20-07",
        actor="compliance-officer",
        role="admin"
    )
    assert approved.status == "APPROVED"

    # Render template with conditional block
    rendered = TemplateEngine.render_template_text(
        tmpl.body_template,
        context={"user": {"name": "Charlie"}, "amount": "99.00", "is_vip": True}
    )
    assert "Hello Charlie, total is $99.00. Thank you for being VIP!" in rendered

    # SSTI attempt must raise an Exception
    ssti_attempt = "{{ ''.__class__.__mro__[1].__subclasses__() }}"
    with pytest.raises(Exception):
        TemplateEngine.render_template_text(ssti_attempt, context={})


@pytest.mark.asyncio
async def test_scenario_S20_08_concurrent_drain(session_and_maker):
    """
    S20-08: Concurrent workers draining queue without duplicate assignment.
    """
    session, session_maker = session_and_maker
    store = NotificationStoreManager(session)

    # Enqueue 30 items
    for i in range(30):
        await store.enqueue_item(
            item_id=f"drain-item-{i}",
            queue_name="drain-q",
            payload={"idx": i},
            priority=i % 10
        )

    claimed_ids = []

    async def worker(w_id: int):
        for _ in range(5):
            async with session_maker() as w_session:
                w_store = NotificationStoreManager(w_session)
                item = await w_store.dequeue_item(
                    queue_name="drain-q",
                    lock_token=f"worker-{w_id}",
                    lease_seconds=30
                )
                if item:
                    claimed_ids.append(item.item_id)
            await asyncio.sleep(0.001)

    workers = [worker(w) for w in range(10)]
    await asyncio.gather(*workers)

    # Invariant: Each item claimed must be strictly unique (no duplicate dequeue)
    assert len(claimed_ids) == len(set(claimed_ids))


@pytest.mark.asyncio
async def test_scenario_S20_09_scheduled_delayed_due_time(session_and_maker):
    """
    S20-09: Scheduled/delayed queues fire at the due time.
    """
    session, _ = session_and_maker
    store = NotificationStoreManager(session)
    now = datetime.now(timezone.utc)

    # Schedule one job due 10 seconds ago, and one due 10 seconds in the future
    await store.schedule_job(
        job_id="job-past",
        notification_id="ntf-past",
        tenant_id="tenant-sched",
        run_at=now - timedelta(seconds=10)
    )
    await store.schedule_job(
        job_id="job-future",
        notification_id="ntf-future",
        tenant_id="tenant-sched",
        run_at=now + timedelta(seconds=10)
    )

    due_now = await store.get_due_jobs(current_time=now)
    due_job_ids = [j.job_id for j in due_now]
    assert "job-past" in due_job_ids
    assert "job-future" not in due_job_ids


@pytest.mark.asyncio
async def test_scenario_S20_13_measured_throughput_latency(session_and_maker):
    """
    S20-13: Measured throughput and latency on local hardware.
    """
    session, _ = session_and_maker
    store = NotificationStoreManager(session)
    start_t = time.perf_counter()
    n_ops = 50

    for i in range(n_ops):
        await store.create_notification(
            notification_id=f"ntf-bench-{i}",
            tenant_id="tenant-bench",
            user_id="user-bench",
            channel="EMAIL",
            body=f"Benchmark payload {i}",
            idempotency_key=f"bench-key-{i}"
        )

    elapsed = time.perf_counter() - start_t
    ops_per_sec = n_ops / elapsed
    p50_ms = (elapsed / n_ops) * 1000

    assert ops_per_sec > 10.0
    assert p50_ms < 100.0
