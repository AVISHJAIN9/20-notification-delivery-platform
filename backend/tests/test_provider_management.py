import pytest
from channels.credentials import ProviderCredentialManager
from channels.capabilities import ProviderCapabilityMatrix, ProviderCapabilities

def test_NTF_049_provider_credentials_encryption_and_masking():
    """
    NTF-049: Provider credentials.
    Tests credential encryption at rest and strict masking on output.
    """
    mgr = ProviderCredentialManager(secret_key="01234567890123456789012345678901")

    raw_credentials = {
        "api_key": "SG.long_secret_sendgrid_token_999",
        "auth_token": "very_confidential_token_xyz",
        "region": "us-east-1"
    }

    # 1. Encrypt credentials at rest
    encrypted = mgr.encrypt_credentials(raw_credentials)
    assert isinstance(encrypted, str)
    assert "SG.long_secret" not in encrypted
    assert "very_confidential" not in encrypted

    # 2. Decrypt for internal engine execution
    decrypted = mgr.decrypt_credentials(encrypted)
    assert decrypted["api_key"] == "SG.long_secret_sendgrid_token_999"
    assert decrypted["auth_token"] == "very_confidential_token_xyz"
    assert decrypted["region"] == "us-east-1"

    # 3. Output masking for API / logs
    masked = mgr.mask_credentials(raw_credentials)
    assert masked["region"] == "us-east-1"  # non-sensitive kept
    assert masked["api_key"] != raw_credentials["api_key"]
    assert "SG." in masked["api_key"]
    assert "***" in masked["api_key"]
    assert masked["auth_token"] != raw_credentials["auth_token"]
    assert "***" in masked["auth_token"]

def test_NTF_051_provider_capability_matrix():
    """
    NTF-051: Provider capability matrix.
    Tests querying provider capability matrix for features, attachment limits, and channels.
    """
    matrix = ProviderCapabilityMatrix()

    p_sendgrid = ProviderCapabilities(
        provider_id="sendgrid",
        channel="EMAIL",
        supports_attachments=True,
        supports_templates=True,
        supports_bulk=True,
        max_payload_bytes=10 * 1024 * 1024, # 10MB
        cost_per_message_cents=0.1
    )
    p_smtp = ProviderCapabilities(
        provider_id="local_smtp",
        channel="EMAIL",
        supports_attachments=False,
        supports_templates=False,
        supports_bulk=False,
        max_payload_bytes=2 * 1024 * 1024, # 2MB
        cost_per_message_cents=0.01
    )
    p_twilio = ProviderCapabilities(
        provider_id="twilio_sms",
        channel="SMS",
        supports_attachments=False,
        supports_templates=False,
        supports_bulk=False,
        max_payload_bytes=1600,
        cost_per_message_cents=0.75
    )

    matrix.register(p_sendgrid)
    matrix.register(p_smtp)
    matrix.register(p_twilio)

    # 1. Filter by channel and attachment capability
    attachment_providers = matrix.get_eligible_providers(
        channel="EMAIL",
        require_attachments=True
    )
    assert len(attachment_providers) == 1
    assert attachment_providers[0].provider_id == "sendgrid"

    # 2. Filter by max payload size
    small_providers = matrix.get_eligible_providers(
        channel="EMAIL",
        required_size_bytes=5 * 1024 * 1024 # 5MB
    )
    assert len(small_providers) == 1
    assert small_providers[0].provider_id == "sendgrid" # local_smtp only supports 2MB

    # 3. Filter for SMS
    sms_providers = matrix.get_eligible_providers(channel="SMS")
    assert len(sms_providers) == 1
    assert sms_providers[0].provider_id == "twilio_sms"
