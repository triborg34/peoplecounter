"""Authentication: bcrypt password hashing, JWT tokens, API keys, RBAC."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

import bcrypt
import jwt

from ..config import Settings, get_settings
from ..db.models import User

log = logging.getLogger(__name__)

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER)

# Permission catalogue
PERM_VIEW = "view"
PERM_CAMERAS_MANAGE = "cameras.manage"
PERM_LINES_MANAGE = "lines.manage"
PERM_REPORTS_VIEW = "reports.view"
PERM_REPORTS_EXPORT = "reports.export"
PERM_USERS_MANAGE = "users.manage"
PERM_COUNTERS_RESET = "counters.reset"
PERM_SETTINGS_MANAGE = "settings.manage"

ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    ROLE_ADMIN: {
        PERM_VIEW, PERM_CAMERAS_MANAGE, PERM_LINES_MANAGE, PERM_REPORTS_VIEW, PERM_REPORTS_EXPORT,
        PERM_USERS_MANAGE, PERM_COUNTERS_RESET, PERM_SETTINGS_MANAGE,
    },
    ROLE_OPERATOR: {
        PERM_VIEW, PERM_CAMERAS_MANAGE, PERM_LINES_MANAGE, PERM_REPORTS_VIEW, PERM_REPORTS_EXPORT,
    },
    ROLE_VIEWER: {
        PERM_VIEW, PERM_REPORTS_VIEW,
    },
}


def role_permissions(role: str) -> Set[str]:
    return ROLE_PERMISSIONS.get((role or "").lower(), set())


def can(role: str, permission: str) -> bool:
    return permission in role_permissions(role)


# -- passwords ---------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_strength_error(password: str) -> Optional[str]:
    if len(password or "") < 8:
        return "Password must be at least 8 characters long"
    return None


# -- jwt ---------------------------------------------------------------
def create_token(user: User, token_type: str = "access", settings: Optional[Settings] = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    if token_type == "access":
        expires = now + timedelta(minutes=settings.access_token_minutes)
    else:
        expires = now + timedelta(days=settings.refresh_token_days)
    payload = {
        "sub": user.username,
        "uid": user.id,
        "role": user.role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Optional[Settings] = None, expected_type: str = "access") -> Dict:
    settings = settings or get_settings()
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


# -- api keys ----------------------------------------------------------
def generate_api_key() -> tuple:
    """Return (plain_text_key, prefix, sha256_hash)."""
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    plain = "pcc_" + prefix + "_" + secret
    return plain, prefix, hash_api_key(plain)


def hash_api_key(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_api_key(plain: str, stored_hash: str) -> bool:
    if not plain or not stored_hash:
        return False
    return secrets.compare_digest(hash_api_key(plain), stored_hash)
