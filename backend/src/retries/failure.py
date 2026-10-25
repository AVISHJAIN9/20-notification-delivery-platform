"""
Retries, Failure Handling, and Provider Fallback (NTF-070, NTF-071, NTF-073, NTF-076).
Provides:
- Failure classification into TRANSIENT (retryable) vs PERMANENT (non-retryable) (NTF-073).
- Exponential backoff delay calculation with jitter bounds (NTF-070).
- Dead-letter queue (DLQ) routing for exhausted notifications (NTF-071).
- Multi-provider fallback cascade upon channel provider errors (NTF-076).
"""

from typing import Dict, Any, Optional, List, Tuple, Callable, Awaitable
from datetime import datetime, timezone
from enum import Enum
import math
import random
import uuid
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, String, Integer, DateTime, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import Base
from channels.providers import BaseProvider, ProviderResult
from models.store import NotificationRecord, NotificationStatus, NotificationStoreManager


class ErrorCategory(str, Enum):
    TRANSIENT = "TRANSIENT"      # Rate limits, timeouts, server 5xx (Retryable)
    PERMANENT = "PERMANENT"      # Invalid recipient, auth failure, bad payload (Non-retryable)


class FailureClassifier:
    """
    Classifies error codes and HTTP statuses (NTF-073).
    """
    PERMANENT_CODES = {
        "INVALID_RECIPIENT", "INVALID_PHONE_NUMBER", "INVALID_URL",
        "UNAUTHORIZED", "BAD_REQUEST", "FORBIDDEN", "NOT_FOUND"
    }

    TRANSIENT_CODES = {
        "RATE_LIMITED", "TIMEOUT", "CONNECTION_RESET", "SERVICE_UNAVAILABLE",
        "GATEWAY_TIMEOUT", "INTERNAL_SERVER_ERROR", "PROVIDER_DOWN"
    }

    @classmethod
    def classify(cls, error_code_or_status: Any) -> ErrorCategory:
        code_str = str(error_code_or_status).upper()
        if code_str in cls.PERMANENT_CODES:
            return ErrorCategory.PERMANENT
        if code_str in cls.TRANSIENT_CODES:
            return ErrorCategory.TRANSIENT

        # Check numeric HTTP status
        try:
            status_code = int(error_code_or_status)
            if status_code in (400, 401, 403, 404, 422):
                return ErrorCategory.PERMANENT
            if status_code in (429, 500, 502, 503, 504):
                return ErrorCategory.TRANSIENT
        except ValueError:
            pass

        return ErrorCategory.TRANSIENT  # Default to transient for safety

    @classmethod
    def is_retryable(cls, error_code_or_status: Any) -> bool:
        return cls.classify(error_code_or_status) == ErrorCategory.TRANSIENT

    @classmethod
    def parse_retry_after(cls, headers: Optional[Dict[str, str]]) -> Optional[float]:
        """
        Parses Retry-After header if present, returning seconds to back off (NTF-078).
        """
        if not headers:
            return None
        retry_val = None
        for k, v in headers.items():
            if k.lower() == "retry-after":
                retry_val = v
                break
        if not retry_val:
            return None
        try:
            return float(retry_val)
        except ValueError:
            pass
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(retry_val)
            delta = (dt - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, float(delta))
        except Exception:
            return None


class RetryPolicy:
    """
    Exponential backoff retry policy (NTF-070).
    """
    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
        factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.factor = factor

    def calculate_backoff(self, attempt: int, jitter: bool = False) -> float:
        """
        Calculates delay: min(max_delay, base_delay * factor^(attempt - 1)) + optional jitter.
        """
        if attempt <= 0:
            return 0.0
        exponent = max(0, attempt - 1)
        delay = self.base_delay * math.pow(self.factor, exponent)
        delay = min(self.max_delay, delay)
        if jitter:
            delay += random.uniform(0, delay * 0.1)
        return round(delay, 2)

    def should_retry(self, attempt: int, error_code: Any) -> bool:
        if attempt >= self.max_retries:
            return False
        return FailureClassifier.is_retryable(error_code)


class DeadLetterRecord(Base):
    __tablename__ = "dead_letter_queue"
    __table_args__ = {"extend_existing": True}

    id = Column(String(64), primary_key=True, index=True)
    notification_id = Column(String(64), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    failure_reason = Column(Text, nullable=False)
    attempt_count = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DeadLetterSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notification_id: str
    tenant_id: str
    failure_reason: str
    attempt_count: int
    created_at: datetime


class DeadLetterQueueManager:
    """
    Dead-letter queue (DLQ) for notifications that exceed retry caps (NTF-071).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_to_dlq(
        self,
        notification_id: str,
        tenant_id: str,
        failure_reason: str,
        attempt_count: int
    ) -> DeadLetterSchema:
        rec = DeadLetterRecord(
            id=f"dlq_{notification_id}",
            notification_id=notification_id,
            tenant_id=tenant_id,
            failure_reason=failure_reason,
            attempt_count=attempt_count,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return DeadLetterSchema.model_validate(rec)

    async def list_dlq(self, tenant_id: str) -> List[DeadLetterSchema]:
        stmt = select(DeadLetterRecord).where(DeadLetterRecord.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        return [DeadLetterSchema.model_validate(r) for r in res.scalars().all()]

    async def reprocess_dead_letter(
        self,
        tenant_id: str,
        dlq_id: str,
        actor: str
    ) -> Any:
        stmt = select(DeadLetterRecord).where(
            DeadLetterRecord.id == dlq_id,
            DeadLetterRecord.tenant_id == tenant_id
        )
        res = await self.session.execute(stmt)
        dlq_rec = res.scalar_one_or_none()
        if not dlq_rec:
            raise ValueError(f"DLQ entry '{dlq_id}' not found for tenant '{tenant_id}'")

        notif_stmt = select(NotificationRecord).where(
            NotificationRecord.id == dlq_rec.notification_id,
            NotificationRecord.tenant_id == tenant_id
        )
        notif_res = await self.session.execute(notif_stmt)
        notif = notif_res.scalar_one_or_none()
        if not notif:
            raise ValueError(f"Notification '{dlq_rec.notification_id}' not found")

        if notif.status == NotificationStatus.DELIVERED.value:
            raise ValueError("Cannot reprocess already DELIVERED notification")

        # 1. Record new delivery attempt
        store = NotificationStoreManager(self.session)
        att_id = f"att_REPROCESS_{uuid.uuid4().hex[:12]}"
        await store.record_delivery_attempt(
            attempt_id=att_id,
            notification_id=notif.id,
            provider_id="system-dlq-reprocess",
            status="REPROCESS_PENDING"
        )

        # 2. Write audit log
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        await store.record_audit_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action="DLQ_REPROCESSED",
            resource_type="dead_letter",
            resource_id=dlq_id,
            details={"notification_id": notif.id}
        )

        # 3. Transition notification back to QUEUED
        notif.status = NotificationStatus.QUEUED.value

        # 4. Remove from DLQ
        await self.session.delete(dlq_rec)
        await self.session.commit()

        return await store.get_notification(notif.id)

    async def manual_retry(
        self,
        tenant_id: str,
        notification_id: str,
        actor: str
    ) -> Any:
        notif_stmt = select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.tenant_id == tenant_id
        )
        notif_res = await self.session.execute(notif_stmt)
        notif = notif_res.scalar_one_or_none()
        if not notif:
            raise ValueError(f"Notification '{notification_id}' not found for tenant '{tenant_id}'")

        if notif.status == NotificationStatus.DELIVERED.value:
            raise ValueError("Cannot retry already DELIVERED notification")

        store = NotificationStoreManager(self.session)
        att_id = f"att_MANUAL_RETRY_{uuid.uuid4().hex[:12]}"
        await store.record_delivery_attempt(
            attempt_id=att_id,
            notification_id=notif.id,
            provider_id="manual-retry-handler",
            status="MANUAL_RETRY_PENDING"
        )

        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        await store.record_audit_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action="MANUAL_RETRY",
            resource_type="notification",
            resource_id=notification_id,
            details={"previous_status": notif.status}
        )

        notif.status = NotificationStatus.QUEUED.value
        await self.session.commit()

        return await store.get_notification(notif.id)

    async def replay_notification(
        self,
        tenant_id: str,
        notification_id: str,
        actor: str
    ) -> Any:
        notif_stmt = select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.tenant_id == tenant_id
        )
        notif_res = await self.session.execute(notif_stmt)
        notif = notif_res.scalar_one_or_none()
        if not notif:
            raise ValueError(f"Notification '{notification_id}' not found for tenant '{tenant_id}'")

        if notif.status == NotificationStatus.DELIVERED.value:
            raise ValueError("Cannot replay already DELIVERED notification")

        store = NotificationStoreManager(self.session)
        att_id = f"att_REPLAY_{uuid.uuid4().hex[:12]}"
        await store.record_delivery_attempt(
            attempt_id=att_id,
            notification_id=notif.id,
            provider_id="replay-handler",
            status="REPLAY_PENDING"
        )

        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        await store.record_audit_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action="NOTIFICATION_REPLAYED",
            resource_type="notification",
            resource_id=notification_id,
            details={"previous_status": notif.status}
        )

        notif.status = NotificationStatus.QUEUED.value
        await self.session.commit()

        return await store.get_notification(notif.id)


class ProviderFallbackRouter:
    """
    Cascades through prioritized providers on channel failure (NTF-076).
    """
    @staticmethod
    async def dispatch_with_fallback(
        providers: List[BaseProvider],
        recipient: str,
        body: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[ProviderResult, List[Dict[str, Any]]]:
        if not providers:
            raise ValueError("No providers provided for fallback router")

        attempts_log = []
        last_result: Optional[ProviderResult] = None

        for provider in providers:
            result = await provider.send(
                recipient=recipient,
                body=body,
                subject=subject,
                metadata=metadata
            )
            attempts_log.append({
                "provider_id": provider.provider_id,
                "success": result.success,
                "error_code": result.error_code,
                "latency_ms": result.latency_ms
            })
            last_result = result
            if result.success:
                return result, attempts_log

            # Check if permanent error (e.g. invalid recipient affects all providers)
            if not FailureClassifier.is_retryable(result.error_code):
                return result, attempts_log

        return last_result, attempts_log
