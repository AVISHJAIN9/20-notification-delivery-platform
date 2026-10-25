import pytest
from channels.providers import ProviderRegistry, EmailChannelProvider, SMSChannelProvider

def test_NTF_048_provider_registry():
    """
    NTF-048: Provider registry.
    Tests registering, looking up, and resolving default providers by channel.
    """
    registry = ProviderRegistry()

    p_sendgrid = EmailChannelProvider(provider_id="sendgrid")
    p_ses = EmailChannelProvider(provider_id="aws_ses")
    p_twilio = SMSChannelProvider(provider_id="twilio")

    registry.register(p_sendgrid)
    registry.register(p_ses)
    registry.register(p_twilio)

    # List registered providers for EMAIL
    email_provs = registry.list_channel_providers("EMAIL")
    assert "sendgrid" in email_provs
    assert "aws_ses" in email_provs

    # Lookup specific provider
    assert registry.get_provider("EMAIL", "aws_ses") == p_ses

    # Lookup default provider (first registered)
    assert registry.get_provider("EMAIL") == p_sendgrid
    assert registry.get_provider("SMS") == p_twilio
