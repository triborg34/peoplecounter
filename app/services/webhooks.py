"""Optional webhooks fired on every counting event."""
from __future__ import annotations

import json
import logging
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from ..config import Settings, get_settings
from ..engine.types import CountEvent

log = logging.getLogger(__name__)


class WebhookDispatcher:
    """Posts count events to the configured webhook urls."""

    def __init__(self, settings: Optional[Settings] = None, max_workers: int = 4):
        self.settings = settings or get_settings()
        self.urls: List[str] = list(self.settings.webhook_urls or [])
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="webhook")

    @property
    def enabled(self) -> bool:
        return bool(self.urls)

    def dispatch(self, event: CountEvent) -> None:
        if not self.urls:
            return
        payload = json.dumps({"event": "count", "data": event.to_dict()}).encode("utf-8")
        for url in self.urls:
            self._pool.submit(self._post, url, payload)

    def _post(self, url: str, payload: bytes) -> None:
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "PeopleCounter/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.webhook_timeout_s) as response:
                response.read()
        except Exception as exc:
            log.warning("Webhook to %s failed: %s", url, exc)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)


_dispatcher: Optional[WebhookDispatcher] = None
_lock = threading.Lock()


def get_dispatcher(settings: Optional[Settings] = None) -> WebhookDispatcher:
    global _dispatcher
    with _lock:
        if _dispatcher is None:
            _dispatcher = WebhookDispatcher(settings)
        return _dispatcher
