"""
Notification Core Engine (NTF-014, NTF-015, NTF-016, NTF-018, NTF-019, NTF-020, NTF-021).
Provides:
- Ingestion pipeline with schema validation and message normalization.
- Unique notification ID generation.
- Strict request idempotency.
- Finite state machine with validated monotonic transitions.
- Multi-tier priority handling and numerical mapping.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import re
import uuid
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.store import NotificationRecord, NotificationSchema, NotificationStoreManager, NotificationStatus, NotificationPriority


class ChannelType(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    WEBHOOK = "WEBHOOK"
    IN_APP = "IN_APP"


# Priority weight mappings
PRIORITY_WEIGHTS = {
    NotificationPriority.URGENT.value: 100,
    NotificationPriority.HIGH.value: 50,
    NotificationPriority.NORMAL.value: 10,
    NotificationPriority.LOW.value: 0
}

# State machine allowable forward transitions
VALID_TRANSITIONS = {
    NotificationStatus.PENDING.value: [NotificationStatus.QUEUED.value, NotificationStatus.DISPATCHING.value, NotificationStatus.SUPPRESSED.value, NotificationStatus.FAILED.value],
    NotificationStatus.QUEUED.value: [NotificationStatus.DISPATCHING.value, NotificationStatus.FAILED.value, NotificationStatus.SUPPRESSED.value],
    NotificationStatus.DISPATCHING.value: [NotificationStatus.DELIVERED.value, NotificationStatus.FAILED.value, NotificationStatus.QUEUED.value],  # Retry returns to QUEUED
    NotificationStatus.DELIVERED.value: [],  # Terminal state
    NotificationStatus.FAILED.value: [NotificationStatus.QUEUED.value],  # Retry returns to QUEUED
    NotificationStatus.SUPPRESSED.value: []  # Terminal state
}


class NotificationRequestPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    user_id: str
    channel: ChannelType
    recipient: str  # email address, phone number, webhook URL, or device token
    subject: Optional[str] = None
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    idempotency_key: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    scheduled_for: Optional[datetime] = None

    @field_validator("tenant_id", "user_id", "body", "idempotency_key", "recipient")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("recipient")
    @classmethod
    def validate_recipient_format(cls, v: str, info) -> str:
        channel = info.data.get("channel")
        if channel == ChannelType.EMAIL:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                raise ValueError(f"Invalid email address: '{v}'")
            return v.lower().strip()
        elif channel == ChannelType.SMS:
            # Normalize E.164 phone number
            cleaned = re.sub(r"[\s\-\(\)]", "", v)
            if not re.match(r"^\+?[1-9]\d{6,14}$", cleaned):
                raise ValueError(f"Invalid phone number: '{v}'")
            return cleaned
        elif channel == ChannelType.WEBHOOK:
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError(f"Invalid webhook URL: '{v}'")
            return v.strip()
        return v.strip()


class IngestionResult(BaseModel):
    notification_id: str
    status: NotificationStatus
    priority_weight: int
    is_duplicate: bool
    recipient_normalized: str


class NotificationCoreEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.store = NotificationStoreManager(session)

    @staticmethod
    def generate_notification_id() -> str:
        """
        Generates standard notification ID with prefix (NTF-018).
        """
        return f"ntf_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def get_priority_weight(priority: str) -> int:
        """
        Maps priority to numeric weighting (NTF-021).
        """
        return PRIORITY_WEIGHTS.get(priority, 10)

    async def ingest_request(self, payload: NotificationRequestPayload) -> IngestionResult:
        """
        Validates, normalizes, and ingests notification request with idempotency (NTF-014, NTF-015, NTF-016, NTF-019).
        """
        # Idempotency check: see if record already exists
        existing_stmt = select(NotificationRecord).where(
            NotificationRecord.tenant_id == payload.tenant_id,
            NotificationRecord.idempotency_key == payload.idempotency_key
        )
        res = await self.session.execute(existing_stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return IngestionResult(
                notification_id=existing.id,
                status=NotificationStatus(existing.status),
                priority_weight=self.get_priority_weight(existing.priority),
                is_duplicate=True,
                recipient_normalized=payload.recipient
            )

        notif_id = self.generate_notification_id()
        meta = dict(payload.metadata)
        meta["recipient"] = payload.recipient

        created = await self.store.create_notification(
            notification_id=notif_id,
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            channel=payload.channel.value,
            subject=payload.subject,
            body=payload.body,
            idempotency_key=payload.idempotency_key,
            priority=payload.priority.value,
            metadata=meta,
            scheduled_for=payload.scheduled_for
        )

        return IngestionResult(
            notification_id=created.id,
            status=NotificationStatus(created.status),
            priority_weight=self.get_priority_weight(created.priority),
            is_duplicate=False,
            recipient_normalized=payload.recipient
        )

    async def transition_state(self, notification_id: str, new_status: NotificationStatus) -> NotificationSchema:
        """
        Executes strict monotonic state machine transition (NTF-020).
        """
        stmt = select(NotificationRecord).where(NotificationRecord.id == notification_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Notification {notification_id} not found")

        current_st = rec.status
        allowed = VALID_TRANSITIONS.get(current_st, [])
        if new_status.value not in allowed:
            raise ValueError(
                f"Invalid state transition: cannot move from {current_st} to {new_status.value}. Allowed: {allowed}"
            )

        rec.status = new_status.value
        now = datetime.now(timezone.utc)
        if new_status == NotificationStatus.DELIVERED:
            rec.delivered_at = now

        await self.session.commit()
        return await self.store.get_notification(notification_id)
