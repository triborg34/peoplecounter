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

    from PyQt6.QtWidgets import QApplication

    from .bootstrap import ensure_default_admin
    from .engine.runtime import EngineRuntime
    from .gui.login_dialog import LoginDialog
    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setOrganizationName("PeopleCounter")

    def _request_quit(_signum, _frame) -> None:
        """Ctrl+C in the console: leave the Qt loop so the shutdown code below
        runs instead of a KeyboardInterrupt blowing up inside a timer."""
        log.info("Interrupt received - shutting down")
        app.quit()

    signal.signal(signal.SIGINT, _request_quit)

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
