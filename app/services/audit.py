"""Audit log of important actions."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db.models import AuditLog, User

log = logging.getLogger(__name__)


def record(
    session: Session,
    action: str,
    user: Optional[User] = None,
    username: str = "",
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Any = "",
    ip_address: str = "",
) -> AuditLog:
    entry = AuditLog(
        user_id=user.id if user else None,
        username=username or (user.username if user else ""),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=str(details) if not isinstance(details, str) else details,
        ip_address=ip_address or "",
    )
    session.add(entry)
    log.info("audit %s by %s", action, entry.username)
    return entry
