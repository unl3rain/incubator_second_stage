"""Database-backed auth service with JWT + refresh session rotation and email-delivered codes."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.auth_session import AuthSession
from app.models.auth_token_revocation import AuthTokenRevocation
from app.models.auth_user import AuthUser
from app.services.email_delivery import send_email
from app.services.profile_stats import get_or_create_profile


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_username(username: str) -> str:
    return username.strip()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email.strip()))


def _derive_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 310000)
    return base64.b64encode(raw).decode("utf-8")


def _create_password_hash(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = _derive_password(password, salt)
    return digest, salt


def _verify_password(password: str, expected_hash: str, salt: str) -> bool:
    actual = _derive_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


def _serialize_user(user: AuthUser) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "profile_id": user.profile_id,
        "email_verified": user.email_verified,
    }


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _issue_access_token(user: dict, session_id: str | None = None) -> str:
    subject = user["email"] or user["username"]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "jti": uuid4().hex,
        "sid": session_id,
        "username": user["username"],
        "email": user["email"],
        "profile_id": user["profile_id"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _get_user_by_profile(profile_id: str) -> dict | None:
    with SessionLocal() as session:
        user = session.execute(select(AuthUser).where(AuthUser.profile_id == profile_id)).scalar_one_or_none()
        if user is None:
            return None
        return _serialize_user(user)


def create_or_get_user(username: str | None = None, email: str | None = None) -> dict:
    normalized_username = _normalize_username(username) if username else None
    normalized_email = _normalize_email(email) if email else None
    if not normalized_username and not normalized_email:
        raise ValueError("Either username or email must be provided")

    with SessionLocal() as session:
        user = session.execute(
            select(AuthUser).where(
                or_(
                    AuthUser.email == normalized_email if normalized_email else False,
                    AuthUser.username == normalized_username if normalized_username else False,
                )
            )
        ).scalar_one_or_none()

        if user is None:
            nickname_seed = normalized_username or (normalized_email.split("@")[0] if normalized_email else "Guest")
            profile = get_or_create_profile(None, nickname_seed, None)
            user = AuthUser(
                email=normalized_email,
                username=normalized_username,
                profile_id=profile["profile_id"],
                email_verified=bool(normalized_email is None),
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        return _serialize_user(user)


def register_user(email: str, password: str, username: str | None = None) -> dict:
    normalized_email = _normalize_email(email)
    normalized_username = _normalize_username(username) if username else None
    if not is_valid_email(normalized_email):
        raise ValueError("Invalid email format")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    with SessionLocal() as session:
        existing = session.execute(
            select(AuthUser).where(or_(AuthUser.email == normalized_email, AuthUser.username == normalized_username))
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError("Email or username is already in use")

        digest, salt = _create_password_hash(password)
        verification_code = f"{secrets.randbelow(1000000):06d}"
        nickname_seed = normalized_username or normalized_email.split("@")[0]
        profile = get_or_create_profile(None, nickname_seed, None)

        user = AuthUser(
            email=normalized_email,
            username=normalized_username,
            profile_id=profile["profile_id"],
            password_hash=digest,
            password_salt=salt,
            verification_code=verification_code,
            email_verified=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        send_email(
            normalized_email,
            "Verify your Checkers account",
            f"Your verification code is: {verification_code}\n\nIf you did not request this, ignore this email.",
        )

        return _serialize_user(user)


def authenticate_user(identifier: str, password: str) -> dict | None:
    normalized_identifier = identifier.strip().lower()
    with SessionLocal() as session:
        user = session.execute(
            select(AuthUser).where(or_(AuthUser.email == normalized_identifier, AuthUser.username == identifier.strip()))
        ).scalar_one_or_none()
        if user is None or not user.password_hash or not user.password_salt:
            return None
        if not _verify_password(password, user.password_hash, user.password_salt):
            return None
        return _serialize_user(user)


def authenticate_social_user(
    provider: str,
    provider_user_id: str,
    email: str | None = None,
    username: str | None = None,
) -> dict:
    allowed = {"google", "github", "apple", "discord"}
    normalized_provider = (provider or "").strip().lower()
    if normalized_provider not in allowed:
        raise ValueError("Unsupported social provider")

    normalized_provider_user_id = (provider_user_id or "").strip()
    if not normalized_provider_user_id:
        raise ValueError("provider_user_id is required")

    normalized_email = _normalize_email(email) if email else None
    normalized_username = _normalize_username(username) if username else None

    with SessionLocal() as session:
        user = session.execute(
            select(AuthUser)
            .where(AuthUser.social_provider == normalized_provider)
            .where(AuthUser.social_provider_user_id == normalized_provider_user_id)
        ).scalar_one_or_none()

        if user is None and normalized_email:
            user = session.execute(select(AuthUser).where(AuthUser.email == normalized_email)).scalar_one_or_none()

        if user is None:
            nickname_seed = normalized_username or (normalized_email.split("@")[0] if normalized_email else "Guest")
            profile = get_or_create_profile(None, nickname_seed, None)
            user = AuthUser(
                email=normalized_email,
                username=normalized_username,
                profile_id=profile["profile_id"],
                email_verified=bool(normalized_email),
                social_provider=normalized_provider,
                social_provider_user_id=normalized_provider_user_id,
                social_display_name=normalized_username,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return _serialize_user(user)

        user.social_provider = normalized_provider
        user.social_provider_user_id = normalized_provider_user_id
        if normalized_username and not user.username:
            user.username = normalized_username
            user.social_display_name = normalized_username
        if normalized_email and not user.email:
            user.email = normalized_email
            user.email_verified = True

        session.commit()
        session.refresh(user)
        return _serialize_user(user)


def generate_token(username: str | None = None, email: str | None = None, expires_in_hours: int = 720) -> str:
    # Compatibility helper for legacy callers.
    user = create_or_get_user(username=username, email=email)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["email"] or user["username"],
        "jti": uuid4().hex,
        "username": user["username"],
        "email": user["email"],
        "profile_id": user["profile_id"],
        "iat": now,
        "exp": now + timedelta(hours=expires_in_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def issue_session_tokens(user: dict, user_agent: str | None = None, ip_address: str | None = None, device_label: str | None = None) -> dict:
    refresh_token = secrets.token_urlsafe(48)
    refresh_hash = _hash_token(refresh_token)
    refresh_expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_days)
    session_id = uuid4().hex

    with SessionLocal() as session:
        session.add(
            AuthSession(
                session_id=session_id,
                profile_id=user["profile_id"],
                refresh_token_hash=refresh_hash,
                user_agent=(user_agent or "")[:300] or None,
                ip_address=(ip_address or "")[:64] or None,
                device_label=(device_label or "")[:100] or None,
                refresh_expires_at=refresh_expires_at,
            )
        )
        session.commit()

    access_token = _issue_access_token(user, session_id=session_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "session_id": session_id,
        "expires_in_seconds": settings.access_token_minutes * 60,
    }


def rotate_refresh_token(refresh_token: str, user_agent: str | None = None, ip_address: str | None = None) -> dict | None:
    token_hash = _hash_token(refresh_token)
    now = datetime.utcnow()

    with SessionLocal() as session:
        auth_session = session.execute(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        ).scalar_one_or_none()
        if auth_session is None or auth_session.revoked or auth_session.refresh_expires_at < now:
            return None

        user = session.execute(select(AuthUser).where(AuthUser.profile_id == auth_session.profile_id)).scalar_one_or_none()
        if user is None:
            return None

        next_refresh = secrets.token_urlsafe(48)
        auth_session.refresh_token_hash = _hash_token(next_refresh)
        auth_session.last_seen_at = now
        if user_agent:
            auth_session.user_agent = user_agent[:300]
        if ip_address:
            auth_session.ip_address = ip_address[:64]
        session.commit()

        serialized_user = _serialize_user(user)
        access_token = _issue_access_token(serialized_user, session_id=auth_session.session_id)
        return {
            "access_token": access_token,
            "refresh_token": next_refresh,
            "session_id": auth_session.session_id,
            "expires_in_seconds": settings.access_token_minutes * 60,
        }


def list_active_sessions(profile_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(AuthSession)
            .where(AuthSession.profile_id == profile_id)
            .where(AuthSession.revoked == False)
            .order_by(AuthSession.last_seen_at.desc())
        ).scalars()

        now = datetime.utcnow()
        results = []
        for row in rows:
            if row.refresh_expires_at < now:
                continue
            results.append(
                {
                    "session_id": row.session_id,
                    "device_label": row.device_label,
                    "user_agent": row.user_agent,
                    "ip_address": row.ip_address,
                    "created_at": row.created_at,
                    "last_seen_at": row.last_seen_at,
                    "refresh_expires_at": row.refresh_expires_at,
                }
            )
        return results


def revoke_all_sessions(profile_id: str, keep_session_id: str | None = None) -> int:
    with SessionLocal() as session:
        rows = session.execute(
            select(AuthSession).where(AuthSession.profile_id == profile_id).where(AuthSession.revoked == False)
        ).scalars().all()

        revoked_count = 0
        for row in rows:
            if keep_session_id and row.session_id == keep_session_id:
                continue
            row.revoked = True
            revoked_count += 1
        session.commit()
        return revoked_count


def revoke_session(profile_id: str, session_id: str) -> bool:
    with SessionLocal() as session:
        row = session.execute(
            select(AuthSession)
            .where(AuthSession.profile_id == profile_id)
            .where(AuthSession.session_id == session_id)
        ).scalar_one_or_none()
        if row is None:
            return False

        row.revoked = True
        session.commit()
        return True


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        jti = payload.get("jti")
        if not jti:
            return None

        with SessionLocal() as session:
            revoked = session.execute(select(AuthTokenRevocation).where(AuthTokenRevocation.jti == jti)).scalar_one_or_none()
            if revoked is not None:
                return None

            sid = payload.get("sid")
            if sid:
                auth_session = session.execute(select(AuthSession).where(AuthSession.session_id == sid)).scalar_one_or_none()
                if auth_session is None or auth_session.revoked or auth_session.refresh_expires_at < datetime.utcnow():
                    return None

        return payload
    except (jwt.InvalidTokenError, jwt.DecodeError):
        return None


def get_profile_id_from_token(token: str) -> str | None:
    payload = verify_token(token)
    return payload["profile_id"] if payload else None


def revoke_token(token: str) -> bool:
    payload = verify_token(token)
    if payload is None:
        return False

    jti = payload.get("jti")
    if not jti:
        return False

    with SessionLocal() as session:
        existing = session.execute(select(AuthTokenRevocation).where(AuthTokenRevocation.jti == jti)).scalar_one_or_none()
        if existing is not None:
            return True

        exp_timestamp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else None
        session.add(
            AuthTokenRevocation(
                jti=jti,
                profile_id=payload.get("profile_id"),
                expires_at=expires_at,
            )
        )

        sid = payload.get("sid")
        if sid:
            auth_session = session.execute(select(AuthSession).where(AuthSession.session_id == sid)).scalar_one_or_none()
            if auth_session is not None:
                auth_session.revoked = True

        session.commit()
    return True


def verify_email_code(email: str, code: str) -> bool:
    with SessionLocal() as session:
        user = session.execute(select(AuthUser).where(AuthUser.email == _normalize_email(email))).scalar_one_or_none()
        if user is None or not user.verification_code:
            return False
        if user.verification_code != code.strip():
            return False

        user.email_verified = True
        user.verification_code = None
        session.commit()
        return True


def create_password_reset(email: str) -> bool:
    with SessionLocal() as session:
        user = session.execute(select(AuthUser).where(AuthUser.email == _normalize_email(email))).scalar_one_or_none()
        if user is None:
            return False

        code = secrets.token_urlsafe(24)
        user.reset_code = code
        user.reset_code_expires_at = datetime.utcnow() + timedelta(minutes=20)
        session.commit()

    send_email(
        _normalize_email(email),
        "Reset your Checkers password",
        f"Your password reset code is: {code}\n\nThis code expires in 20 minutes.",
    )
    return True


def reset_password(email: str, code: str, new_password: str) -> bool:
    if len(new_password) < 8:
        return False

    with SessionLocal() as session:
        user = session.execute(select(AuthUser).where(AuthUser.email == _normalize_email(email))).scalar_one_or_none()
        if user is None or not user.reset_code or not user.reset_code_expires_at:
            return False
        if user.reset_code != code.strip():
            return False
        if user.reset_code_expires_at < datetime.utcnow():
            return False

        digest, salt = _create_password_hash(new_password)
        user.password_hash = digest
        user.password_salt = salt
        user.reset_code = None
        user.reset_code_expires_at = None
        session.commit()
        return True


def extract_bearer_token(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    value = auth_header.strip()
    if not value.lower().startswith("bearer "):
        return None
    return value.split(" ", 1)[1].strip()
