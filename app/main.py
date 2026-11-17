"""Desktop application entry point.

    python -m app.main
"""
from __future__ import annotations

import logging
import signal
import sys

from .config import get_settings
from .logging_setup import setup_logging

log = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, settings.log_max_bytes, settings.log_backup_count)

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    from .bootstrap import ensure_default_admin
    from .engine.runtime import EngineRuntime
    from .gui.login_dialog import LoginDialog
    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setOrganizationName("PeopleCounter")

    def _request_quit(_signum=None, _frame=None) -> None:
        """Ctrl+C in the console or termination: exit Qt event loop cleanly."""
        log.info("Interrupt / termination signal received - shutting down gracefully")
        app.quit()

    signal.signal(signal.SIGINT, _request_quit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_quit)

    # Periodic timer so the Python interpreter periodically runs bytecode,
    # allowing Python signal handlers to execute when Ctrl+C is pressed on Windows/Linux.
    sigint_timer = QTimer()
    sigint_timer.timeout.connect(lambda: None)
    sigint_timer.start(300)

    runtime = EngineRuntime(settings)
    runtime.start()
    ensure_default_admin(runtime.db, settings)

    from .gui.theme import apply_theme

    apply_theme(app, "dark")

    dialog = LoginDialog(runtime)
    if dialog.exec() != LoginDialog.DialogCode.Accepted:
        runtime.stop()
        return 1

    window = MainWindow(runtime, dialog.user, app)
    window.show()

    try:
        return app.exec()
    finally:
        try:
            window.shutdown()
        except Exception:  # pragma: no cover
            log.exception("Failed to shut the main window down")
        runtime.stop()


if __name__ == "__main__":
    sys.exit(main())
