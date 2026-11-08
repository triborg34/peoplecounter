"""Light / dark theming."""
from __future__ import annotations

from pathlib import Path

RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
THEMES = ("dark", "light")


def stylesheet_path(theme: str) -> Path:
    theme = theme if theme in THEMES else "dark"
    return RESOURCE_DIR / ("style_" + theme + ".qss")


def load_stylesheet(theme: str) -> str:
    path = stylesheet_path(theme)
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def apply_theme(app, theme: str) -> None:
    if app is None:
        return
    app.setStyleSheet(load_stylesheet(theme))


def current_theme(app) -> str:
    """The theme that is currently applied (dark when nothing is applied)."""
    if app is None:
        return "dark"
    sheet = app.styleSheet()
    return "light" if "#f5f6f8" in sheet else "dark"
