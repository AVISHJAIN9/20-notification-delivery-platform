import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.store import NotificationStoreManager, NotificationPriority
from preferences.routing import PreferenceRoutingEngine, SuppressionReason


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_NTF_084_user_notification_preferences(async_session):
    """
    NTF-084: User notification preferences.
    Tests preference persistence and comprehensive routing evaluation.
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    # 1. Set full user preferences
    pref = await store.set_user_preference(
        tenant_id="tenant-p84",
        user_id="user-p84",
        channel_opt_in={"EMAIL": True, "SMS": False},
        categories_opt_in={"marketing": False, "alerts": True},
        opt_out_all=False,
        quiet_hours_start="23:00",
        quiet_hours_end="07:00",
        timezone="America/New_York",
        preferred_channel="EMAIL",
        max_daily_limit=25
    )
    assert pref.tenant_id == "tenant-p84"
    assert pref.user_id == "user-p84"
    assert pref.timezone == "America/New_York"
    assert pref.preferred_channel == "EMAIL"
    assert pref.max_daily_limit == 25

    # 2. Verify allowed dispatch
    dec_allowed = await engine.evaluate_dispatch(
        tenant_id="tenant-p84",
        user_id="user-p84",
        channel="EMAIL",
        category="alerts"
    )
    assert dec_allowed.allowed is True

    # 3. Verify channel opt-out
    dec_sms = await engine.evaluate_dispatch(
        tenant_id="tenant-p84",
        user_id="user-p84",
        channel="SMS",
        category="alerts"
    )
    assert dec_sms.allowed is False
    assert dec_sms.suppression_reason == SuppressionReason.OPT_OUT_CHANNEL

    # 4. Transactional message bypasses channel opt-out
    dec_trans = await engine.evaluate_dispatch(
        tenant_id="tenant-p84",
        user_id="user-p84",
        channel="SMS",
        category="alerts",
        is_transactional=True
    )
    assert dec_trans.allowed is True


@pytest.mark.asyncio
async def test_NTF_087_category_preferences(async_session):
    """
    NTF-087: Category preferences.
    Tests opt-out of specific categories (e.g. marketing, newsletters) while permitting others (e.g. security, billing).
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    await store.set_user_preference(
        tenant_id="tenant-cat",
        user_id="user-cat",
        categories_opt_in={"marketing": False, "newsletters": False, "security": True, "billing": True}
    )

    # Opted-out category should be suppressed
    dec_mkt = await engine.evaluate_dispatch(
        tenant_id="tenant-cat",
        user_id="user-cat",
        channel="EMAIL",
        category="marketing"
    )
    assert dec_mkt.allowed is False
    assert dec_mkt.suppression_reason == SuppressionReason.OPT_OUT_CATEGORY
    assert "marketing" in dec_mkt.reason_detail

    # Allowed category should be permitted
    dec_sec = await engine.evaluate_dispatch(
        tenant_id="tenant-cat",
        user_id="user-cat",
        channel="EMAIL",
        category="security"
    )
    assert dec_sec.allowed is True

    # Transactional messages bypass category suppression
    dec_mkt_trans = await engine.evaluate_dispatch(
        tenant_id="tenant-cat",
        user_id="user-cat",
        channel="EMAIL",
        category="marketing",
        is_transactional=True
    )
    assert dec_mkt_trans.allowed is True


@pytest.mark.asyncio
async def test_NTF_089_timezone_aware_delivery_with_dst(async_session):
    """
    NTF-089: Timezone-aware delivery.
    Tests quiet hours suppression respecting the user's configured timezone and Daylight Saving Time (DST).
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    # User in New York with quiet hours 22:00 to 08:00
    await store.set_user_preference(
        tenant_id="tenant-tz",
        user_id="user-ny",
        quiet_hours_start="22:00",
        quiet_hours_end="08:00",
        timezone="America/New_York"
    )

    # Test 1: Summer (EDT is UTC-4).
    # 03:00 UTC = 23:00 EDT (inside quiet hours 22:00 - 08:00)
    summer_time_utc = datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc)
    dec_summer = await engine.evaluate_dispatch(
        tenant_id="tenant-tz",
        user_id="user-ny",
        channel="EMAIL",
        current_time=summer_time_utc
    )
    assert dec_summer.allowed is False
    assert dec_summer.suppression_reason == SuppressionReason.QUIET_HOURS

    # 15:00 UTC = 11:00 EDT (outside quiet hours)
    summer_day_utc = datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc)
    dec_summer_day = await engine.evaluate_dispatch(
        tenant_id="tenant-tz",
        user_id="user-ny",
        channel="EMAIL",
        current_time=summer_day_utc
    )
    assert dec_summer_day.allowed is True

    # Test 2: Winter (EST is UTC-5).
    # 03:00 UTC = 22:00 EST (inside quiet hours)
    winter_night_utc = datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)
    dec_winter_night = await engine.evaluate_dispatch(
        tenant_id="tenant-tz",
        user_id="user-ny",
        channel="EMAIL",
        current_time=winter_night_utc
    )
    assert dec_winter_night.allowed is False
    assert dec_winter_night.suppression_reason == SuppressionReason.QUIET_HOURS

    # 13:30 UTC = 08:30 EST (outside quiet hours, just after 08:00)
    winter_morning_utc = datetime(2026, 1, 15, 13, 30, tzinfo=timezone.utc)
    dec_winter_morning = await engine.evaluate_dispatch(
        tenant_id="tenant-tz",
        user_id="user-ny",
        channel="EMAIL",
        current_time=winter_morning_utc
    )
    assert dec_winter_morning.allowed is True

    # User in Tokyo (JST is UTC+9, no DST)
    await store.set_user_preference(
        tenant_id="tenant-tz",
        user_id="user-tokyo",
        quiet_hours_start="23:00",
        quiet_hours_end="07:00",
        timezone="Asia/Tokyo"
    )
    # 15:00 UTC = 00:00 JST (midnight, inside quiet hours)
    tokyo_night = datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc)
    dec_tokyo = await engine.evaluate_dispatch(
        tenant_id="tenant-tz",
        user_id="user-tokyo",
        channel="EMAIL",
        current_time=tokyo_night
    )
    assert dec_tokyo.allowed is False
    assert dec_tokyo.suppression_reason == SuppressionReason.QUIET_HOURS


@pytest.mark.asyncio
async def test_NTF_093_preferred_channel(async_session):
    """
    NTF-093: Preferred channel routing.
    Tests resolving user preferred channel with channel opt-in checks and fallback behavior.
    """
    store = NotificationStoreManager(async_session)
    engine = PreferenceRoutingEngine(async_session)

    # 1. User prefers SMS and it is available and opted-in
    await store.set_user_preference(
        tenant_id="tenant-prefch",
        user_id="user-1",
        preferred_channel="SMS",
        channel_opt_in={"SMS": True, "EMAIL": True}
    )
    resolved = await engine.resolve_preferred_channel(
        tenant_id="tenant-prefch",
        user_id="user-1",
        available_channels=["EMAIL", "SMS", "PUSH"]
    )
    assert resolved == "SMS"

    # 2. Preferred channel is not supported/available for this notification -> falls back to default
    resolved_fallback = await engine.resolve_preferred_channel(
        tenant_id="tenant-prefch",
        user_id="user-1",
        available_channels=["EMAIL", "SLACK"],
        default_channel="EMAIL"
    )
    assert resolved_fallback == "EMAIL"

    # 3. User preferred channel is explicitly opted-out -> falls back to first available opted-in channel
    await store.set_user_preference(
        tenant_id="tenant-prefch",
        user_id="user-2",
        preferred_channel="SMS",
        channel_opt_in={"SMS": False, "PUSH": True, "EMAIL": False}
    )
    resolved_opted_out = await engine.resolve_preferred_channel(
        tenant_id="tenant-prefch",
        user_id="user-2",
        available_channels=["SMS", "PUSH", "EMAIL"],
        default_channel="EMAIL"
    )
    assert resolved_opted_out == "PUSH"
