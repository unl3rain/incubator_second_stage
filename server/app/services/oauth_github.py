from __future__ import annotations

import json
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings

_GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"

_STATE_TTL_SECONDS = 600
_STATE_LOCK = threading.RLock()
_STATE_ISSUED_AT: dict[str, dict] = {}


def issue_github_oauth_state(oauth_session: str) -> tuple[str, str]:
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


def consume_github_oauth_state(state: str) -> dict | None:
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


def build_github_auth_url(state: str) -> str:
    client_id = settings.github_oauth_client_id
    redirect_uri = settings.github_oauth_redirect_uri

    if not client_id or not redirect_uri:
        raise ValueError("GitHub OAuth is not configured")

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state,
            "allow_signup": "true",
        }
    )
    return f"{_GITHUB_AUTH_URL}?{query}"


def exchange_github_code_for_profile(code: str) -> dict:
    client_id = settings.github_oauth_client_id
    client_secret = settings.github_oauth_client_secret
    redirect_uri = settings.github_oauth_redirect_uri

    if not client_id or not client_secret or not redirect_uri:
        raise ValueError("GitHub OAuth credentials are missing")

    token_body = urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")

    token_req = Request(
        _GITHUB_TOKEN_URL,
        data=token_body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urlopen(token_req, timeout=10) as response:
        token_payload = json.loads(response.read().decode("utf-8"))

    access_token = token_payload.get("access_token")
    if not access_token:
        raise ValueError("GitHub token exchange failed")

    profile_req = Request(
        _GITHUB_USER_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        },
        method="GET",
    )

    with urlopen(profile_req, timeout=10) as response:
        profile = json.loads(response.read().decode("utf-8"))

    if not profile.get("id"):
        raise ValueError("GitHub profile payload is invalid")

    return profile


def _cleanup_expired_states(now: float) -> None:
    expired = [
        state
        for state, payload in _STATE_ISSUED_AT.items()
        if now - float(payload.get("issued_at", 0)) > _STATE_TTL_SECONDS
    ]
    for state in expired:
        _STATE_ISSUED_AT.pop(state, None)
