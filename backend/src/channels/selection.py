"""
Deterministic Provider Selection (NTF-052).
Selects the optimal provider based on health, capability match, and cost.
"""

from typing import List, Dict, Optional, Any
from channels.capabilities import ProviderCapabilities


class ProviderSelector:
    """
    Deterministic provider selection engine (NTF-052).
    Given the same inputs, always returns the exact same provider decision.
    """

    @classmethod
    def select_best_provider(
        cls,
        candidates: List[ProviderCapabilities],
        health_status: Dict[str, bool],
        require_attachments: bool = False,
        require_templates: bool = False,
        require_bulk: bool = False,
        required_size_bytes: Optional[int] = None
    ) -> Optional[ProviderCapabilities]:
        chain = cls.select_ordered_fallback_chain(
            candidates=candidates,
            health_status=health_status,
            require_attachments=require_attachments,
            require_templates=require_templates,
            require_bulk=require_bulk,
            required_size_bytes=required_size_bytes
        )
        return chain[0] if chain else None

    @classmethod
    def select_ordered_fallback_chain(
        cls,
        candidates: List[ProviderCapabilities],
        health_status: Dict[str, bool],
        require_attachments: bool = False,
        require_templates: bool = False,
        require_bulk: bool = False,
        required_size_bytes: Optional[int] = None
    ) -> List[ProviderCapabilities]:
        eligible: List[ProviderCapabilities] = []

        for p in candidates:
            if not p.is_active:
                continue
            if require_attachments and not p.supports_attachments:
                continue
            if require_templates and not p.supports_templates:
                continue
            if require_bulk and not p.supports_bulk:
                continue
            if required_size_bytes and p.max_payload_bytes < required_size_bytes:
                continue
            eligible.append(p)

        # Deterministic sorting:
        # 1. Health: True (1) before False (0) -> key: -1 if healthy, 0 if unhealthy
        # 2. Cost: lower cost first
        # 3. Provider ID: alphabetical tie-breaker
        def sort_key(item: ProviderCapabilities):
            is_healthy = health_status.get(item.provider_id, True)
            health_rank = 0 if is_healthy else 1 # 0 comes first
            return (health_rank, item.cost_per_message_cents, item.provider_id)

        eligible.sort(key=sort_key)
        return eligible
