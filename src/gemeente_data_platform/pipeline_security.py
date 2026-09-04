"""Redactie van operationele pipeline-informatie vóór persistente logging."""

from __future__ import annotations

import re

MARKER = "[REDACTED]"


def redact(value: str, secrets: tuple[str, ...] = ()) -> str:
    """Verwijder credentials, URL-wachtwoorden en bekende secretpaden."""
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, MARKER)
    result = re.sub(
        r"([a-z][a-z0-9+.-]*://[^:/\s]+:)[^@\s]+(@)",
        rf"\1{MARKER}\2",
        result,
    )
    result = re.sub(
        r"(?i)(password|token|secret)\s*=\s*[^\s,;]+",
        rf"\1={MARKER}",
        result,
    )
    return re.sub(r"(?i)([A-Z]:\\|/)[^\s]*?(secrets?|password)[^\s]*", MARKER, result)
