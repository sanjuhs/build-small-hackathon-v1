from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


def redact_endpoint_url(endpoint: str | None) -> str | None:
    """Keep public diagnostics useful without exposing owner-specific backend URLs."""
    if not endpoint:
        return None
    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if host in {"127.0.0.1", "localhost", "::1"}:
        return endpoint
    if host.endswith(".modal.run"):
        return "https://<modal-endpoint-redacted>"
    if host:
        return urlunparse((parsed.scheme, f"<{host}>", parsed.path or "", "", "", ""))
    return "<endpoint-redacted>"


def redact_endpoint_text(value: object) -> str:
    text = str(value)
    text = re.sub(r"https?://[^\s`\"']*\.modal\.run[^\s`\"']*", "https://<modal-endpoint-redacted>", text)
    return re.sub(r"[A-Za-z0-9-]+--[A-Za-z0-9-]+\.modal\.run", "<modal-endpoint-redacted>", text)
