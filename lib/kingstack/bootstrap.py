"""Clone the reviewed kingstack repository without mutating agent homes."""

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from kingstack.inventory import capture_baseline, write_public_report
from kingstack.paths import Paths


class BootstrapError(RuntimeError):
    """Raised before bootstrap would violate its non-destructive contract."""


def _git(repo: Path, *arguments: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BootstrapError("git command failed: " + detail.strip()) from error
    return result.stdout.strip()


def _optional_git(repo: Path, *arguments: str) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _source_state(source_repo: Path) -> Dict[str, object]:
    if not source_repo.is_dir():
        raise BootstrapError("source repository is not a directory")
    if _git(source_repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BootstrapError("source repository has uncommitted changes")

    head = _git(source_repo, "rev-parse", "HEAD")
    branch = _git(source_repo, "rev-parse", "--abbrev-ref", "HEAD")
    origin = _optional_git(source_repo, "remote", "get-url", "origin")
    if not origin:
        raise BootstrapError("source repository has no origin remote")
    upstream = _optional_git(
        source_repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
    )
    if upstream:
        divergence = _git(
            source_repo, "rev-list", "--left-right", "--count", upstream + "...HEAD",
        ).split()
        behind, ahead = (int(divergence[0]), int(divergence[1]))
    else:
        ahead_text = _git(source_repo, "rev-list", "--count", "HEAD", "--not", "--remotes")
        behind, ahead = (0, int(ahead_text))

    return {
        "ahead": ahead,
        "behind": behind,
        "branch": branch,
        "head": head,
        "origin": origin,
        "tags": sorted(filter(None, _git(source_repo, "tag", "--list").splitlines())),
        "upstream": upstream,
    }


def _baseline_for_homes(baseline_homes: Iterable[Path]) -> dict:
    homes = [Path(path).expanduser().absolute() for path in baseline_homes]
    if any(path.is_symlink() or not path.is_dir() for path in homes):
        raise BootstrapError("baseline homes must be real directories, not symlinks")
    claude = [path for path in homes if path.name == ".claude"]
    codex = [path for path in homes if path.name == ".codex"]
    if len(claude) != 1 or len(codex) != 1 or len(homes) != 2:
        raise BootstrapError("baseline homes must be exactly one .claude and one .codex directory")
    paths = Paths(
        home=claude[0].parent,
        repo=claude[0].parent / "Desktop/Work/kingstack",
        runtime=claude[0].parent / ".kingstack",
        claude_home=claude[0],
        codex_home=codex[0],
    )
    baseline = capture_baseline(paths)
    _validate_public_baseline(baseline, homes)
    return baseline


def _validate_public_baseline(baseline: dict, private_roots: Iterable[Path]) -> None:
    encoded = json.dumps(baseline, sort_keys=True)
    for root in private_roots:
        if str(root) in encoded or str(root.parent) in encoded:
            raise BootstrapError("redacted baseline contains an absolute private path")

    allowed_record_keys = {"kind", "mode", "path", "sha256", "target"}
    for agent in ("claude", "codex"):
        section = baseline.get(agent)
        if not isinstance(section, dict):
            raise BootstrapError("redacted baseline has an invalid agent section")
        for record in section.get("records", []):
            if set(record) != allowed_record_keys:
                raise BootstrapError("redacted baseline has an unexpected record field")
            path = record.get("path")
            target = record.get("target")
            if not isinstance(path, str) or Path(path).is_absolute():
                raise BootstrapError("redacted baseline contains an absolute record path")
            if isinstance(target, str) and (
                target.startswith(("/", "\\", "~"))
                or re.match(r"^[A-Za-z]:[\\/]", target)
            ):
                raise BootstrapError("redacted baseline contains an absolute link target")


def _sha256_json(value: dict) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise BootstrapError("private runtime path is not a real directory: " + str(path))
    if path.exists():
        path.chmod(0o700)
        return
    path.mkdir(mode=0o700)
    path.chmod(0o700)


def _validate_private_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise BootstrapError("private runtime path is not a real directory: " + str(path))


def _write_private_manifest(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise BootstrapError("private bootstrap manifest already exists")
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(value, destination, indent=2, sort_keys=True)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def bootstrap(
    source_repo: Path,
    destination: Path,
    runtime: Path,
    baseline_homes: Iterable[Path],
    allow_unpushed: bool = False,
    dry_run: bool = False,
) -> dict:
    """Clone a clean reviewed repository and record redacted baseline evidence."""
    source_repo = Path(source_repo).expanduser().resolve()
    destination = Path(destination).expanduser().absolute()
    runtime = Path(runtime).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise BootstrapError("destination already exists; refusing to replace it")

    source = _source_state(source_repo)
    if source["ahead"] and not allow_unpushed:
        raise BootstrapError("source contains unpushed commits; pass --allow-unpushed explicitly")
    baseline = _baseline_for_homes(baseline_homes)
    public_report = destination / "docs/baselines/claude-codex-baseline.json"
    private_directory = runtime / "bootstrap"
    private_manifest = private_directory / "manifest.json"
    _validate_private_directory(runtime)
    _validate_private_directory(private_directory)
    if not dry_run and private_manifest.exists():
        raise BootstrapError("private bootstrap manifest already exists")

    would_write = [str(destination), str(public_report)]
    if not runtime.exists() or stat.S_IMODE(runtime.stat().st_mode) != 0o700:
        would_write.append(str(runtime))
    if not private_directory.exists():
        would_write.append(str(private_directory))
    would_write.append(str(private_manifest))
    result = {
        "baseline": baseline,
        "baseline_sha256": _sha256_json(baseline),
        "destination": str(destination),
        "dry_run": bool(dry_run),
        "source": source,
        "version": 1,
        "would_write": would_write,
    }
    if dry_run:
        return result

    try:
        subprocess.run(
            ["git", "clone", "--no-hardlinks", str(source_repo), str(destination)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BootstrapError("git clone failed: " + detail.strip()) from error

    _git(destination, "remote", "set-url", "origin", str(source["origin"]))
    _git(destination, "fetch", "--tags", "--force", "origin")
    if _git(destination, "rev-parse", "HEAD") != source["head"]:
        raise BootstrapError("clone HEAD does not match reviewed source HEAD")
    clone_tags = sorted(filter(None, _git(destination, "tag", "--list").splitlines()))
    if clone_tags != source["tags"]:
        raise BootstrapError("clone tags do not match reviewed source tags")
    _git(destination, "fsck", "--full")

    write_public_report(baseline, public_report)
    _ensure_private_directory(runtime)
    _ensure_private_directory(private_directory)
    _write_private_manifest(private_manifest, result)
    return result
