"""Authentication endpoints."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ....db.models import User, utcnow
from ....services import audit
from ....services import auth as auth_service
from ...deps import client_ip, get_current_user, get_db
from ..schemas import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse, UserOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_attempts: Dict[str, Deque[float]] = defaultdict(deque)
_attempts_lock = threading.Lock()


def _rate_limited(identifier: str, limit: int, window_s: float = 60.0) -> bool:
    now = time.monotonic()
    with _attempts_lock:
        bucket = _attempts[identifier]
        while bucket and now - bucket[0] > window_s:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
    return False


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> TokenResponse:
    ip = client_ip(request)
    limit = request.app.state.runtime.settings.rate_limit_login_per_minute
    if _rate_limited(ip, limit):
        raise HTTPException(status_code=429, detail="Too many login attempts, try again later")

    user = session.query(User).filter(User.username == payload.username).first()
    if user is None or not auth_service.verify_password(payload.password, user.password_hash):
        audit.record(session, "login_failed", username=payload.username, details="bad credentials", ip_address=ip)
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is deactivated")

    user.last_login_at = utcnow()
    audit.record(session, "login", user=user, ip_address=ip)
    session.commit()

    settings = request.app.state.runtime.settings
    return TokenResponse(
        access_token=auth_service.create_token(user, "access", settings),
        refresh_token=auth_service.create_token(user, "refresh", settings),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, session: Session = Depends(get_db)) -> TokenResponse:
    settings = request.app.state.runtime.settings
    try:
        claims = auth_service.decode_token(payload.refresh_token, settings, expected_type="refresh")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = session.query(User).filter(User.username == claims.get("sub")).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return TokenResponse(
        access_token=auth_service.create_token(user, "access", settings),
        refresh_token=auth_service.create_token(user, "refresh", settings),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict:
    error = auth_service.password_strength_error(payload.new_password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not auth_service.verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = auth_service.hash_password(payload.new_password)
    user.must_change_password = False
    audit.record(session, "password_changed", user=user, entity_type="user", entity_id=user.id,
                 ip_address=client_ip(request))
    session.commit()
    return {"ok": True}
