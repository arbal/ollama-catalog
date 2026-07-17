"""Redact sensitive-looking third-party text before public persistence."""

from __future__ import annotations

import copy
import ipaddress
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REDACTED_CREDENTIAL = "[REDACTED_CREDENTIAL]"
REDACTED_EMAIL = "[REDACTED_EMAIL]"
REDACTED_INTERNAL_URL = "[REDACTED_INTERNAL_URL]"
REDACTED_PRIVATE_IP = "[REDACTED_PRIVATE_IP]"
REDACTED_PRIVATE_KEY = "[REDACTED_PRIVATE_KEY]"

_PRIVATE_KEY = re.compile(
    r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----.*?-----END(?: [A-Z]+)? PRIVATE KEY-----",
    re.DOTALL,
)
_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_CREDENTIAL = re.compile(
    r"\b(?:api[-_ ]?key|access[-_ ]?key|client[-_ ]?secret|secret|token|password|"
    r"passwd|authorization)\b\s*[:=]\s*(?:Bearer\s+)?[^\s,;\\\"'}]+",
    re.IGNORECASE,
)
_INTERNAL_URL = re.compile(
    r"https?://(?:localhost|(?:[A-Z0-9-]+\.)+(?:local|lan)|(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?::\d+)?[^\s'\\\"]*",
    re.IGNORECASE,
)
_IP = re.compile(
    r"(?<![\w.])(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"(?<![\w.])192\.168\.\d{1,3}\.\d{1,3}|"
    r"(?<![\w.])172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
)

# These fields are public identifiers or normalized scalar data. Every other
# field is untrusted upstream content and is recursively sanitized, including
# nested variant labels and any future free-text fields added by the scraper.
_IDENTITY_FIELDS = frozenset(
    {
        "slug",
        "name",
        "namespace",
        "model_type",
        "capabilities",
        "pulls",
        "pulls_text",
        "updated",
        "tags_count",
    }
)


@dataclass(frozen=True)
class SanitizationResult:
    """Counts returned after an offline JSONL sanitization pass."""

    records: int
    changed: int


def _replace_private_ip(match: re.Match[str]) -> str:
    try:
        address = ipaddress.ip_address(match.group(0))
        if address.is_private or match.group(0).startswith("127."):
            return REDACTED_PRIVATE_IP
        return match.group(0)
    except ValueError:
        return match.group(0)


def sanitize_text(value: str) -> str:
    """Return deterministic public-safe text without changing ordinary prose."""
    value = _PRIVATE_KEY.sub(REDACTED_PRIVATE_KEY, value)
    value = _INTERNAL_URL.sub(REDACTED_INTERNAL_URL, value)
    value = _CREDENTIAL.sub(REDACTED_CREDENTIAL, value)
    value = _EMAIL.sub(REDACTED_EMAIL, value)
    return _IP.sub(_replace_private_ip, value)


def _sanitize_untrusted_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_untrusted_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_untrusted_value(item) for key, item in value.items()}
    return value


def sanitize_model_record(model: dict[str, Any]) -> dict[str, Any]:
    """Copy a dynamic scraper record while sanitizing untrusted content."""
    # The scraper permits future upstream fields, so a structured model here
    # would either discard them or require synchronized parser releases.
    sanitized = copy.deepcopy(model)
    for field, value in sanitized.items():
        if field not in _IDENTITY_FIELDS:
            sanitized[field] = _sanitize_untrusted_value(value)
    return sanitized


def sanitize_models_jsonl(path: Path) -> SanitizationResult:
    """Rewrite a JSONL model file atomically and report its change counts."""
    records: list[dict[str, Any]] = []
    changed = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            safe_record = sanitize_model_record(record)
            changed += safe_record != record
            records.append(safe_record)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            for record in records:
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return SanitizationResult(records=len(records), changed=changed)
