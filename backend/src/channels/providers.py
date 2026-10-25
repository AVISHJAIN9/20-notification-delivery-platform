"""
Channels and Provider Abstraction (NTF-042, NTF-043, NTF-045, NTF-047, NTF-048).
Provides:
- Common provider abstraction with latency tracking and normalized responses (NTF-047).
- Email channel adapter (NTF-042).
- SMS channel adapter with segment calculation (NTF-043).
- Webhook channel adapter with HMAC signature generation (NTF-045).
- Provider registry for multi-channel dispatch (NTF-048).
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import time
import hmac
import hashlib
import json
import math
from pydantic import BaseModel, Field


class ProviderResult(BaseModel):
    success: bool
    provider_id: str
    channel: str
    external_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseProvider(ABC):
    """
    Standard provider interface (NTF-047).
    """
    def __init__(self, provider_id: str, channel: str, config: Optional[Dict[str, Any]] = None):
        self.provider_id = provider_id
        self.channel = channel
        self.config = config or {}

    @abstractmethod
    async def send(
        self,
        recipient: str,
        body: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        pass


class EmailChannelProvider(BaseProvider):
    """
    Email delivery provider (NTF-042).
    """
    def __init__(self, provider_id: str = "email-provider-default", config: Optional[Dict[str, Any]] = None):
        super().__init__(provider_id=provider_id, channel="EMAIL", config=config)

    async def send(
        self,
        recipient: str,
        body: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        start_t = time.perf_counter()
        meta = metadata or {}

        # Validate recipient email format
        if "@" not in recipient or "." not in recipient:
            latency = int((time.perf_counter() - start_t) * 1000)
            return ProviderResult(
                success=False,
                provider_id=self.provider_id,
                channel="EMAIL",
                error_code="INVALID_RECIPIENT",
                error_message=f"Invalid email: {recipient}",
                latency_ms=latency
            )

        # Assemble email envelope
        from_email = self.config.get("from_email", "no-reply@notifications.internal")
        envelope = {
            "from": from_email,
            "to": recipient,
            "subject": subject or "Notification",
            "body_length": len(body),
            "headers": {"X-Priority": meta.get("priority", "NORMAL")}
        }

        latency = max(1, int((time.perf_counter() - start_t) * 1000))
        ext_id = f"eml_{hashlib.md5(f'{recipient}:{time.time()}'.encode()).hexdigest()[:12]}"

        return ProviderResult(
            success=True,
            provider_id=self.provider_id,
            channel="EMAIL",
            external_id=ext_id,
            latency_ms=latency,
            metadata={"envelope": envelope}
        )


class SMSChannelProvider(BaseProvider):
    """
    SMS delivery provider with segment counting (NTF-043).
    """
    def __init__(self, provider_id: str = "sms-provider-default", config: Optional[Dict[str, Any]] = None):
        super().__init__(provider_id=provider_id, channel="SMS", config=config)

    async def send(
        self,
        recipient: str,
        body: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        start_t = time.perf_counter()

        if not recipient.startswith("+"):
            latency = int((time.perf_counter() - start_t) * 1000)
            return ProviderResult(
                success=False,
                provider_id=self.provider_id,
                channel="SMS",
                error_code="INVALID_PHONE_NUMBER",
                error_message="Phone number must be E.164 format with leading +",
                latency_ms=latency
            )

        # Calculate SMS segments (160 characters per standard GSM segment)
        body_len = len(body)
        segments = max(1, math.ceil(body_len / 160))

        latency = max(1, int((time.perf_counter() - start_t) * 1000))
        ext_id = f"sms_{hashlib.md5(f'{recipient}:{time.time()}'.encode()).hexdigest()[:12]}"

        return ProviderResult(
            success=True,
            provider_id=self.provider_id,
            channel="SMS",
            external_id=ext_id,
            latency_ms=latency,
            metadata={
                "char_count": body_len,
                "segments": segments,
                "sender_id": self.config.get("sender_id", "NOTIF")
            }
        )


class WebhookChannelProvider(BaseProvider):
    """
    Webhook delivery provider with HMAC-SHA256 signature (NTF-045).
    """
    def __init__(self, provider_id: str = "webhook-provider-default", config: Optional[Dict[str, Any]] = None):
        super().__init__(provider_id=provider_id, channel="WEBHOOK", config=config)
        self.secret = self.config.get("signing_secret", "default_webhook_secret_key").encode()

    def generate_signature(self, payload_bytes: bytes, timestamp: int) -> str:
        msg = f"{timestamp}.".encode() + payload_bytes
        sig = hmac.new(self.secret, msg, hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={sig}"

    async def send(
        self,
        recipient: str,
        body: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProviderResult:
        start_t = time.perf_counter()

        if not (recipient.startswith("http://") or recipient.startswith("https://")):
            latency = int((time.perf_counter() - start_t) * 1000)
            return ProviderResult(
                success=False,
                provider_id=self.provider_id,
                channel="WEBHOOK",
                error_code="INVALID_URL",
                error_message="Webhook recipient must be a valid HTTP or HTTPS URL",
                latency_ms=latency
            )

        ts = int(time.time())
        payload_bytes = body.encode("utf-8")
        signature_header = self.generate_signature(payload_bytes, ts)

        latency = max(1, int((time.perf_counter() - start_t) * 1000))
        ext_id = f"wh_{hashlib.md5(f'{recipient}:{ts}'.encode()).hexdigest()[:12]}"

        return ProviderResult(
            success=True,
            provider_id=self.provider_id,
            channel="WEBHOOK",
            external_id=ext_id,
            latency_ms=latency,
            metadata={
                "target_url": recipient,
                "signature_header": signature_header,
                "timestamp": ts
            }
        )


class ProviderRegistry:
    """
    Registry for managing and resolving provider adapters across channels (NTF-048).
    """
    def __init__(self):
        self._providers: Dict[str, Dict[str, BaseProvider]] = {
            "EMAIL": {},
            "SMS": {},
            "WEBHOOK": {},
            "PUSH": {},
            "IN_APP": {}
        }

    def register(self, provider: BaseProvider) -> None:
        ch = provider.channel.upper()
        if ch not in self._providers:
            self._providers[ch] = {}
        self._providers[ch][provider.provider_id] = provider

    def get_provider(self, channel: str, provider_id: Optional[str] = None) -> Optional[BaseProvider]:
        ch = channel.upper()
        ch_providers = self._providers.get(ch, {})
        if not ch_providers:
            return None
        if provider_id and provider_id in ch_providers:
            return ch_providers[provider_id]
        # Return default first provider registered for channel
        return next(iter(ch_providers.values()), None)

    @property
    def providers(self) -> Dict[str, Dict[str, BaseProvider]]:
        return self._providers

    def list_channel_providers(self, channel: str) -> List[str]:
        return list(self._providers.get(channel.upper(), {}).keys())
