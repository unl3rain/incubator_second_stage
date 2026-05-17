from __future__ import annotations

import json
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

_STATE_TTL_SECONDS = 600
_STATE_LOCK = threading.RLock()
_STATE_ISSUED_AT: dict[str, dict] = {}


def issue_google_oauth_state(oauth_session: str) -> tuple[str, str]:
    if not oauth_session:
        raise ValueError("oauth_session is required")

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    now = time.time()

    with _STATE_LOCK:
        _cleanup_expired_states(now)
        _STATE_ISSUED_AT[state] = {
            "issued_at": now,
            "oauth_session": oauth_session,
            "nonce": nonce,
        }

    return state, nonce


def consume_google_oauth_state(state: str) -> dict | None:
    if not state:
        return None

    now = time.time()
    with _STATE_LOCK:
        _cleanup_expired_states(now)
        payload = _STATE_ISSUED_AT.pop(state, None)
        if payload is None:
            return None
        issued_at = float(payload.get("issued_at", 0))
        if now - issued_at > _STATE_TTL_SECONDS:
            return None
        return payload


def build_google_auth_url(state: str, nonce: str) -> str:
    client_id = settings.google_oauth_client_id
    redirect_uri = settings.google_oauth_redirect_uri

    if not client_id or not redirect_uri:
        raise ValueError("Google OAuth is not configured")

    # Catch common placeholder or malformed client IDs before redirecting to Google.
    if client_id in {"dev-google-client-id", "your-google-client-id"} or not client_id.endswith(".apps.googleusercontent.com"):
        raise ValueError("Google OAuth client ID is invalid. Set GOOGLE_OAUTH_CLIENT_ID from Google Cloud OAuth credentials.")

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return f"{_GOOGLE_AUTH_URL}?{query}"


def exchange_google_code_for_profile(code: str, expected_nonce: str) -> dict:
    client_id = settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret
    redirect_uri = settings.google_oauth_redirect_uri

    if not client_id or not client_secret or not redirect_uri:
        raise ValueError("Google OAuth credentials are missing")

    token_body = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    token_req = Request(
        _GOOGLE_TOKEN_URL,
        data=token_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urlopen(token_req, timeout=10) as response:
        token_payload = json.loads(response.read().decode("utf-8"))

    access_token = token_payload.get("access_token")
    id_token = token_payload.get("id_token")
    if not access_token or not id_token:
        raise ValueError("Google token exchange failed")

    tokeninfo_req = Request(
        f"{_GOOGLE_TOKENINFO_URL}?id_token={id_token}",
        method="GET",
    )
    with urlopen(tokeninfo_req, timeout=10) as response:
        tokeninfo = json.loads(response.read().decode("utf-8"))

    aud = tokeninfo.get("aud")
    iss = tokeninfo.get("iss")
    nonce = tokeninfo.get("nonce")
    exp_raw = tokeninfo.get("exp")

    if aud != client_id:
        raise ValueError("Google token audience mismatch")
    if iss not in {"https://accounts.google.com", "accounts.google.com"}:
        raise ValueError("Google token issuer mismatch")
    if expected_nonce and nonce != expected_nonce:
        raise ValueError("Google token nonce mismatch")
    if exp_raw is not None:
        try:
            exp_timestamp = int(exp_raw)
        except (TypeError, ValueError):
            raise ValueError("Google token expiry is invalid")
        if exp_timestamp <= int(time.time()):
            raise ValueError("Google token expired")

    profile_req = Request(
        _GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    with urlopen(profile_req, timeout=10) as response:
        profile = json.loads(response.read().decode("utf-8"))

    if not profile.get("sub"):
        raise ValueError("Google profile payload is invalid")
    if profile.get("email_verified") is False:
        raise ValueError("Google email is not verified")

    return profile


def _cleanup_expired_states(now: float) -> None:
    expired = [
        state
        for state, payload in _STATE_ISSUED_AT.items()
        if now - float(payload.get("issued_at", 0)) > _STATE_TTL_SECONDS
    ]
    for state in expired:
        _STATE_ISSUED_AT.pop(state, None)
