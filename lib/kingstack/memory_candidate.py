"""Versioned, adapter-neutral memory candidates."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Mapping

from kingstack.adapter_contract import ADAPTER_ID_PATTERN
from kingstack.secret_filter import reject_if_secret


class MemoryCandidateError(ValueError):
    """Raised when a candidate record is invalid."""


TYPES = ("user", "feedback", "project", "reference")
PROVENANCE = ("typed", "suggestion_accepted", "unknown")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_candidate(
    source_adapter: str,
    project_id: str,
    session_id: str,
    title: str,
    description: str,
    body: str,
    memory_type: str = "project",
    prompt_provenance: str = "typed",
    source_profile: str = "unknown",
) -> Mapping[str, object]:
    if ADAPTER_ID_PATTERN.fullmatch(source_adapter) is None:
        raise MemoryCandidateError("source_adapter must be a validated adapter id")
    if memory_type not in TYPES:
        raise MemoryCandidateError("unknown memory type")
    if prompt_provenance not in PROVENANCE:
        raise MemoryCandidateError("unknown prompt provenance")
    reject_if_secret("\n".join((title, description, body)))
    content_hash = _hash(body)
    session_hash = _hash(session_id)
    identity = {
        "source_adapter": source_adapter,
        "project_id": project_id,
        "content_hash": content_hash,
    }
    candidate_id = "c_" + _hash(json.dumps(identity, sort_keys=True))[:16]
    return {
        "schema": 1,
        "id": candidate_id,
        "source_adapter": source_adapter,
        "source_profile": source_profile,
        "project_id": project_id,
        "session_id_hash": session_hash,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": memory_type,
        "prompt_provenance": prompt_provenance,
        "content_hash": content_hash,
        "title": title,
        "description": description,
        "body": body,
    }
