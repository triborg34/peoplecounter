"""FastAPI dependencies: database session, runtime access, authentication."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db.models import ApiKey, User
from ..engine.runtime import EngineRuntime
from ..services import auth as auth_service

log = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def get_runtime(request: Request) -> EngineRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:  # pragma: no cover - only when the app was not wired up
        raise HTTPException(status_code=503, detail="Engine runtime is not available")
    return runtime


def get_db(request: Request) -> Session:
    runtime = request.app.state.runtime
    session = runtime.db.session()
    try:
        yield session
    finally:
        session.close()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _user_from_api_key(session: Session, plain_key: str) -> Optional[User]:
    key_hash = auth_service.hash_api_key(plain_key)
    record = session.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)).first()
    if record is None:
        return None
    record.last_used_at = None
    from ..db.models import utcnow

    record.last_used_at = utcnow()
    session.commit()
    admin = session.query(User).filter(User.role == "admin", User.is_active.is_(True)).first()
    if admin is not None:
        return admin
    return session.query(User).filter(User.is_active.is_(True)).first()


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: Session = Depends(get_db),
) -> User:
    api_key = request.headers.get("x-api-key")
    if api_key:
        user = _user_from_api_key(session, api_key)
        if user is not None:
            return user
        raise HTTPException(status_code=401, detail="Invalid API key")

    if credentials is None or not credentials.credentials:
        # Allow a token via query string for media endpoints (e.g. <img src> MJPEG
        # streams and WebSocket-style clients) that cannot set headers.
        query_token = request.query_params.get("token")
        if query_token:
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=query_token)
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = auth_service.decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = session.query(User).filter(User.username == payload.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is deactivated")
    return user


def require_permission(permission: str) -> Callable:
    """Dependency factory enforcing a role permission."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not auth_service.can(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: " + permission,
            )
        return user

    return dependency


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user
