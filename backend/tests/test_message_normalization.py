import pytest
from core.engine import NotificationRequestPayload, ChannelType

def test_NTF_016_message_normalization():
    """
    NTF-016: Message normalization.
    Tests recipient canonicalization (lowercasing email, formatting phone to digits).
    """
    # 1. Email normalization (case insensitive, trimmed)
    payload_email = NotificationRequestPayload(
        tenant_id="tenant-x",
        user_id="user-1",
        channel=ChannelType.EMAIL,
        recipient="  Alice.Smith@COMPANY.COM  ",
        body="Hello Alice",
        idempotency_key="key-norm-1"
    )
    assert payload_email.recipient == "alice.smith@company.com"

    # 2. SMS normalization (strips dashes, spaces, brackets)
    payload_sms = NotificationRequestPayload(
        tenant_id="tenant-x",
        user_id="user-2",
        channel=ChannelType.SMS,
        recipient="+1 (555) 234-5678",
        body="Security code: 123456",
        idempotency_key="key-norm-2"
    )
    assert payload_sms.recipient == "+15552345678"
