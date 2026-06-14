from supabase import create_client

from app.core.config import settings


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def append_log(
    admin_id: str,
    action_type: str,
    target_user_id: str,
    submission_id: str | None = None,
    reason: str | None = None,
) -> str:
    sb = _supabase()
    row = {
        "admin_id": admin_id,
        "action_type": action_type,
        "target_user_id": target_user_id,
    }
    if submission_id:
        row["submission_id"] = submission_id
    if reason:
        row["reason"] = reason

    resp = sb.table("admin_audit_logs").insert(row).execute()
    return resp.data[0]["id"]
