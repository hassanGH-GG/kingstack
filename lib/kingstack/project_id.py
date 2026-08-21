"""Stable project identity that is not a path basename."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
from typing import Optional


class ProjectIdError(ValueError):
    """Raised when a project identity cannot be derived safely."""


@dataclass(frozen=True)
class ProjectIdentity:
    id: str
    label: str
    root: str
    remote_fingerprint: Optional[str]


def _run_git(root: Path, args):
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _normalize_remote(url: str) -> str:
    value = url.strip()
    if value.endswith(".git"):
        value = value[:-4]
    value = value.replace("git@github.com:", "https://github.com/")
    return value.rstrip("/").lower()


def _digest(material: str) -> str:
    return "p_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def decode_claude_project_slug(name: str) -> Optional[Path]:
    """Turn Claude's hyphen-encoded cwd slug back into a real directory."""
    if not name.startswith("-"):
        return None
    parts = name[1:].split("-")
    current = Path("/")
    index = 0
    while index < len(parts):
        found = None
        for end in range(len(parts), index, -1):
            candidate = current / "-".join(parts[index:end])
            if candidate.exists():
                found = candidate
                index = end
                break
        if found is None:
            return None
        current = found
    return current if current.is_dir() else None


def identity_for_claude_bank(memory_dir: Path) -> ProjectIdentity:
    slug_dir = Path(memory_dir).resolve().parent
    decoded = decode_claude_project_slug(slug_dir.name)
    if decoded is not None:
        return project_identity(decoded)
    return ProjectIdentity(
        _digest("claude-project:" + slug_dir.name),
        slug_dir.name,
        str(slug_dir),
        None,
    )


def project_identity(root: Path) -> ProjectIdentity:
    root = Path(os.path.realpath(str(root)))
    if not root.is_dir():
        raise ProjectIdError("project root is not a directory: {}".format(root))
    label = root.name or "project"
    remote = _run_git(root, ["config", "--get", "remote.origin.url"])
    if remote:
        fingerprint = _normalize_remote(remote)
        return ProjectIdentity(_digest("remote:" + fingerprint), label, str(root), fingerprint)
    common = _run_git(root, ["rev-parse", "--git-common-dir"])
    if common:
        common_root = Path(os.path.realpath(str(Path(root, common) if not os.path.isabs(common) else common)))
        return ProjectIdentity(_digest("git-common:" + str(common_root)), label, str(root), None)
    return ProjectIdentity(_digest("path:" + str(root)), label, str(root), None)


def project_id(root: Path) -> str:
    return project_identity(root).id
