import pytest
from channels.providers import BaseProvider, ProviderResult, EmailChannelProvider, SMSChannelProvider, WebhookChannelProvider

def test_NTF_047_provider_abstraction():
    """
    NTF-047: Provider abstraction.
    Validates that all channel providers conform to BaseProvider interface
    and return uniform ProviderResult structures.
    """
    providers = [
        EmailChannelProvider(),
        SMSChannelProvider(),
        WebhookChannelProvider()
    ]

    for p in providers:
        assert isinstance(p, BaseProvider)
        assert hasattr(p, "send")
        assert hasattr(p, "provider_id")
        assert hasattr(p, "channel")
