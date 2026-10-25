import pytest
from pydantic import ValidationError
from core.engine import NotificationRequestPayload, ChannelType

def test_NTF_015_notification_schema_validation():
    """
    NTF-015: Notification schema validation.
    Tests validation rules rejecting invalid emails, empty bodies, and invalid recipients.
    """
    # 1. Invalid email recipient
    with pytest.raises(ValidationError, match="Invalid email address"):
        NotificationRequestPayload(
            tenant_id="tenant-x",
            user_id="user-1",
            channel=ChannelType.EMAIL,
            recipient="not-an-email",
            body="Test message",
            idempotency_key="key-val-1"
        )

    # 2. Invalid SMS recipient (non-phone string)
    with pytest.raises(ValidationError, match="Invalid phone number"):
        NotificationRequestPayload(
            tenant_id="tenant-x",
            user_id="user-1",
            channel=ChannelType.SMS,
            recipient="letters-not-digits",
            body="Test SMS",
            idempotency_key="key-val-2"
        )

    # 3. Invalid Webhook recipient (not HTTP/HTTPS)
    with pytest.raises(ValidationError, match="Invalid webhook URL"):
        NotificationRequestPayload(
            tenant_id="tenant-x",
            user_id="user-1",
            channel=ChannelType.WEBHOOK,
            recipient="ftp://myhook.com/api",
            body="Test webhook",
            idempotency_key="key-val-3"
        )

    # 4. Empty body rejected
    with pytest.raises(ValidationError, match="Field cannot be empty"):
        NotificationRequestPayload(
            tenant_id="tenant-x",
            user_id="user-1",
            channel=ChannelType.EMAIL,
            recipient="valid@example.com",
            body="   ",
            idempotency_key="key-val-4"
        )
