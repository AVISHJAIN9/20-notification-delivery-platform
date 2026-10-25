"""
Database Stores and Schemas for Notification Delivery Platform (NTF-001 to NTF-007).
Provides:
- Notification Store (NTF-001)
- Template Store (NTF-002)
- User Preference Store (NTF-003)
- Delivery Attempt Store (NTF-004)
- Provider Configuration Store (NTF-005)
- Scheduled-Job Store (NTF-006)
- Queue State Store (NTF-007)
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import asyncio
import json
import uuid
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text, select, update, Index
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import Base


def _normalize_tz(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


# ----------------------------------------------------------------------------
# NTF-001: Notification Store
# ----------------------------------------------------------------------------

class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


class NotificationPriority(str, Enum):
    URGENT = "URGENT"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class NotificationRecord(Base):
    __tablename__ = "notifications"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    channel = Column(String(32), nullable=False, index=True)  # EMAIL, SMS, PUSH, WEBHOOK, IN_APP
    priority = Column(String(16), default=NotificationPriority.NORMAL.value, nullable=False)
    status = Column(String(32), default=NotificationStatus.PENDING.value, nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    subject = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_ntf_tenant_idem", "tenant_id", "idempotency_key", unique=True),
        Index("ix_ntf_tenant_user", "tenant_id", "user_id"),
    )


class NotificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    user_id: str
    channel: str
    priority: str = NotificationPriority.NORMAL.value
    status: str = NotificationStatus.PENDING.value
    idempotency_key: str
    subject: Optional[str] = None
    body: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    scheduled_for: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("scheduled_for", "delivered_at", "created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-002: Template Store
# ----------------------------------------------------------------------------

class TemplateRecord(Base):
    __tablename__ = "templates"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False, index=True)
    channel = Column(String(32), nullable=False)
    subject_template = Column(String(256), nullable=True)
    body_template = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    language = Column(String(16), default="en", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), default="DRAFT", nullable=False)
    approved_by = Column(String(64), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by = Column(String(64), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_tmpl_tenant_name_chan_lang_ver", "tenant_id", "name", "channel", "language", "version", unique=True),
    )


class TemplateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    channel: str
    language: str = "en"
    subject_template: Optional[str] = None
    body_template: str
    version: int = 1
    is_active: bool = True
    status: str = "DRAFT"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    deactivated_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("created_at", "approved_at", "deactivated_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-003: User Preference Store
# ----------------------------------------------------------------------------

class UserPreferenceRecord(Base):
    __tablename__ = "user_preferences"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    channel_opt_in_json = Column(Text, default="{}", nullable=False)  # {"EMAIL": true, "SMS": false}
    categories_opt_in_json = Column(Text, default="{}", nullable=False)  # {"marketing": false, "security": true}
    opt_out_all = Column(Boolean, default=False, nullable=False)
    quiet_hours_start = Column(String(5), nullable=True)  # e.g. "22:00"
    quiet_hours_end = Column(String(5), nullable=True)    # e.g. "08:00"
    timezone = Column(String(64), default="UTC", nullable=False)  # e.g. "America/New_York"
    preferred_channel = Column(String(32), nullable=True)  # e.g. "SMS", "EMAIL"
    max_daily_limit = Column(Integer, default=50, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_pref_tenant_user", "tenant_id", "user_id", unique=True),
    )


class UserPreferenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    user_id: str
    channel_opt_in: Dict[str, bool] = Field(default_factory=dict)
    categories_opt_in: Dict[str, bool] = Field(default_factory=dict)
    opt_out_all: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: str = "UTC"
    preferred_channel: Optional[str] = None
    max_daily_limit: int = 50
    updated_at: datetime

    @field_validator("updated_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-004: Delivery Attempt Store
# ----------------------------------------------------------------------------

class DeliveryAttemptRecord(Base):
    __tablename__ = "delivery_attempts"

    id = Column(String(64), primary_key=True, index=True)
    notification_id = Column(String(64), ForeignKey("notifications.id"), nullable=False, index=True)
    provider_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)  # SUCCESS, FAILED
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, default=0, nullable=False)
    attempted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DeliveryAttemptSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notification_id: str
    provider_id: str
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: int = 0
    attempted_at: datetime

    @field_validator("attempted_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-005: Provider Configuration Store
# ----------------------------------------------------------------------------

class ProviderConfigRecord(Base):
    __tablename__ = "provider_configs"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    channel = Column(String(32), nullable=False, index=True)
    provider_name = Column(String(64), nullable=False)
    credentials_json = Column(Text, default="{}", nullable=False)
    priority = Column(Integer, default=1, nullable=False)
    rate_limit_rps = Column(Integer, default=100, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ProviderConfigSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    channel: str
    provider_name: str
    credentials: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 1
    rate_limit_rps: int = 100
    is_active: bool = True
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-006: Scheduled-Job Store
# ----------------------------------------------------------------------------

class ScheduledJobRecord(Base):
    __tablename__ = "scheduled_jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    notification_id = Column(String(64), ForeignKey("notifications.id"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    run_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, EXECUTED, CANCELLED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ScheduledJobSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    notification_id: str
    tenant_id: str
    run_at: datetime
    status: str = "PENDING"
    created_at: datetime

    @field_validator("run_at", "created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-007: Queue State Store
# ----------------------------------------------------------------------------

class QueueStateRecord(Base):
    __tablename__ = "queue_state"

    item_id = Column(String(64), primary_key=True, index=True)
    queue_name = Column(String(64), nullable=False, index=True)
    priority = Column(Integer, default=0, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    lock_token = Column(String(64), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True, index=True)
    enqueued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class QueueStateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    queue_name: str
    priority: int = 0
    payload: Dict[str, Any] = Field(default_factory=dict)
    lock_token: Optional[str] = None
    locked_until: Optional[datetime] = None
    enqueued_at: datetime

    @field_validator("locked_until", "enqueued_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-008: Audit Store
# ----------------------------------------------------------------------------

class AuditRecord(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    actor = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    resource_id = Column(String(64), nullable=False, index=True)
    details_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_tenant_res", "tenant_id", "resource_type", "resource_id"),
        Index("ix_audit_tenant_time", "tenant_id", "created_at"),
    )


class AuditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    actor: str
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# NTF-125: API Key Store
# ----------------------------------------------------------------------------

class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    hashed_key = Column(String(128), nullable=False, index=True)
    role = Column(String(32), default="OPERATOR", nullable=False)
    name = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_apikey_tenant_hash", "tenant_id", "hashed_key"),
    )


class ApiKeySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    hashed_key: str
    role: str
    name: str
    is_active: bool
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


# ----------------------------------------------------------------------------
# Store Manager Implementations
# ----------------------------------------------------------------------------

class NotificationStoreManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    # NTF-001: Notifications
    async def create_notification(
        self,
        notification_id: str,
        tenant_id: str,
        user_id: str,
        channel: str,
        body: str,
        idempotency_key: str,
        priority: str = NotificationPriority.NORMAL.value,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None
    ) -> NotificationSchema:
        # Check idempotency
        stmt = select(NotificationRecord).where(
            NotificationRecord.tenant_id == tenant_id,
            NotificationRecord.idempotency_key == idempotency_key
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            meta = json.loads(existing.metadata_json or "{}")
            return NotificationSchema(
                id=existing.id,
                tenant_id=existing.tenant_id,
                user_id=existing.user_id,
                channel=existing.channel,
                priority=existing.priority,
                status=existing.status,
                idempotency_key=existing.idempotency_key,
                subject=existing.subject,
                body=existing.body,
                metadata=meta,
                scheduled_for=existing.scheduled_for,
                delivered_at=existing.delivered_at,
                created_at=existing.created_at
            )

        now = datetime.now(timezone.utc)
        rec = NotificationRecord(
            id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            priority=priority,
            status=NotificationStatus.PENDING.value,
            idempotency_key=idempotency_key,
            subject=subject,
            body=body,
            metadata_json=json.dumps(metadata or {}),
            scheduled_for=scheduled_for,
            created_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return NotificationSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            user_id=rec.user_id,
            channel=rec.channel,
            priority=rec.priority,
            status=rec.status,
            idempotency_key=rec.idempotency_key,
            subject=rec.subject,
            body=rec.body,
            metadata=metadata or {},
            scheduled_for=rec.scheduled_for,
            delivered_at=rec.delivered_at,
            created_at=rec.created_at
        )

    async def get_notification(self, notification_id: str) -> Optional[NotificationSchema]:
        stmt = select(NotificationRecord).where(NotificationRecord.id == notification_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return NotificationSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            user_id=rec.user_id,
            channel=rec.channel,
            priority=rec.priority,
            status=rec.status,
            idempotency_key=rec.idempotency_key,
            subject=rec.subject,
            body=rec.body,
            metadata=json.loads(rec.metadata_json or "{}"),
            scheduled_for=rec.scheduled_for,
            delivered_at=rec.delivered_at,
            created_at=rec.created_at
        )

    async def get_notification_scoped(self, tenant_id: str, notification_id: str) -> Optional[NotificationSchema]:
        stmt = select(NotificationRecord).where(
            NotificationRecord.id == notification_id,
            NotificationRecord.tenant_id == tenant_id
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return NotificationSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            user_id=rec.user_id,
            channel=rec.channel,
            priority=rec.priority,
            status=rec.status,
            idempotency_key=rec.idempotency_key,
            subject=rec.subject,
            body=rec.body,
            metadata=json.loads(rec.metadata_json or "{}"),
            scheduled_for=rec.scheduled_for,
            delivered_at=rec.delivered_at,
            created_at=rec.created_at
        )

    async def list_notifications_by_tenant(self, tenant_id: str, limit: int = 50, offset: int = 0) -> List[NotificationSchema]:
        stmt = select(NotificationRecord).where(
            NotificationRecord.tenant_id == tenant_id
        ).order_by(NotificationRecord.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return [
            NotificationSchema(
                id=r.id,
                tenant_id=r.tenant_id,
                user_id=r.user_id,
                channel=r.channel,
                priority=r.priority,
                status=r.status,
                idempotency_key=r.idempotency_key,
                subject=r.subject,
                body=r.body,
                metadata=json.loads(r.metadata_json or "{}"),
                scheduled_for=r.scheduled_for,
                delivered_at=r.delivered_at,
                created_at=r.created_at
            )
            for r in records
        ]

    # NTF-002: Templates
    async def create_template(
        self,
        template_id: str,
        tenant_id: str,
        name: str,
        channel: str,
        body_template: str,
        subject_template: Optional[str] = None,
        language: str = "en",
        version: int = 1
    ) -> TemplateSchema:
        rec = TemplateRecord(
            id=template_id,
            tenant_id=tenant_id,
            name=name,
            channel=channel,
            language=language,
            body_template=body_template,
            subject_template=subject_template,
            version=version,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return TemplateSchema.model_validate(rec)

    async def get_template(
        self,
        tenant_id: str,
        name: str,
        version: Optional[int] = None,
        channel: Optional[str] = None,
        language: Optional[str] = None
    ) -> Optional[TemplateSchema]:
        stmt = select(TemplateRecord).where(
            TemplateRecord.tenant_id == tenant_id,
            TemplateRecord.name == name
        )
        if channel is not None:
            stmt = stmt.where(TemplateRecord.channel == channel)
        if language is not None:
            stmt = stmt.where(TemplateRecord.language == language)
        if version is not None:
            stmt = stmt.where(TemplateRecord.version == version)
        else:
            stmt = stmt.order_by(TemplateRecord.version.desc())
        res = await self.session.execute(stmt)
        rec = res.scalars().first()
        if not rec:
            return None
        return TemplateSchema.model_validate(rec)

    # NTF-003: User Preferences
    async def set_user_preference(
        self,
        tenant_id: str,
        user_id: str,
        channel_opt_in: Optional[Dict[str, bool]] = None,
        categories_opt_in: Optional[Dict[str, bool]] = None,
        opt_out_all: bool = False,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
        timezone: str = "UTC",
        preferred_channel: Optional[str] = None,
        max_daily_limit: int = 50
    ) -> UserPreferenceSchema:
        pref_id = f"pref_{tenant_id}_{user_id}"
        stmt = select(UserPreferenceRecord).where(UserPreferenceRecord.id == pref_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()

        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc)
        opts = channel_opt_in or {}
        cats = categories_opt_in or {}

        if not rec:
            rec = UserPreferenceRecord(
                id=pref_id,
                tenant_id=tenant_id,
                user_id=user_id,
                channel_opt_in_json=json.dumps(opts),
                categories_opt_in_json=json.dumps(cats),
                opt_out_all=opt_out_all,
                quiet_hours_start=quiet_hours_start,
                quiet_hours_end=quiet_hours_end,
                timezone=timezone or "UTC",
                preferred_channel=preferred_channel,
                max_daily_limit=max_daily_limit,
                updated_at=now
            )
            self.session.add(rec)
        else:
            rec.channel_opt_in_json = json.dumps(opts)
            rec.categories_opt_in_json = json.dumps(cats)
            rec.opt_out_all = opt_out_all
            rec.quiet_hours_start = quiet_hours_start
            rec.quiet_hours_end = quiet_hours_end
            rec.timezone = timezone or "UTC"
            rec.preferred_channel = preferred_channel
            rec.max_daily_limit = max_daily_limit
            rec.updated_at = now

        await self.session.commit()
        return UserPreferenceSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            user_id=rec.user_id,
            channel_opt_in=opts,
            categories_opt_in=cats,
            opt_out_all=rec.opt_out_all,
            quiet_hours_start=rec.quiet_hours_start,
            quiet_hours_end=rec.quiet_hours_end,
            timezone=rec.timezone,
            preferred_channel=rec.preferred_channel,
            max_daily_limit=rec.max_daily_limit,
            updated_at=rec.updated_at
        )

    async def get_user_preference(self, tenant_id: str, user_id: str) -> Optional[UserPreferenceSchema]:
        pref_id = f"pref_{tenant_id}_{user_id}"
        stmt = select(UserPreferenceRecord).where(UserPreferenceRecord.id == pref_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return UserPreferenceSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            user_id=rec.user_id,
            channel_opt_in=json.loads(rec.channel_opt_in_json or "{}"),
            categories_opt_in=json.loads(rec.categories_opt_in_json or "{}"),
            opt_out_all=rec.opt_out_all,
            quiet_hours_start=rec.quiet_hours_start,
            quiet_hours_end=rec.quiet_hours_end,
            timezone=rec.timezone or "UTC",
            preferred_channel=rec.preferred_channel,
            max_daily_limit=rec.max_daily_limit,
            updated_at=rec.updated_at
        )

    # NTF-004: Delivery Attempts
    async def record_delivery_attempt(
        self,
        attempt_id: str,
        notification_id: str,
        provider_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        latency_ms: int = 0
    ) -> DeliveryAttemptSchema:
        rec = DeliveryAttemptRecord(
            id=attempt_id,
            notification_id=notification_id,
            provider_id=provider_id,
            status=status,
            error_code=error_code,
            error_message=error_message,
            latency_ms=latency_ms,
            attempted_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return DeliveryAttemptSchema.model_validate(rec)

    async def get_delivery_attempts(self, notification_id: str) -> List[DeliveryAttemptSchema]:
        stmt = select(DeliveryAttemptRecord).where(
            DeliveryAttemptRecord.notification_id == notification_id
        ).order_by(DeliveryAttemptRecord.attempted_at.asc())
        res = await self.session.execute(stmt)
        return [DeliveryAttemptSchema.model_validate(r) for r in res.scalars().all()]

    # NTF-005: Provider Configs
    async def configure_provider(
        self,
        config_id: str,
        tenant_id: str,
        channel: str,
        provider_name: str,
        credentials: Optional[Dict[str, Any]] = None,
        priority: int = 1,
        rate_limit_rps: int = 100
    ) -> ProviderConfigSchema:
        rec = ProviderConfigRecord(
            id=config_id,
            tenant_id=tenant_id,
            channel=channel,
            provider_name=provider_name,
            credentials_json=json.dumps(credentials or {}),
            priority=priority,
            rate_limit_rps=rate_limit_rps,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return ProviderConfigSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            channel=rec.channel,
            provider_name=rec.provider_name,
            credentials=credentials or {},
            priority=rec.priority,
            rate_limit_rps=rec.rate_limit_rps,
            is_active=rec.is_active,
            created_at=rec.created_at
        )

    async def list_providers_for_channel(self, tenant_id: str, channel: str) -> List[ProviderConfigSchema]:
        stmt = select(ProviderConfigRecord).where(
            ProviderConfigRecord.tenant_id == tenant_id,
            ProviderConfigRecord.channel == channel,
            ProviderConfigRecord.is_active == True
        ).order_by(ProviderConfigRecord.priority.asc())
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return [
            ProviderConfigSchema(
                id=r.id,
                tenant_id=r.tenant_id,
                channel=r.channel,
                provider_name=r.provider_name,
                credentials=json.loads(r.credentials_json or "{}"),
                priority=r.priority,
                rate_limit_rps=r.rate_limit_rps,
                is_active=r.is_active,
                created_at=r.created_at
            )
            for r in records
        ]

    # NTF-006: Scheduled Jobs
    async def schedule_job(
        self,
        job_id: str,
        notification_id: str,
        tenant_id: str,
        run_at: datetime
    ) -> ScheduledJobSchema:
        rec = ScheduledJobRecord(
            job_id=job_id,
            notification_id=notification_id,
            tenant_id=tenant_id,
            run_at=run_at,
            status="PENDING",
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return ScheduledJobSchema.model_validate(rec)

    async def get_due_jobs(self, current_time: datetime) -> List[ScheduledJobSchema]:
        stmt = select(ScheduledJobRecord).where(
            ScheduledJobRecord.status == "PENDING",
            ScheduledJobRecord.run_at <= current_time
        ).order_by(ScheduledJobRecord.run_at.asc())
        res = await self.session.execute(stmt)
        return [ScheduledJobSchema.model_validate(r) for r in res.scalars().all()]

    # NTF-007: Queue State
    async def enqueue_item(
        self,
        item_id: str,
        queue_name: str,
        payload: Dict[str, Any],
        priority: int = 0
    ) -> QueueStateSchema:
        rec = QueueStateRecord(
            item_id=item_id,
            queue_name=queue_name,
            priority=priority,
            payload_json=json.dumps(payload),
            lock_token=None,
            locked_until=None,
            enqueued_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return QueueStateSchema(
            item_id=rec.item_id,
            queue_name=rec.queue_name,
            priority=rec.priority,
            payload=payload,
            lock_token=rec.lock_token,
            locked_until=rec.locked_until,
            enqueued_at=rec.enqueued_at
        )

    _dequeue_lock = None
    _dequeue_lock_loop = None

    async def dequeue_item(
        self,
        queue_name: str,
        lock_token: str,
        lease_seconds: int = 30,
        starvation_threshold_seconds: Optional[int] = None
    ) -> Optional[QueueStateSchema]:
        from datetime import timedelta
        from sqlalchemy import text
        loop = asyncio.get_running_loop()
        if NotificationStoreManager._dequeue_lock is None or NotificationStoreManager._dequeue_lock_loop is not loop:
            NotificationStoreManager._dequeue_lock = asyncio.Lock()
            NotificationStoreManager._dequeue_lock_loop = loop
        async with NotificationStoreManager._dequeue_lock:
            now = datetime.now(timezone.utc)
            until = now + timedelta(seconds=lease_seconds)

            if starvation_threshold_seconds is not None:
                cutoff = now - timedelta(seconds=starvation_threshold_seconds)
                sql_starved = text("""
                    UPDATE queue_state
                    SET lock_token = :token, locked_until = :until
                    WHERE item_id = (
                        SELECT item_id FROM queue_state
                        WHERE queue_name = :q
                          AND (locked_until IS NULL OR locked_until < :now)
                          AND enqueued_at <= :cutoff
                        ORDER BY enqueued_at ASC
                        LIMIT 1
                    )
                    RETURNING item_id, queue_name, priority, payload_json, lock_token, locked_until, enqueued_at
                """)
                res = await self.session.execute(sql_starved, {
                    "token": lock_token,
                    "until": until,
                    "q": queue_name,
                    "now": now,
                    "cutoff": cutoff
                })
                rows = res.mappings().all()
                if rows:
                    row = dict(rows[0])
                    await self.session.commit()
                    return QueueStateSchema(
                        item_id=row["item_id"],
                        queue_name=row["queue_name"],
                        priority=row["priority"],
                        payload=json.loads(row["payload_json"] or "{}"),
                        lock_token=row["lock_token"],
                        locked_until=row["locked_until"],
                        enqueued_at=row["enqueued_at"]
                    )

            sql_normal = text("""
                UPDATE queue_state
                SET lock_token = :token, locked_until = :until
                WHERE item_id = (
                    SELECT item_id FROM queue_state
                    WHERE queue_name = :q
                      AND (locked_until IS NULL OR locked_until < :now)
                    ORDER BY priority DESC, enqueued_at ASC
                    LIMIT 1
                )
                RETURNING item_id, queue_name, priority, payload_json, lock_token, locked_until, enqueued_at
            """)
            res = await self.session.execute(sql_normal, {
                "token": lock_token,
                "until": until,
                "q": queue_name,
                "now": now
            })
            rows = res.mappings().all()
            if not rows:
                return None

            row = dict(rows[0])
            await self.session.commit()
            return QueueStateSchema(
                item_id=row["item_id"],
                queue_name=row["queue_name"],
                priority=row["priority"],
                payload=json.loads(row["payload_json"] or "{}"),
                lock_token=row["lock_token"],
                locked_until=row["locked_until"],
                enqueued_at=row["enqueued_at"]
            )

    # NTF-008: Audit Store
    async def record_audit_event(
        self,
        audit_id: str,
        tenant_id: str,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditSchema:
        now = datetime.now(timezone.utc)
        rec = AuditRecord(
            id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=json.dumps(details or {}),
            created_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return AuditSchema(
            id=rec.id,
            tenant_id=rec.tenant_id,
            actor=rec.actor,
            action=rec.action,
            resource_type=rec.resource_type,
            resource_id=rec.resource_id,
            details=details or {},
            created_at=rec.created_at
        )

    async def get_audit_logs(
        self,
        tenant_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditSchema]:
        stmt = select(AuditRecord).where(AuditRecord.tenant_id == tenant_id)
        if resource_type:
            stmt = stmt.where(AuditRecord.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditRecord.resource_id == resource_id)
        stmt = stmt.order_by(AuditRecord.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return [
            AuditSchema(
                id=r.id,
                tenant_id=r.tenant_id,
                actor=r.actor,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                details=json.loads(r.details_json or "{}"),
                created_at=r.created_at
            )
            for r in records
        ]

    # NTF-125: API Keys
    async def create_api_key(
        self,
        tenant_id: str,
        name: str,
        role: str = "OPERATOR",
        raw_key_override: Optional[str] = None
    ) -> Tuple[ApiKeySchema, str]:
        import hashlib
        import secrets
        key_id = f"key_{uuid.uuid4().hex[:12]}"
        raw_key = raw_key_override or f"ntf_{secrets.token_urlsafe(32)}"
        hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        rec = ApiKeyRecord(
            id=key_id,
            tenant_id=tenant_id,
            hashed_key=hashed,
            role=role.upper(),
            name=name,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return ApiKeySchema.model_validate(rec), raw_key

    async def get_api_key_by_hash(self, hashed_key: str) -> Optional[ApiKeySchema]:
        stmt = select(ApiKeyRecord).where(ApiKeyRecord.hashed_key == hashed_key, ApiKeyRecord.is_active == True)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return ApiKeySchema.model_validate(rec)

    async def revoke_api_key(self, tenant_id: str, key_id: str) -> bool:
        stmt = select(ApiKeyRecord).where(ApiKeyRecord.id == key_id, ApiKeyRecord.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return False
        rec.is_active = False
        await self.session.commit()
        return True
