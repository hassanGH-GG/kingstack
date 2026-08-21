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
