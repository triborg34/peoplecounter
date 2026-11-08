"""Camera source helpers: RTSP URL construction and credential handling."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, unquote, urlparse

log = logging.getLogger(__name__)

DEFAULT_RTSP_PORTS = (554, 8554, 80, 443)


@dataclass
class ParsedSource:
    scheme: str = "rtsp"
    host: str = ""
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    path: str = ""
    query: str = ""


def build_rtsp_url(
    host: str,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    path: str = "",
    scheme: str = "rtsp",
) -> str:
    """Build rtsp://user:pass@host:port/path with URL encoded credentials."""
    host = (host or "").strip()
    if not host:
        raise ValueError("host is required")
    if "://" in host:  # the user pasted a full url into the host field
        host = host.split("://", 1)[1]

    credentials = ""
    if username:
        credentials = quote(str(username), safe="")
        if password:
            credentials += ":" + quote(str(password), safe="")
        credentials += "@"

    netloc = host
    if port:
        netloc = host + ":" + str(int(port))

    path = path or ""
    if path and not path.startswith("/"):
        path = "/" + path
    return scheme + "://" + credentials + netloc + path


def parse_source(url: str) -> ParsedSource:
    """Split an RTSP url into its parts (credentials are decoded)."""
    if not url:
        return ParsedSource()
    parsed = urlparse(url)
    scheme = parsed.scheme or "rtsp"
    host = parsed.hostname or ""
    port = parsed.port
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    path = parsed.path or ""
    if port is None:
        port = 554 if scheme in ("rtsp", "rtsps") else None
    return ParsedSource(
        scheme=scheme, host=host, port=port, username=username, password=password,
        path=path, query=parsed.query,
    )


def strip_credentials(url: str) -> str:
    """Return the url without embedded credentials (for safe storage)."""
    parsed = urlparse(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = netloc + ":" + str(parsed.port)
    return parsed.scheme + "://" + netloc + parsed.path


def describe_source(url: str) -> str:
    """A log/display safe description of a stream url."""
    try:
        parsed = parse_source(url)
        return parsed.scheme + "://" + parsed.host + ":" + str(parsed.port or "-") + parsed.path
    except Exception:
        return "<invalid url>"
