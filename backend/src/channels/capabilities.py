"""
Provider Capability Matrix (NTF-051).
Maintains metadata regarding features, limits, attachments, and channels supported per provider.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ProviderCapabilities(BaseModel):
    provider_id: str
    channel: str
    supports_attachments: bool = False
    supports_templates: bool = False
    supports_bulk: bool = False
    max_payload_bytes: int = 10 * 1024 * 1024 # 10MB default
    cost_per_message_cents: float = 0.0
    supported_locales: List[str] = Field(default_factory=lambda: ["*"])
    is_active: bool = True


class ProviderCapabilityMatrix:
    """
    Catalog of provider capabilities with eligibility filtering (NTF-051).
    """
    def __init__(self):
        self._registry: Dict[str, ProviderCapabilities] = {}

    def register(self, capabilities: ProviderCapabilities) -> None:
        self._registry[capabilities.provider_id] = capabilities

    def get_capabilities(self, provider_id: str) -> Optional[ProviderCapabilities]:
        return self._registry.get(provider_id)

    def get_eligible_providers(
        self,
        channel: str,
        require_attachments: bool = False,
        require_templates: bool = False,
        require_bulk: bool = False,
        required_size_bytes: Optional[int] = None
    ) -> List[ProviderCapabilities]:
        eligible = []
        target_ch = channel.upper()

        for cap in self._registry.values():
            if not cap.is_active:
                continue
            if cap.channel.upper() != target_ch:
                continue
            if require_attachments and not cap.supports_attachments:
                continue
            if require_templates and not cap.supports_templates:
                continue
            if require_bulk and not cap.supports_bulk:
                continue
            if required_size_bytes and cap.max_payload_bytes < required_size_bytes:
                continue
            eligible.append(cap)

        return eligible
