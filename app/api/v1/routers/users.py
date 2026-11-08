"""User administration and API keys (admin only)."""
from __future__ import annotations

import datetime as dt
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db.models import ApiKey, AuditLog, User
from ....services import audit
from ....services import auth as auth_service
from ...deps import client_ip, get_db, require_admin
from ..schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, UserCreate, UserOut, UserUpdate

log = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(session: Session = Depends(get_db), _: User = Depends(require_admin)) -> List[UserOut]:
    users = session.execute(select(User).order_by(User.username)).scalars().all()
    return [UserOut.model_validate(user) for user in users]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserOut:
    error = auth_service.password_strength_error(payload.password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    if session.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name or "",
        email=payload.email,
        password_hash=auth_service.hash_password(payload.password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    session.flush()
    audit.record(session, "user_created", user=admin, entity_type="user", entity_id=user.id,
                 details=user.username, ip_address=client_ip(request))
    session.commit()
    return UserOut.model_validate(user)


@router.get("/audit")
def audit_log(
    limit: int = 200,
    session: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> List[dict]:
    entries = (
        session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000)))
        .scalars()
        .all()
    )
    return [
        {
            "id": entry.id,
            "ts": entry.ts.isoformat(sep=" "),
            "username": entry.username,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "details": entry.details,
            "ip_address": entry.ip_address,
        }
        for entry in entries
    ]


@router.get("/api-keys", response_model=List[ApiKeyOut])
def list_api_keys(session: Session = Depends(get_db), _: User = Depends(require_admin)) -> List[ApiKeyOut]:
    keys = session.execute(select(ApiKey).order_by(ApiKey.id.desc())).scalars().all()
    return [ApiKeyOut.model_validate(key) for key in keys]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ApiKeyCreated:
    plain, prefix, key_hash = auth_service.generate_api_key()
    record = ApiKey(name=payload.name, prefix=prefix, key_hash=key_hash, created_by=admin.username, is_active=True)
    session.add(record)
    session.flush()
    audit.record(session, "api_key_created", user=admin, entity_type="api_key", entity_id=record.id,
                 details=payload.name, ip_address=client_ip(request))
    session.commit()
    return ApiKeyCreated(id=record.id, name=record.name, key=plain, prefix=prefix)


@router.delete("/api-keys/{key_id}", status_code=204)
def delete_api_key(key_id: int, session: Session = Depends(get_db), _: User = Depends(require_admin)) -> None:
    record = session.get(ApiKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="API key not found")
    session.delete(record)
    session.commit()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, session: Session = Depends(get_db), _: User = Depends(require_admin)) -> UserOut:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserOut:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    if "role" in data and data["role"] is not None:
        if data["role"] not in ("admin", "operator", "viewer"):
            raise HTTPException(status_code=400, detail="Unknown role")
        if user.id == admin.id and data["role"] != "admin":
            raise HTTPException(status_code=400, detail="You cannot remove your own admin role")
        user.role = data["role"]
    if "full_name" in data and data["full_name"] is not None:
        user.full_name = data["full_name"]
    if "email" in data:
        user.email = data["email"]
    if "is_active" in data and data["is_active"] is not None:
        if user.id == admin.id and not data["is_active"]:
            raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
        user.is_active = data["is_active"]
    if password:
        error = auth_service.password_strength_error(password)
        if error:
            raise HTTPException(status_code=400, detail=error)
        user.password_hash = auth_service.hash_password(password)
        user.must_change_password = True
    audit.record(session, "user_updated", user=admin, entity_type="user", entity_id=user.id,
                 details=",".join(sorted(data.keys())), ip_address=client_ip(request))
    session.commit()
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    username = user.username
    session.delete(user)
    audit.record(session, "user_deleted", user=admin, entity_type="user", entity_id=user_id,
                 details=username, ip_address=client_ip(request))
    session.commit()
