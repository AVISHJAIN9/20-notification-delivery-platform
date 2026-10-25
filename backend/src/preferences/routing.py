"""
User Preferences, Routing, and Delivery Suppression (NTF-084, NTF-085, NTF-087, NTF-089, NTF-093).
Enforces:
- Global user opt-out suppression (NTF-084).
- Channel-specific opt-in / opt-out routing (NTF-085).
- Category-specific preferences (NTF-087).
- Frequency capping over rolling 24-hour window.
- Timezone-aware quiet hours suppression with overnight wrap-around & DST (NTF-089).
- Preferred channel resolution (NTF-093).
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from enum import Enum
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.store import NotificationStoreManager, NotificationRecord, NotificationStatus, NotificationPriority


class SuppressionReason(str, Enum):
    OPT_OUT_GLOBAL = "OPT_OUT_GLOBAL"
    OPT_OUT_CHANNEL = "OPT_OUT_CHANNEL"
    OPT_OUT_CATEGORY = "OPT_OUT_CATEGORY"
    FREQUENCY_CAPPED = "FREQUENCY_CAPPED"
    QUIET_HOURS = "QUIET_HOURS"


class RoutingDecision(BaseModel):
    allowed: bool
    suppression_reason: Optional[SuppressionReason] = None
    reason_detail: Optional[str] = None


class PreferenceRoutingEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.store = NotificationStoreManager(session)

    @staticmethod
    def is_in_quiet_hours(
        start_str: str,
        end_str: str,
        check_time: datetime,
        tz_name: str = "UTC"
    ) -> bool:
        """
        Determines if check_time falls within quiet hours (e.g. "22:00" to "08:00").
        Handles overnight midnight wrap-around and local timezone with DST (NTF-089).
        """
        if not start_str or not end_str:
            return False

        try:
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
        except Exception:
            return False

        # Convert check_time to user's local timezone
        try:
            tz = ZoneInfo(tz_name) if tz_name else timezone.utc
            if check_time.tzinfo is None:
                check_time = check_time.replace(tzinfo=timezone.utc)
            local_time = check_time.astimezone(tz)
        except Exception:
            local_time = check_time

        start_minutes = sh * 60 + sm
        end_minutes = eh * 60 + em
        curr_minutes = local_time.hour * 60 + local_time.minute

        if start_minutes < end_minutes:
            # Same day window (e.g. 13:00 to 15:00)
            return start_minutes <= curr_minutes < end_minutes
        else:
            # Overnight window (e.g. 22:00 to 08:00)
            return curr_minutes >= start_minutes or curr_minutes < end_minutes

    async def get_daily_send_count(self, tenant_id: str, user_id: str, since_time: datetime) -> int:
        """
        Calculates total notifications delivered/sent to user in the window.
        """
        stmt = (
            select(func.count(NotificationRecord.id))
            .where(
                NotificationRecord.tenant_id == tenant_id,
                NotificationRecord.user_id == user_id,
                NotificationRecord.status.in_([NotificationStatus.DELIVERED.value, NotificationStatus.DISPATCHING.value]),
                NotificationRecord.created_at >= since_time
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def evaluate_dispatch(
        self,
        tenant_id: str,
        user_id: str,
        channel: str,
        category: Optional[str] = None,
        priority: str = NotificationPriority.NORMAL.value,
        current_time: Optional[datetime] = None,
        is_transactional: bool = False
    ) -> RoutingDecision:
        """
        Evaluates whether a notification is allowed to be dispatched (NTF-084, NTF-085, NTF-087, NTF-089).
        Critical/transactional notifications (or URGENT priority) bypass promotional quiet hours, frequency caps, and opt-outs.
        """
        pref = await self.store.get_user_preference(tenant_id, user_id)
        if not pref:
            return RoutingDecision(allowed=True)

        now = current_time or datetime.now(timezone.utc)

        # 1. Global Opt-Out (NTF-084)
        if pref.opt_out_all and not is_transactional:
            return RoutingDecision(
                allowed=False,
                suppression_reason=SuppressionReason.OPT_OUT_GLOBAL,
                reason_detail="User opted out of all notifications"
            )

        # 2. Channel Preference (NTF-085)
        if pref.channel_opt_in.get(channel.upper()) is False and not is_transactional:
            return RoutingDecision(
                allowed=False,
                suppression_reason=SuppressionReason.OPT_OUT_CHANNEL,
                reason_detail=f"User opted out of {channel} channel"
            )

        # 3. Category Preference (NTF-087)
        if category and not is_transactional:
            cat_lower = category.lower()
            cat_pref = pref.categories_opt_in.get(cat_lower)
            if cat_pref is None:
                cat_pref = pref.categories_opt_in.get(category)
            if cat_pref is False:
                return RoutingDecision(
                    allowed=False,
                    suppression_reason=SuppressionReason.OPT_OUT_CATEGORY,
                    reason_detail=f"User opted out of category '{category}'"
                )

        # Urgent / Critical bypasses frequency caps and quiet hours
        if is_transactional or priority == NotificationPriority.URGENT.value:
            return RoutingDecision(allowed=True)

        # 4. Frequency Capping
        since = now - timedelta(days=1)
        sent_today = await self.get_daily_send_count(tenant_id, user_id, since)
        if sent_today >= pref.max_daily_limit:
            return RoutingDecision(
                allowed=False,
                suppression_reason=SuppressionReason.FREQUENCY_CAPPED,
                reason_detail=f"Daily limit ({pref.max_daily_limit}) exceeded: {sent_today} sent today"
            )

        # 5. Timezone-Aware Quiet Hours Suppression (NTF-089)
        if pref.quiet_hours_start and pref.quiet_hours_end:
            if self.is_in_quiet_hours(pref.quiet_hours_start, pref.quiet_hours_end, now, pref.timezone):
                return RoutingDecision(
                    allowed=False,
                    suppression_reason=SuppressionReason.QUIET_HOURS,
                    reason_detail=f"Current local time in {pref.timezone} is within quiet hours ({pref.quiet_hours_start} - {pref.quiet_hours_end})"
                )

        return RoutingDecision(allowed=True)

    async def resolve_preferred_channel(
        self,
        tenant_id: str,
        user_id: str,
        available_channels: List[str],
        default_channel: str = "EMAIL"
    ) -> str:
        """
        Resolves the preferred channel for a user (NTF-093).
        Honors explicit user channel preference and opt-outs.
        """
        available_upper = [c.upper() for c in available_channels]
        pref = await self.store.get_user_preference(tenant_id, user_id)
        if not pref:
            if default_channel.upper() in available_upper:
                return default_channel.upper()
            return available_upper[0] if available_upper else default_channel.upper()

        # If user has a preferred channel configured and it's available and not opted-out:
        if pref.preferred_channel:
            pref_ch = pref.preferred_channel.upper()
            if pref_ch in available_upper and pref.channel_opt_in.get(pref_ch) is not False:
                return pref_ch

        # Fallback to default channel if available and not opted-out
        default_upper = default_channel.upper()
        if default_upper in available_upper and pref.channel_opt_in.get(default_upper) is not False:
            return default_upper

        # Pick first available channel that is not opted out
        for ch in available_upper:
            if pref.channel_opt_in.get(ch) is not False:
                return ch

        # If all opted out, fallback to default_channel
        return default_upper
