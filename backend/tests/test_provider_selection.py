import pytest
from channels.capabilities import ProviderCapabilities
from channels.selection import ProviderSelector

def test_NTF_052_deterministic_provider_selection():
    """
    NTF-052: Provider selection.
    Tests deterministic selection based on capability matching, health, and cost.
    """
    p_premium = ProviderCapabilities(
        provider_id="mailgun-premium",
        channel="EMAIL",
        supports_attachments=True,
        supports_templates=True,
        supports_bulk=True,
        max_payload_bytes=20 * 1024 * 1024,
        cost_per_message_cents=0.5
    )
    p_cheap = ProviderCapabilities(
        provider_id="ses-cheap",
        channel="EMAIL",
        supports_attachments=True,
        supports_templates=True,
        supports_bulk=True,
        max_payload_bytes=10 * 1024 * 1024,
        cost_per_message_cents=0.08
    )
    p_unhealthy = ProviderCapabilities(
        provider_id="sendgrid-unhealthy",
        channel="EMAIL",
        supports_attachments=True,
        supports_templates=True,
        supports_bulk=True,
        max_payload_bytes=10 * 1024 * 1024,
        cost_per_message_cents=0.02 # Cheaper but down!
    )

    candidates = [p_premium, p_cheap, p_unhealthy]
    health = {
        "mailgun-premium": True,
        "ses-cheap": True,
        "sendgrid-unhealthy": False
    }

    # 1. Deterministic selection: ses-cheap should be chosen (healthy and lowest cost)
    best1 = ProviderSelector.select_best_provider(
        candidates=candidates,
        health_status=health,
        require_attachments=True
    )
    assert best1 is not None
    assert best1.provider_id == "ses-cheap"

    # Run 100 times to verify determinism
    for _ in range(100):
        best = ProviderSelector.select_best_provider(
            candidates=candidates,
            health_status=health,
            require_attachments=True
        )
        assert best.provider_id == "ses-cheap"

    # 2. If ses-cheap becomes unhealthy, falls back to mailgun-premium
    health["ses-cheap"] = False
    best2 = ProviderSelector.select_best_provider(
        candidates=candidates,
        health_status=health,
        require_attachments=True
    )
    assert best2.provider_id == "mailgun-premium"
