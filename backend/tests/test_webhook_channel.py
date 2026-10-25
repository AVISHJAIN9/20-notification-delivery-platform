import pytest
import hmac
import hashlib
from channels.providers import WebhookChannelProvider

@pytest.mark.asyncio
async def test_NTF_045_webhook_channel():
    """
    NTF-045: Webhook channel.
    Tests webhook payload preparation with HMAC-SHA256 signature verification.
    """
    secret = "my_super_secret_webhook_key"
    provider = WebhookChannelProvider(
        provider_id="provider-webhook-http",
        config={"signing_secret": secret}
    )

    body = '{"event": "user.signup", "user_id": "usr_99"}'
    res = await provider.send(
        recipient="https://api.partner.com/events/listen",
        body=body
    )

    assert res.success is True
    assert res.channel == "WEBHOOK"
    sig_header = res.metadata["signature_header"]
    assert sig_header.startswith("t=")
    assert ",v1=" in sig_header

    # Verify signature manually
    parts = dict(part.split("=") for part in sig_header.split(","))
    timestamp = parts["t"]
    expected_v1 = parts["v1"]

    msg = f"{timestamp}.".encode() + body.encode("utf-8")
    actual_sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    assert actual_sig == expected_v1
