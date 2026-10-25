import pytest
from channels.providers import EmailChannelProvider

@pytest.mark.asyncio
async def test_NTF_042_email_channel():
    """
    NTF-042: Email channel.
    Tests email provider assembling headers, validating recipient, and delivering payload.
    """
    provider = EmailChannelProvider(
        provider_id="provider-smtp-main",
        config={"from_email": "billing@saas.com"}
    )

    # 1. Successful email send
    res = await provider.send(
        recipient="customer@enterprise.com",
        subject="Monthly Invoice Ready",
        body="Your invoice for October is $50.00.",
        metadata={"priority": "HIGH"}
    )
    assert res.success is True
    assert res.channel == "EMAIL"
    assert res.external_id.startswith("eml_")
    assert res.metadata["envelope"]["from"] == "billing@saas.com"
    assert res.metadata["envelope"]["to"] == "customer@enterprise.com"

    # 2. Invalid recipient email
    err_res = await provider.send(
        recipient="invalid-email-string",
        body="Hello"
    )
    assert err_res.success is False
    assert err_res.error_code == "INVALID_RECIPIENT"
