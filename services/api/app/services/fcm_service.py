from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings
from app.core.database import get_pool

logger = logging.getLogger(__name__)

_app: Optional[firebase_admin.App] = None

_NOTIFICATION_TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "booking_received": {
        "en": ("New Booking Request", "A passenger wants to join your ride."),
        "ar": ("طلب حجز جديد", "يريد أحد الركاب الانضمام إلى رحلتك."),
    },
    "booking_reminder": {
        "en": (
            "Pending Booking Request",
            "You have a pending booking request waiting for your response.",
        ),
        "ar": ("طلب حجز معلّق", "لديك طلب حجز بانتظار ردك."),
    },
    "booking_confirmed": {
        "en": ("Booking Confirmed", "Your ride booking has been confirmed!"),
        "ar": ("تم تأكيد الحجز", "تم تأكيد حجز رحلتك!"),
    },
    "booking_rejected": {
        "en": ("Booking Not Accepted", "Your booking request was not accepted."),
        "ar": ("لم يتم قبول الحجز", "لم يتم قبول طلب حجزك."),
    },
    "booking_cancelled": {
        "en": ("Booking Cancelled", "A booking on your ride has been cancelled."),
        "ar": ("تم إلغاء الحجز", "تم إلغاء أحد الحجوزات في رحلتك."),
    },
    "booking_expired": {
        "en": ("Booking Expired", "Your booking request has expired."),
        "ar": ("انتهت صلاحية الحجز", "انتهت صلاحية طلب حجزك."),
    },
    "ride_cancelled": {
        "en": ("Ride Cancelled", "Your upcoming ride has been cancelled."),
        "ar": ("تم إلغاء الرحلة", "تم إلغاء رحلتك القادمة."),
    },
    "ride_started": {
        "en": (
            "Ride Started",
            "Your driver has started the ride. Track their location now.",
        ),
        "ar": ("بدأت الرحلة", "بدأ السائق الرحلة. تتبّع موقعه الآن."),
    },
    "ride_completed": {
        "en": ("Ride Completed", "Your ride is complete. Thank you for using Triplyy!"),
        "ar": ("اكتملت الرحلة", "اكتملت رحلتك. شكراً لاستخدامك Triplyy!"),
    },
    "rating_prompt": {
        "en": ("Rate Your Ride", "How was your ride? Tap to leave a rating."),
        "ar": ("قيّم رحلتك", "كيف كانت رحلتك؟ اضغط لترك تقييم."),
    },
    "moderation_outcome": {
        "en": ("Account Notice", "An admin has reviewed a report involving your account."),
        "ar": ("إشعار بخصوص حسابك", "قام أحد المشرفين بمراجعة بلاغ يخص حسابك."),
    },
    "moderation_reinstated": {
        "en": (
            "Account Reinstated",
            "Your account has been reinstated. You can resume booking and driving.",
        ),
        "ar": (
            "تمت إعادة تفعيل الحساب",
            "تمت إعادة تفعيل حسابك. يمكنك الآن استئناف الحجز والقيادة.",
        ),
    },
    "wallet_topup_approved": {
        "en": ("Top-Up Approved", "Your wallet top-up request has been approved and credited."),
        "ar": ("تمت الموافقة على شحن المحفظة", "تمت الموافقة على طلب شحن محفظتك وتم إضافة الرصيد."),
    },
    "wallet_topup_rejected": {
        "en": ("Top-Up Rejected", "Your wallet top-up request was not approved."),
        "ar": ("تم رفض طلب شحن المحفظة", "لم تتم الموافقة على طلب شحن محفظتك."),
    },
    "car_maintenance_earned": {
        "en": (
            "Free Car Maintenance Earned!",
            "You've reached 3000 EGP in car maintenance savings. We'll be in touch to arrange your free maintenance.",
        ),
        "ar": (
            "لقد استحققت صيانة سيارة مجانية!",
            "لقد وصلت إلى 3000 جنيه في مدخرات صيانة السيارة. سنتواصل معك لترتيب الصيانة المجانية.",
        ),
    },
    "verification_approved": {
        "en": ("Identity Verified", "Your identity was verified. You can now book and take rides."),
        "ar": ("تم التحقق من الهوية", "تم التحقق من هويتك. يمكنك الآن حجز الرحلات وقيادتها."),
    },
    "verification_rejected": {
        "en": ("Verification Not Approved", "Your identity verification was not approved. Open the app for details."),
        "ar": ("لم تتم الموافقة على التحقق", "لم تتم الموافقة على التحقق من هويتك. افتح التطبيق للتفاصيل."),
    },
    "loyalty_points_earned": {
        "en": ("Points Earned", "You've earned loyalty points. Open the app to see your balance."),
        "ar": ("تم اكتساب نقاط", "لقد حصلت على نقاط ولاء. افتح التطبيق لرؤية رصيدك."),
    },
    "loyalty_redemption_fulfilled": {
        "en": ("Reward Fulfilled", "Your loyalty points redemption has been fulfilled."),
        "ar": ("تم صرف المكافأة", "تم صرف طلب استبدال نقاط الولاء الخاص بك."),
    },
    "loyalty_redemption_rejected": {
        "en": ("Redemption Not Approved", "Your loyalty points redemption was not approved. Your points were refunded."),
        "ar": ("لم تتم الموافقة على الاستبدال", "لم تتم الموافقة على استبدال نقاط الولاء الخاص بك. تم رد نقاطك."),
    },
    "loyalty_threshold_reached": {
        "en": ("Reward Unlocked!", "You've earned enough loyalty points to redeem a reward."),
        "ar": ("تم فتح مكافأة!", "لقد حصلت على نقاط ولاء كافية لاستبدال مكافأة."),
    },
}

# Locale-aware fallback for event types with no entry above (mirrors the FR-011
# fallback-to-English principle applied to notification content).
_DEFAULT_TEMPLATE: dict[str, tuple[str, str]] = {
    "en": ("Triplyy", "You have a new notification."),
    "ar": ("Triplyy", "لديك إشعار جديد."),
}

_WEEKDAY_NAMES: dict[str, list[str]] = {
    # index 0 = Monday, matching datetime.weekday()
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "ar": ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
}
_MONTH_NAMES: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ar": [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
    ],
}


def _format_day_label(iso_datetime: str | None, locale: str) -> str:
    """Render an ISO datetime as a short day label, e.g. "Thu, Sep 3" (or the
    Arabic equivalent). Returns "" if the datetime is missing/unparseable so
    callers can fall back to a day-agnostic message.
    """
    if not iso_datetime:
        return ""
    try:
        dt = datetime.fromisoformat(iso_datetime)
    except ValueError:
        return ""
    weekday = _WEEKDAY_NAMES.get(locale, _WEEKDAY_NAMES["en"])[dt.weekday()]
    month = _MONTH_NAMES.get(locale, _MONTH_NAMES["en"])[dt.month - 1]
    if locale == "ar":
        return f"{weekday} {dt.day} {month}"
    return f"{weekday}, {month} {dt.day}"


def _select_template(
    event_type: str, locale: str | None, data_payload: dict | None = None
) -> tuple[str, str]:
    """Resolve (title, body) for an event_type/locale pair, defaulting to English.

    For "booking_received", appends the ride's day (from data_payload's
    departure_datetime) to the body so a driver with multiple recurring-ride
    instances can tell which day the new booking is for.
    """
    resolved_locale = locale or "en"
    title, body = _NOTIFICATION_TEMPLATES.get(event_type, _DEFAULT_TEMPLATE)[resolved_locale]

    if event_type == "booking_received" and data_payload:
        day = _format_day_label(data_payload.get("departure_datetime"), resolved_locale)
        if day:
            body = body.rstrip(".")
            body = f"{body} يوم {day}." if resolved_locale == "ar" else f"{body} on {day}."

    return title, body


# FCM error codes that mark a token as permanently invalid (should be deregistered)
_INVALID_TOKEN_CODES = frozenset({
    "registration-token-not-registered",
    "invalid-registration-token",
    "messaging/registration-token-not-registered",
    "messaging/invalid-registration-token",
})


async def initialize_fcm() -> None:
    """Load Firebase credentials from Supabase Vault and initialize the Firebase app.

    Called once during FastAPI lifespan startup, after the connection pool is ready.
    Raises RuntimeError if the Vault secret is missing — treat as a startup failure.
    """
    global _app
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = $1",
            settings.firebase_service_account_secret_name,
        )
    if row is None:
        raise RuntimeError(
            f"Firebase service account secret '{settings.firebase_service_account_secret_name}' "
            "not found in Supabase Vault. Store it via the Supabase dashboard before starting the API."
        )
    cred_dict = json.loads(row["decrypted_secret"])
    cred = credentials.Certificate(cred_dict)
    _app = firebase_admin.initialize_app(cred)
    logger.info("FCM credentials loaded from Vault (project: %s)", cred_dict.get("project_id", "unknown"))


async def send_push_notifications(
    conn,
    recipient_user_id: uuid.UUID,
    event_type: str,
    data_payload: dict,
) -> int:
    """Send FCM push notifications to all active device tokens for a user.

    Deregisters permanently invalid tokens. Returns count of successful sends.
    No-ops silently if FCM is not initialized or the user has no registered tokens.
    """
    if _app is None:
        logger.warning("FCM not initialized — skipping push for user %s event %s", recipient_user_id, event_type)
        return 0

    rows = await conn.fetch(
        "SELECT id, token FROM user_device_tokens WHERE user_id = $1",
        recipient_user_id,
    )
    if not rows:
        return 0

    tokens = [r["token"] for r in rows]
    token_to_id: dict[str, uuid.UUID] = {r["token"]: r["id"] for r in rows}

    profile_row = await conn.fetchrow(
        "SELECT language_preference FROM profiles WHERE id = $1",
        recipient_user_id,
    )
    locale = profile_row["language_preference"] if profile_row else None

    title, body = _select_template(event_type, locale, data_payload)

    multicast_msg = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data_payload.items() if v is not None},
    )

    response = await asyncio.to_thread(messaging.send_each_for_multicast, multicast_msg)

    invalid_ids = [
        token_to_id[tokens[i]]
        for i, result in enumerate(response.responses)
        if not result.success
        and getattr(result.exception, "code", None) in _INVALID_TOKEN_CODES
    ]
    if invalid_ids:
        await conn.execute(
            "DELETE FROM user_device_tokens WHERE id = ANY($1::uuid[])",
            invalid_ids,
        )
        logger.info(
            "Deregistered %d invalid FCM token(s) for user %s",
            len(invalid_ids),
            recipient_user_id,
        )

    return response.success_count
