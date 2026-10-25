"""
Queues, Scheduling, and Dispatcher Worker (NTF-056, NTF-057, NTF-060, NTF-062).
Provides:
- Priority queue management with lease-based locking (NTF-056).
- Scheduled delay queue with timestamp polling (NTF-057).
- Dispatcher worker execution loop (NTF-060).
- Token-bucket rate limiter per provider/tenant (NTF-062).
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
import time
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.store import (
    NotificationStoreManager, QueueStateRecord, ScheduledJobRecord,
    NotificationRecord, NotificationStatus
)
from channels.providers import ProviderRegistry, ProviderResult


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter enforcing requests-per-second constraints (NTF-062).
    """
    def __init__(self):
        # Maps key -> (tokens, last_refill_timestamp)
        self._buckets: Dict[str, Tuple[float, float]] = {}

    def allow(self, key: str, rate_rps: float, capacity: Optional[float] = None) -> bool:
        cap = capacity if capacity is not None else rate_rps
        now = time.monotonic()

        tokens, last_refill = self._buckets.get(key, (cap, now))
        elapsed = now - last_refill

        # Refill tokens based on elapsed time * rate
        tokens = min(cap, tokens + (elapsed * rate_rps))

        if tokens >= 1.0:
            tokens -= 1.0
            self._buckets[key] = (tokens, now)
            return True
        else:
            self._buckets[key] = (tokens, now)
            return False


class PriorityQueueManager:
    """
    Priority queue with lease-based concurrency locking (NTF-056).
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.store = NotificationStoreManager(session)

    async def enqueue(
        self,
        item_id: str,
        queue_name: str,
        payload: Dict[str, Any],
        priority: int = 10
    ):
        return await self.store.enqueue_item(
            item_id=item_id,
            queue_name=queue_name,
            payload=payload,
            priority=priority
        )

    async def dequeue(
        self,
        queue_name: str,
        lock_token: str,
        lease_seconds: int = 30,
        starvation_threshold_seconds: Optional[int] = None
    ):
        return await self.store.dequeue_item(
            queue_name=queue_name,
            lock_token=lock_token,
            lease_seconds=lease_seconds,
            starvation_threshold_seconds=starvation_threshold_seconds
        )

    async def acknowledge(self, item_id: str):
        stmt = select(QueueStateRecord).where(QueueStateRecord.item_id == item_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if rec:
            await self.session.delete(rec)
            await self.session.commit()


class ScheduledQueueManager:
    """
    Future scheduling queue (NTF-057).
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.store = NotificationStoreManager(session)

    async def schedule(self, job_id: str, notification_id: str, tenant_id: str, run_at: datetime):
        return await self.store.schedule_job(
            job_id=job_id,
            notification_id=notification_id,
            tenant_id=tenant_id,
            run_at=run_at
        )

    async def poll_due_jobs(self, current_time: Optional[datetime] = None) -> List[str]:
        now = current_time or datetime.now(timezone.utc)
        due_jobs = await self.store.get_due_jobs(now)
        due_notif_ids = []
        for job in due_jobs:
            stmt = select(ScheduledJobRecord).where(ScheduledJobRecord.job_id == job.job_id)
            res = await self.session.execute(stmt)
            rec = res.scalar_one_or_none()
            if rec:
                rec.status = "EXECUTED"
            due_notif_ids.append(job.notification_id)
        await self.session.commit()
        return due_notif_ids


class DispatcherWorker:
    """
    Worker pulling queued notifications, enforcing rate limits, and dispatching to providers (NTF-060, NTF-062).
    """
    def __init__(
        self,
        session: AsyncSession,
        provider_registry: ProviderRegistry,
        rate_limiter: Optional[TokenBucketRateLimiter] = None
    ):
        self.session = session
        self.registry = provider_registry
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self.store = NotificationStoreManager(session)
        self.queue_mgr = PriorityQueueManager(session)

    async def process_next(
        self,
        queue_name: str,
        worker_id: str,
        rate_limit_rps: float = 100.0
    ) -> Optional[Dict[str, Any]]:
        # 1. Dequeue top priority item
        item = await self.queue_mgr.dequeue(queue_name, lock_token=worker_id)
        if not item:
            return None

        notif_id = item.payload.get("notification_id")
        notif = await self.store.get_notification(notif_id)
        if not notif:
            await self.queue_mgr.acknowledge(item.item_id)
            return None

        # 2. Check Rate Limit
        rl_key = f"{notif.tenant_id}:{notif.channel}"
        if not self.rate_limiter.allow(rl_key, rate_rps=rate_limit_rps):
            # Requeue / return without acknowledge (let lease expire or handle backoff)
            return {"status": "RATE_LIMITED", "notification_id": notif_id}

        # 3. Transition to DISPATCHING
        notif_rec_stmt = select(NotificationRecord).where(NotificationRecord.id == notif_id)
        n_res = await self.session.execute(notif_rec_stmt)
        n_rec = n_res.scalar_one_or_none()
        if n_rec:
            n_rec.status = NotificationStatus.DISPATCHING.value
            await self.session.commit()

        # 4. Resolve Provider and Send
        provider = self.registry.get_provider(notif.channel)
        if not provider:
            if n_rec:
                n_rec.status = NotificationStatus.FAILED.value
                await self.session.commit()
            await self.queue_mgr.acknowledge(item.item_id)
            return {"status": "FAILED", "reason": "No provider configured"}

        recipient = notif.metadata.get("recipient", "user@default.internal")
        send_res = await provider.send(
            recipient=recipient,
            body=notif.body,
            subject=notif.subject,
            metadata=notif.metadata
        )

        # 5. Record Delivery Attempt & Update Notification State
        await self.store.record_delivery_attempt(
            attempt_id=f"att_{item.item_id}",
            notification_id=notif_id,
            provider_id=provider.provider_id,
            status="SUCCESS" if send_res.success else "FAILED",
            error_code=send_res.error_code,
            error_message=send_res.error_message,
            latency_ms=send_res.latency_ms
        )

        if n_rec:
            now = datetime.now(timezone.utc)
            if send_res.success:
                n_rec.status = NotificationStatus.DELIVERED.value
                n_rec.delivered_at = now
            else:
                n_rec.status = NotificationStatus.FAILED.value
            await self.session.commit()

        # 6. Acknowledge completed item
        await self.queue_mgr.acknowledge(item.item_id)

        return {
            "status": "DELIVERED" if send_res.success else "FAILED",
            "notification_id": notif_id,
            "provider_id": provider.provider_id,
            "latency_ms": send_res.latency_ms
        }
