import pytest
from channels.providers import BaseProvider, ProviderResult
from retries.failure import ProviderFallbackRouter

class MockFailingProvider(BaseProvider):
    def __init__(self, provider_id: str, error_code: str = "TIMEOUT"):
        super().__init__(provider_id, "EMAIL")
        self.error_code = error_code

    async def send(self, recipient, body, subject=None, metadata=None):
        return ProviderResult(
            success=False,
            provider_id=self.provider_id,
            channel="EMAIL",
            error_code=self.error_code,
            error_message="Simulated error"
        )

class MockSuccessProvider(BaseProvider):
    def __init__(self, provider_id: str):
        super().__init__(provider_id, "EMAIL")

    async def send(self, recipient, body, subject=None, metadata=None):
        return ProviderResult(
            success=True,
            provider_id=self.provider_id,
            channel="EMAIL",
            external_id="ext-success-123"
        )

@pytest.mark.asyncio
async def test_NTF_076_provider_fallback():
    """
    NTF-076: Provider fallback.
    Tests cascading to backup provider when primary encounters retryable error.
    """
    primary = MockFailingProvider("sendgrid-primary", error_code="RATE_LIMITED")
    backup = MockSuccessProvider("mailgun-backup")

    res, attempts = await ProviderFallbackRouter.dispatch_with_fallback(
        providers=[primary, backup],
        recipient="user@test.com",
        body="Fallback test message"
    )

    # Dispatch succeeds via backup provider
    assert res.success is True
    assert res.provider_id == "mailgun-backup"
    assert len(attempts) == 2
    assert attempts[0]["provider_id"] == "sendgrid-primary"
    assert attempts[0]["success"] is False
    assert attempts[1]["provider_id"] == "mailgun-backup"
    assert attempts[1]["success"] is True

@pytest.mark.asyncio
async def test_NTF_054_provider_fallback_idempotent():
    """
    NTF-054: Provider fallback.
    Tests fallback providers in configured order and ensures no double-send when primary succeeds.
    """
    p1 = MockSuccessProvider("primary-prov")
    p2 = MockSuccessProvider("backup-prov")

    res, attempts = await ProviderFallbackRouter.dispatch_with_fallback(
        providers=[p1, p2],
        recipient="user@test.com",
        body="Message with idempotency check",
        metadata={"idempotency_key": "idem-safe-123"}
    )

    # Primary succeeds, so backup provider MUST NEVER be called
    assert res.success is True
    assert res.provider_id == "primary-prov"
    assert len(attempts) == 1
    assert attempts[0]["provider_id"] == "primary-prov"
