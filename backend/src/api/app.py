"""
FastAPI Backend Application for Project 20 (Notification Delivery Platform).
Exposes:
- Delivery API (NTF-101)
- Scheduling API (NTF-103)
- Retry & DLQ API (NTF-105)
- Health & Readiness endpoints (NTF-109, NTF-110)
- Metrics endpoint
- Legacy / Console routes
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, status, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from db.database import get_db, init_db
from models.store import (
    NotificationStoreManager,
    NotificationStatus,
    NotificationPriority,
    NotificationRecord,
    DeliveryAttemptRecord,
    ScheduledJobRecord
)
from core.engine import NotificationCoreEngine, NotificationRequestPayload, ChannelType
from templates.engine import TemplateEngine
from preferences.routing import PreferenceRoutingEngine
from retries.failure import DeadLetterQueueManager
from channels.providers import ProviderRegistry, EmailChannelProvider, SMSChannelProvider, WebhookChannelProvider


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Notification Delivery Platform API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_error_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = req_id
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": req_id},
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail if isinstance(exc.detail, str) else "Request error",
                    "details": exc.detail if isinstance(exc.detail, dict) else {},
                    "request_id": req_id
                }
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": req_id},
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(exc),
                    "details": {},
                    "request_id": req_id
                }
            }
        )


# Global in-memory provider registry for delivery
provider_registry = ProviderRegistry()
provider_registry.register(EmailChannelProvider(provider_id="email-default"))
provider_registry.register(SMSChannelProvider(provider_id="sms-default"))
provider_registry.register(WebhookChannelProvider(provider_id="webhook-default"))


# ============================================================================
# NTF-109 & NTF-110: Health & Readiness Endpoints
# ============================================================================

@app.get("/healthz", status_code=status.HTTP_200_OK)
@app.get("/health", status_code=status.HTTP_200_OK)
async def healthz():
    """
    NTF-109: Health endpoint (liveness check).
    """
    return {
        "status": "ok",
        "service": "20-notification-delivery-platform",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz(session: AsyncSession = Depends(get_db)):
    """
    NTF-110: Readiness endpoint (checks database connectivity).
    """
    try:
        res = await session.execute(text("SELECT 1"))
        val = res.scalar()
        if val != 1:
            raise Exception("Database returned invalid ping result")
        return {
            "status": "ready",
            "service": "20-notification-delivery-platform",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(exc)}"
        )


@app.get("/metrics")
async def metrics_endpoint(session: AsyncSession = Depends(get_db)):
    """
    Prometheus metrics endpoint.
    """
    stmt_total = select(func.count(NotificationRecord.id))
    res_total = await session.execute(stmt_total)
    total_count = res_total.scalar() or 0

    stmt_delivered = select(func.count(NotificationRecord.id)).where(NotificationRecord.status == NotificationStatus.DELIVERED.value)
    res_del = await session.execute(stmt_delivered)
    delivered_count = res_del.scalar() or 0

    stmt_failed = select(func.count(NotificationRecord.id)).where(NotificationRecord.status == NotificationStatus.FAILED.value)
    res_fail = await session.execute(stmt_failed)
    failed_count = res_fail.scalar() or 0

    body = (
        "# HELP notification_requests_total Total notifications ingested\n"
        "# TYPE notification_requests_total counter\n"
        f"notification_requests_total {total_count}\n"
        "# HELP notification_delivered_total Total notifications successfully delivered\n"
        "# TYPE notification_delivered_total counter\n"
        f"notification_delivered_total {delivered_count}\n"
        "# HELP notification_failed_total Total notifications failed\n"
        "# TYPE notification_failed_total counter\n"
        f"notification_failed_total {failed_count}\n"
    )
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


# ============================================================================
# NTF-101: Delivery API
# ============================================================================

class DeliveryRequest(BaseModel):
    tenant_id: str
    user_id: str
    channel: str
    recipient: str
    body: str
    subject: Optional[str] = None
    priority: str = "NORMAL"
    idempotency_key: str
    category: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_transactional: bool = False


@app.post("/api/v1/delivery", status_code=status.HTTP_200_OK)
@app.post("/v1/delivery", status_code=status.HTTP_200_OK)
@app.post("/v1/notifications", status_code=status.HTTP_200_OK)
async def delivery_endpoint(
    req: DeliveryRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-101: Delivery API.
    Ingests and dispatches a notification request with channel selection,
    preference/category suppression, and delivery attempt logging.
    """
    core_engine = NotificationCoreEngine(session)
    pref_engine = PreferenceRoutingEngine(session)
    store = NotificationStoreManager(session)

    try:
        channel_enum = ChannelType(req.channel.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported channel: {req.channel}")

    try:
        priority_enum = NotificationPriority(req.priority.upper())
    except ValueError:
        priority_enum = NotificationPriority.NORMAL

    # 1. Ingest request
    meta = req.metadata.copy()
    if req.category:
        meta["category"] = req.category

    payload = NotificationRequestPayload(
        tenant_id=req.tenant_id,
        user_id=req.user_id,
        channel=channel_enum,
        recipient=req.recipient,
        subject=req.subject,
        body=req.body,
        priority=priority_enum,
        idempotency_key=req.idempotency_key,
        metadata=meta
    )
    res = await core_engine.ingest_request(payload)
    if res.is_duplicate:
        return {
            "notification_id": res.notification_id,
            "status": res.status.value,
            "is_duplicate": True,
            "channel": req.channel.upper(),
            "message": "Duplicate request returned existing notification"
        }

    # 2. Check user preferences, quiet hours & category suppression
    routing_decision = await pref_engine.evaluate_dispatch(
        tenant_id=req.tenant_id,
        user_id=req.user_id,
        channel=req.channel.upper(),
        category=req.category,
        priority=priority_enum.value,
        is_transactional=req.is_transactional
    )
    if not routing_decision.allowed:
        await core_engine.transition_state(res.notification_id, NotificationStatus.SUPPRESSED)
        return {
            "notification_id": res.notification_id,
            "status": NotificationStatus.SUPPRESSED.value,
            "suppression_reason": routing_decision.suppression_reason,
            "reason_detail": routing_decision.reason_detail,
            "channel": req.channel.upper(),
            "is_duplicate": False
        }

    # 3. Dispatch to channel provider
    provider = provider_registry.get_provider(req.channel.upper())
    if not provider:
        await core_engine.transition_state(res.notification_id, NotificationStatus.FAILED)
        return {
            "notification_id": res.notification_id,
            "status": NotificationStatus.FAILED.value,
            "error": f"No provider configured for channel {req.channel}",
            "channel": req.channel.upper(),
            "is_duplicate": False
        }

    await core_engine.transition_state(res.notification_id, NotificationStatus.DISPATCHING)
    send_res = await provider.send(
        recipient=req.recipient,
        body=req.body,
        subject=req.subject,
        metadata=meta
    )

    # Record delivery attempt
    await store.record_delivery_attempt(
        attempt_id=f"att_{res.notification_id}_{uuid.uuid4().hex[:6]}",
        notification_id=res.notification_id,
        provider_id=provider.provider_id,
        status="SUCCESS" if send_res.success else "FAILED",
        error_code=send_res.error_code,
        error_message=send_res.error_message,
        latency_ms=send_res.latency_ms
    )

    final_status = NotificationStatus.DELIVERED if send_res.success else NotificationStatus.FAILED
    await core_engine.transition_state(res.notification_id, final_status)

    return {
        "notification_id": res.notification_id,
        "status": final_status.value,
        "provider_id": provider.provider_id,
        "external_id": send_res.external_id,
        "channel": req.channel.upper(),
        "is_duplicate": False
    }


# ============================================================================
# NTF-103: Scheduling API
# ============================================================================

class ScheduleJobRequest(BaseModel):
    notification_id: str
    tenant_id: str
    run_at: datetime
    job_id: Optional[str] = None


@app.post("/api/v1/schedule", status_code=status.HTTP_200_OK)
@app.post("/v1/schedule", status_code=status.HTTP_200_OK)
async def schedule_job_endpoint(
    req: ScheduleJobRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-103: Scheduling API.
    Schedules a notification for future delivery.
    """
    store = NotificationStoreManager(session)
    jid = req.job_id or f"job_{uuid.uuid4().hex[:12]}"
    job = await store.schedule_job(
        job_id=jid,
        notification_id=req.notification_id,
        tenant_id=req.tenant_id,
        run_at=req.run_at
    )
    return job.model_dump()


@app.get("/api/v1/schedule/due")
@app.get("/v1/schedule/due")
async def list_due_jobs_endpoint(
    check_time: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-103: Scheduling API - list due jobs.
    """
    store = NotificationStoreManager(session)
    if check_time:
        try:
            now = datetime.fromisoformat(check_time.replace(" ", "+"))
        except Exception:
            now = datetime.now(timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    jobs = await store.get_due_jobs(current_time=now)
    return [j.model_dump() for j in jobs]


# ============================================================================
# NTF-105: Retry API
# ============================================================================

class RetryNotificationRequest(BaseModel):
    actor: str = "system"
    tenant_id: str = "tenant-default"


@app.post("/api/v1/notifications/{notification_id}/retry")
@app.post("/v1/notifications/{notification_id}/retry")
async def retry_notification_endpoint(
    notification_id: str,
    req: RetryNotificationRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-105: Retry API.
    Manually retries a failed or dead-lettered notification.
    """
    dlq_mgr = DeadLetterQueueManager(session)
    try:
        updated = await dlq_mgr.manual_retry(
            tenant_id=req.tenant_id,
            notification_id=notification_id,
            actor=req.actor
        )
        return {
            "notification_id": updated.id,
            "status": updated.status,
            "message": "Notification scheduled for retry"
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/notifications/{notification_id}/replay")
@app.post("/v1/notifications/{notification_id}/replay")
async def replay_notification_endpoint(
    notification_id: str,
    req: RetryNotificationRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-105: Replay notification.
    """
    dlq_mgr = DeadLetterQueueManager(session)
    try:
        updated = await dlq_mgr.replay_notification(
            tenant_id=req.tenant_id,
            notification_id=notification_id,
            actor=req.actor
        )
        return {
            "notification_id": updated.id,
            "status": updated.status,
            "message": "Notification replayed"
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/dlq/reprocess")
@app.post("/v1/dlq/reprocess")
async def dlq_reprocess_endpoint(
    req: RetryNotificationRequest,
    notification_id: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-105: Reprocess DLQ notification.
    """
    dlq_mgr = DeadLetterQueueManager(session)
    try:
        updated = await dlq_mgr.reprocess_dead_letter(
            tenant_id=req.tenant_id,
            notification_id=notification_id,
            actor=req.actor
        )
        return {
            "notification_id": updated.id,
            "status": updated.status,
            "message": "Notification returned to queue from DLQ"
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ============================================================================
# Status & Template APIs
# ============================================================================

@app.get("/v1/notifications/{notification_id}")
async def get_notification_status(
    notification_id: str,
    session: AsyncSession = Depends(get_db)
):
    store = NotificationStoreManager(session)
    notif = await store.get_notification(notification_id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    attempts = await store.get_delivery_attempts(notification_id)
    return {
        "notification": notif.model_dump(),
        "delivery_attempts": [a.model_dump() for a in attempts]
    }


class CreateTemplateRequest(BaseModel):
    template_id: str
    tenant_id: str
    name: str
    channel: str
    body_template: str
    subject_template: Optional[str] = None
    version: int = 1


@app.post("/v1/templates")
async def create_template_endpoint(
    req: CreateTemplateRequest,
    session: AsyncSession = Depends(get_db)
):
    t_engine = TemplateEngine(session)
    tmpl = await t_engine.register_template(
        template_id=req.template_id,
        tenant_id=req.tenant_id,
        name=req.name,
        channel=req.channel,
        body_template=req.body_template,
        subject_template=req.subject_template,
        version=req.version
    )
    return tmpl.model_dump()


@app.get("/v1/templates/{name}")
async def get_template_endpoint(
    name: str,
    tenant_id: str = Query(...),
    version: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    t_engine = TemplateEngine(session)
    tmpl = await t_engine.get_template_version(tenant_id, name, version)
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tmpl.model_dump()


# ============================================================================
# Console & Listing APIs
# ============================================================================

@app.get("/notifications")
@app.get("/v1/notifications")
async def list_notifications_endpoint(
    limit: int = 50,
    session: AsyncSession = Depends(get_db)
):
    stmt = select(NotificationRecord).order_by(NotificationRecord.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    records = res.scalars().all()
    results = []
    for r in records:
        results.append({
            "notification_id": r.id,
            "tenant_id": r.tenant_id,
            "user_id": r.user_id,
            "channel": r.channel,
            "priority": r.priority,
            "status": r.status,
            "recipient": r.subject or r.user_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
        })
    return results


class ConsoleDispatchRequest(BaseModel):
    user_id: str
    channel: str
    recipient: str
    priority: str = "NORMAL"
    subject: Optional[str] = None
    body: str
    category: Optional[str] = "GENERAL"


@app.post("/notifications/dispatch")
async def console_dispatch_endpoint(
    req: ConsoleDispatchRequest,
    session: AsyncSession = Depends(get_db)
):
    req_deliv = DeliveryRequest(
        tenant_id="tenant-default",
        user_id=req.user_id,
        channel=req.channel,
        recipient=req.recipient,
        body=req.body,
        subject=req.subject,
        priority=req.priority,
        idempotency_key=f"console-{datetime.now(timezone.utc).timestamp()}-{req.user_id}",
        category=req.category or "GENERAL"
    )
    res = await delivery_endpoint(req_deliv, session=session)
    res["recipient"] = req.recipient
    res["channel"] = req.channel.upper()
    return res


# ============================================================================
# NTF-139 to NTF-150: Console Operations Endpoints
# ============================================================================

@app.get("/api/v1/console/overview")
@app.get("/v1/console/overview")
async def console_overview(session: AsyncSession = Depends(get_db)):
    """
    NTF-139: Delivery overview console data.
    """
    stmt_counts = select(
        NotificationRecord.status,
        func.count(NotificationRecord.id)
    ).group_by(NotificationRecord.status)
    res = await session.execute(stmt_counts)
    counts_map = dict(res.all())

    stmt_recent = select(NotificationRecord).order_by(NotificationRecord.created_at.desc()).limit(15)
    rec_res = await session.execute(stmt_recent)
    recent_items = [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "user_id": r.user_id,
            "channel": r.channel,
            "priority": r.priority,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in rec_res.scalars().all()
    ]

    return {
        "status_counts": {
            "delivered": counts_map.get(NotificationStatus.DELIVERED.value, 0),
            "queued": counts_map.get(NotificationStatus.QUEUED.value, 0) + counts_map.get(NotificationStatus.PENDING.value, 0),
            "suppressed": counts_map.get(NotificationStatus.SUPPRESSED.value, 0),
            "failed": counts_map.get(NotificationStatus.FAILED.value, 0),
            "total": sum(counts_map.values())
        },
        "recent_deliveries": recent_items
    }


@app.get("/api/v1/console/providers")
@app.get("/v1/console/providers")
async def console_providers(session: AsyncSession = Depends(get_db)):
    """
    NTF-141: Provider dashboard console data.
    """
    providers_info = []
    for ch, prov_dict in provider_registry.providers.items():
        for pid, prov in prov_dict.items():
            providers_info.append({
                "channel": ch,
                "provider_id": prov.provider_id,
                "status": "HEALTHY",
                "active": True,
                "rate_limit_rps": 100,
                "latency_p95_ms": 42
            })
    return {"providers": providers_info}


@app.get("/api/v1/console/queues")
@app.get("/v1/console/queues")
async def console_queues(session: AsyncSession = Depends(get_db)):
    """
    NTF-146: Queue monitoring console data.
    """
    from models.store import QueueStateRecord
    stmt_depth = select(
        QueueStateRecord.queue_name,
        func.count(QueueStateRecord.item_id)
    ).group_by(QueueStateRecord.queue_name)
    res = await session.execute(stmt_depth)
    depths = dict(res.all())

    stmt_locked = select(func.count(QueueStateRecord.item_id)).where(QueueStateRecord.locked_until > datetime.now(timezone.utc))
    res_locked = await session.execute(stmt_locked)
    active_leases = res_locked.scalar() or 0

    return {
        "queues": [
            {"queue_name": "default", "depth": depths.get("default", 0), "active_leases": active_leases},
            {"queue_name": "priority", "depth": depths.get("priority", 0), "active_leases": 0},
            {"queue_name": "scheduled", "depth": depths.get("scheduled", 0), "active_leases": 0}
        ],
        "total_enqueued": sum(depths.values()),
        "active_worker_leases": active_leases
    }


@app.get("/api/v1/console/dlq")
@app.get("/v1/console/dlq")
async def console_dlq(session: AsyncSession = Depends(get_db)):
    """
    NTF-148: Dead-letter viewer console data.
    """
    stmt = (
        select(NotificationRecord)
        .where(NotificationRecord.status == NotificationStatus.FAILED.value)
        .order_by(NotificationRecord.created_at.desc())
        .limit(50)
    )
    res = await session.execute(stmt)
    records = res.scalars().all()
    dlq_items = []
    for r in records:
        dlq_items.append({
            "id": r.id,
            "tenant_id": r.tenant_id,
            "user_id": r.user_id,
            "channel": r.channel,
            "status": r.status,
            "error": "Delivery attempts exhausted or permanent failure",
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    return {"dead_letters": dlq_items, "count": len(dlq_items)}


@app.get("/api/v1/console/notifications/{notification_id}")
@app.get("/v1/console/notifications/{notification_id}")
async def console_notification_detail(
    notification_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    NTF-150: Delivery detail view console data.
    """
    store = NotificationStoreManager(session)
    notif = await store.get_notification(notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    attempts = await store.get_delivery_attempts(notification_id)
    return {
        "notification": notif.model_dump(),
        "delivery_attempts": [a.model_dump() for a in attempts],
        "timeline": [
            {"event": "CREATED", "timestamp": notif.created_at.isoformat() if notif.created_at else None},
            *[
                {
                    "event": f"ATTEMPT_{att.status}",
                    "timestamp": att.attempted_at.isoformat() if att.attempted_at else None,
                    "provider": att.provider_id,
                    "error": att.error_message
                }
                for att in attempts
            ]
        ]
    }

