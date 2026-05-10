# auth.py
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth.transport.requests
from supabase import create_client
from PyQt6.QtCore import QSettings

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_supabase_client():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

def perform_login():
    """Handles Google OAuth and Supabase upsert."""
    SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
    flow  = InstalledAppFlow.from_client_secrets_file(".secrets/client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    session = google.auth.transport.requests.AuthorizedSession(creds)
    info    = session.get("https://www.googleapis.com/oauth2/v2/userinfo").json()

    # Supabase Upsert
    sb = get_supabase_client()
    if sb:
        result = (
            sb.table("users")
            .upsert({
                "google_sub":  info.get("id"),
                "email":       info.get("email"),
                "given_name":  info.get("given_name"),
                "picture_url": info.get("picture"),
                "last_seen_at": "now()",
            }, on_conflict="google_sub")
            .execute()
        )
        rows = result.data
        info["is_pro"] = rows[0].get("is_pro", False) if rows else False
    else:
        info["is_pro"] = False

    s = QSettings("ScreenBreak", "ScreenBreak")
    s.setValue("user_info", json.dumps(info))
    return info

def load_cached_user():
    """Returns cached user info if available."""
    s = QSettings("ScreenBreak", "ScreenBreak")
    saved = s.value("user_info", None)
    if saved:
        try:
            return json.loads(saved)
        except Exception:
            pass
    return None

def logout_user():
    s = QSettings("ScreenBreak", "ScreenBreak")
    s.remove("user_info")