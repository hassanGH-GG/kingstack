"""Reject secret-like content without echoing matched values."""

import math
import re
from typing import List, Tuple


class SecretFilterError(ValueError):
    """Raised when candidate content looks like a secret."""


_PREFIXES = (
    "sk-",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "xoxp-",
    "AKIA",
)
_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|token|private[_-]?key)\s*[:=]\s*(\S+)"
)
_URL_CREDS = re.compile(r"://[^/\s:]+:[^/\s@]+@")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_ALLOW_NAMES = {"POSTHOG_KEY", "SENTRY_DSN_NAME", "API_KEY_NAME"}


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    return -sum((n / len(value)) * math.log2(n / len(value)) for n in counts.values())


def inspect(text: str) -> List[Tuple[str, str]]:
    """Return (category, location) pairs. Never return matched secret values."""
    hits = []
    if _PRIVATE_KEY.search(text):
        hits.append(("private_key", "body"))
    if _URL_CREDS.search(text):
        hits.append(("url_credentials", "body"))
    for prefix in _PREFIXES:
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(prefix), text):
            hits.append(("token_prefix", "body"))
            break
    for match in _ASSIGNMENT.finditer(text):
        name = match.group(1).upper().replace("-", "_")
        if name in _ALLOW_NAMES or match.group(0).split()[0].strip(":=").upper() in _ALLOW_NAMES:
            continue
        value = match.group(2)
        if len(value) >= 12:
            hits.append(("assignment", "body"))
    tokens = re.findall(r"[A-Za-z0-9+/=_-]{24,}", text)
    for token in tokens:
        if any(name in text and token not in name for name in _ALLOW_NAMES):
            continue
        if _entropy(token) >= 4.2:
            hits.append(("high_entropy", "body"))
            break
    return hits


def reject_if_secret(text: str) -> None:
    hits = inspect(text)
    if hits:
        categories = ",".join(sorted({item[0] for item in hits}))
        raise SecretFilterError("secret-like content rejected ({})".format(categories))
