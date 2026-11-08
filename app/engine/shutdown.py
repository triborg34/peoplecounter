"""Helpers for shutting many blocking workers down in parallel.

Camera captures can hang inside ``cv2.VideoCapture.read()`` / ``release()``
when an RTSP peer is gone.  Stopping the workers one after another would add
up to ``n * timeout`` on the GUI thread, so they are stopped concurrently and
the whole phase is bounded by one total budget.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Iterable, List

log = logging.getLogger(__name__)


def parallel_stop(workers: Iterable[Any], per_timeout: float = 2.0, max_total: float = 8.0) -> List[Any]:
    """Call ``worker.stop(timeout=per_timeout)`` on all workers at once.

    Returns the workers that did not finish within ``max_total`` seconds.  They
    run on daemon threads and will die with the process, but the caller can
    log them.
    """
    items = list(workers)
    if not items:
        return []

    def _stop_one(worker: Any) -> None:
        try:
            worker.stop(timeout=per_timeout)
        except Exception:  # pragma: no cover - a broken worker must not block others
            log.exception("Worker %r failed to stop", worker)

    threads: List[threading.Thread] = [
        threading.Thread(target=_stop_one, args=(worker,), name="stop-worker", daemon=True)
        for worker in items
    ]
    deadline = time.monotonic() + max(0.1, max_total)
    for thread in threads:
        thread.start()

    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)

    stuck = [worker for worker, thread in zip(items, threads) if thread.is_alive()]
    for worker in stuck:
        log.warning("Camera %r is still stopping after %.1fs", getattr(worker, "source", worker), max_total)
    return stuck
