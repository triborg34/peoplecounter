"""First run bootstrap: create the default administrator account."""
from __future__ import annotations

import logging

from sqlalchemy import select

from .config import Settings, get_settings
from .db.models import User
from .db.session import Database
from .services.auth import hash_password

log = logging.getLogger(__name__)


def ensure_default_admin(db: Database, settings: Settings = None) -> User:
    """Create the default admin on first run (forces a password change)."""
    settings = settings or get_settings()
    with db.session_scope() as session:
        existing = session.execute(select(User).where(User.username == settings.default_admin_username)).scalars().first()
        if existing is not None:
            return existing
        admin = User(
            username=settings.default_admin_username,
            full_name="Administrator",
            email=None,
            password_hash=hash_password(settings.default_admin_password),
            role="admin",
            is_active=True,
            must_change_password=settings.force_password_change,
        )
        session.add(admin)
        log.warning(
            "Created default admin user '%s' - change the password after the first login",
            settings.default_admin_username,
        )
        session.flush()
        return admin
