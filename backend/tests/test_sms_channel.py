import pytest
from channels.providers import SMSChannelProvider

@pytest.mark.asyncio
async def test_NTF_043_sms_channel():
    """
    NTF-043: SMS channel.
    Tests SMS provider E.164 validation and segment calculations.
    """
    provider = SMSChannelProvider(
        provider_id="provider-twilio",
        config={"sender_id": "ACME"}
    )

    # 1. Single-segment SMS (<= 160 chars)
    short_body = "Your login verification code is 492810."
    res1 = await provider.send(
        recipient="+14155552671",
        body=short_body
    )
    assert res1.success is True
    assert res1.channel == "SMS"
    assert res1.metadata["segments"] == 1
    assert res1.metadata["sender_id"] == "ACME"

    # 2. Multi-segment SMS (> 160 chars)
    long_body = "A" * 350  # 350 chars = 3 segments (160 + 160 + 30)
    res2 = await provider.send(
        recipient="+14155552671",
        body=long_body
    )
    assert res2.success is True
    assert res2.metadata["segments"] == 3

    # 3. Non E.164 phone number
    err_res = await provider.send(
        recipient="5551234",
        body="Missing plus code"
    )
    assert err_res.success is False
    assert err_res.error_code == "INVALID_PHONE_NUMBER"
