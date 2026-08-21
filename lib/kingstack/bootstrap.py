"""Clone the reviewed kingstack repository without mutating agent homes."""

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

from kingstack.inventory import (
    atomic_write_no_clobber,
    capture_baseline,
    open_directory_no_symlinks,
    write_public_report_at,
)
from kingstack.paths import Paths


class BootstrapError(RuntimeError):
    """Raised before bootstrap would violate its non-destructive contract."""


RepoLocation = Union[Path, int]


def _git_process(repo: RepoLocation, arguments: Iterable[str], check: bool):
    if isinstance(repo, int):
        def enter_held_directory() -> None:
            os.fchdir(repo)

        return subprocess.run(
            ["git", *arguments],
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=enter_held_directory,
            pass_fds=(repo,),
        )
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git(repo: RepoLocation, *arguments: str, check: bool = True) -> str:
    try:
        result = _git_process(repo, arguments, check)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BootstrapError("git command failed: " + detail.strip()) from error
    return result.stdout.strip()


def _optional_git(repo: RepoLocation, *arguments: str) -> Optional[str]:
    result = _git_process(repo, arguments, False)
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
        "remote_refs": _remote_refs(source_repo),
        "tags": sorted(filter(None, _git(source_repo, "tag", "--list").splitlines())),
        "upstream": upstream,
    }


def _remote_refs(repo: RepoLocation) -> List[dict]:
    output = _git(
        repo,
        "for-each-ref",
        "--format=%(refname)%09%(objectname)%09%(symref)",
        "refs/remotes",
    )
    records = []
    for line in output.splitlines():
        if not line:
            continue
        name, object_id, symbolic_target = (line.split("\t") + ["", ""])[:3]
        records.append(
            {"name": name, "object": object_id, "symbolic_target": symbolic_target or None}
        )
    return records


def _reconcile_remote_refs(repo: RepoLocation, expected: List[dict]) -> None:
    for record in _remote_refs(repo):
        if record["symbolic_target"]:
            _git(repo, "symbolic-ref", "--delete", str(record["name"]))
        else:
            _git(repo, "update-ref", "-d", str(record["name"]))
    for record in expected:
        if not record["symbolic_target"]:
            _git(repo, "update-ref", str(record["name"]), str(record["object"]))
    for record in expected:
        if record["symbolic_target"]:
            _git(repo, "symbolic-ref", str(record["name"]), str(record["symbolic_target"]))


def _reconcile_upstream(repo: RepoLocation, branch: str, expected: Optional[str]) -> None:
    current = _optional_git(
        repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
    )
    if expected:
        _git(repo, "branch", "--set-upstream-to=" + expected, branch)
    elif current:
        _git(repo, "branch", "--unset-upstream", branch)


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


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _validate_no_symlink_components(path: Path, require_leaf: bool = False) -> None:
    path = Path(path).expanduser().absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            details = current.lstat()
        except FileNotFoundError:
            if require_leaf:
                raise BootstrapError("required output parent does not exist: " + str(path))
            return
        if stat.S_ISLNK(details.st_mode):
            raise BootstrapError("refusing symlinked output path: " + str(current))
        if not stat.S_ISDIR(details.st_mode):
            raise BootstrapError("output path component is not a directory: " + str(current))


def _validate_output_boundaries(
    destination: Path, runtime: Path, baseline_homes: Iterable[Path]
) -> None:
    homes = [Path(path).expanduser().absolute() for path in baseline_homes]
    _validate_no_symlink_components(destination.parent, require_leaf=True)
    _validate_no_symlink_components(runtime)
    try:
        native_identities = [path.resolve(strict=True) for path in homes]
        destination_identity = destination.parent.resolve(strict=True) / destination.name
        runtime_identity = runtime.resolve(strict=False)
    except OSError as error:
        raise BootstrapError("cannot resolve managed path identity: " + str(error)) from error
    for owned in (destination_identity, runtime_identity):
        for native in native_identities:
            if _paths_overlap(owned, native):
                raise BootstrapError("managed output paths must not overlap native agent homes")
    if _paths_overlap(destination_identity, runtime_identity):
        raise BootstrapError("destination and runtime paths must not overlap")


def _assert_directory_identity(path: Path, descriptor: int) -> None:
    held = os.fstat(descriptor)
    try:
        current = os.stat(path, follow_symlinks=False)
    except FileNotFoundError as error:
        raise BootstrapError("destination parent changed during bootstrap") from error
    if (
        not stat.S_ISDIR(current.st_mode)
        or current.st_dev != held.st_dev
        or current.st_ino != held.st_ino
    ):
        raise BootstrapError("destination parent changed during bootstrap")


def _assert_destination_absent(parent_fd: int, name: str) -> None:
    if name in {"", ".", ".."} or "/" in name or "\\" in name:
        raise BootstrapError("destination must have a safe leaf name")
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise BootstrapError("destination already exists; refusing to replace it")


def _create_clone_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o755, dir_fd=parent_fd)
    except FileExistsError as error:
        raise BootstrapError("destination already exists; refusing to replace it") from error
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise BootstrapError("cannot open reserved clone destination") from error
    os.fchmod(descriptor, 0o755)
    return descriptor


def _clone_into_held_directory(source_repo: Path, destination_fd: int) -> None:
    try:
        _git_process(
            destination_fd,
            ["clone", "--no-hardlinks", str(source_repo), "."],
            True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise BootstrapError("git clone failed: " + detail.strip()) from error


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
    try:
        descriptor = open_directory_no_symlinks(path, create=True, mode=0o700)
    except ValueError as error:
        raise BootstrapError(str(error)) from error
    try:
        os.fchmod(descriptor, 0o700)
    finally:
        os.close(descriptor)


def _validate_private_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise BootstrapError("private runtime path is not a real directory: " + str(path))


def _write_private_manifest(path: Path, value: dict) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        atomic_write_no_clobber(path, payload, mode=0o600)
    except ValueError as error:
        raise BootstrapError(str(error)) from error


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
    baseline_homes = [Path(path).expanduser().absolute() for path in baseline_homes]
    _validate_output_boundaries(destination, runtime, baseline_homes)
    try:
        parent_fd = open_directory_no_symlinks(destination.parent)
    except ValueError as error:
        raise BootstrapError(str(error)) from error
    try:
        _assert_directory_identity(destination.parent, parent_fd)
        _assert_destination_absent(parent_fd, destination.name)

        source = _source_state(source_repo)
        if source["ahead"] and not allow_unpushed:
            raise BootstrapError(
                "source contains unpushed commits; pass --allow-unpushed explicitly"
            )
        baseline = _baseline_for_homes(baseline_homes)
        public_report = destination / "docs/baselines/claude-codex-baseline.json"
        private_directory = runtime / "bootstrap"
        private_manifest = private_directory / "manifest.json"
        _validate_private_directory(runtime)
        _validate_private_directory(private_directory)
        if not dry_run and (private_manifest.exists() or private_manifest.is_symlink()):
            raise BootstrapError("private bootstrap manifest already exists")

        _assert_directory_identity(destination.parent, parent_fd)
        _assert_destination_absent(parent_fd, destination.name)
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

        clone_fd = _create_clone_directory(parent_fd, destination.name)
        try:
            _clone_into_held_directory(source_repo, clone_fd)
            _git(clone_fd, "remote", "set-url", "origin", str(source["origin"]))
            _git(clone_fd, "fetch", "--tags", "--force", "origin")
            _reconcile_remote_refs(clone_fd, source["remote_refs"])
            _reconcile_upstream(clone_fd, str(source["branch"]), source["upstream"])
            if _git(clone_fd, "rev-parse", "HEAD") != source["head"]:
                raise BootstrapError("clone HEAD does not match reviewed source HEAD")
            clone_tags = sorted(filter(None, _git(clone_fd, "tag", "--list").splitlines()))
            if clone_tags != source["tags"]:
                raise BootstrapError("clone tags do not match reviewed source tags")
            if _remote_refs(clone_fd) != source["remote_refs"]:
                raise BootstrapError("clone remote-tracking refs do not match reviewed source")
            clone_upstream = _optional_git(
                clone_fd,
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            )
            if clone_upstream != source["upstream"]:
                raise BootstrapError("clone upstream does not match reviewed source")
            _git(clone_fd, "fsck", "--full")

            try:
                write_public_report_at(
                    baseline,
                    clone_fd,
                    Path("docs/baselines/claude-codex-baseline.json"),
                )
            except ValueError as error:
                raise BootstrapError(str(error)) from error
        finally:
            os.close(clone_fd)

        _ensure_private_directory(runtime)
        _ensure_private_directory(private_directory)
        _assert_directory_identity(destination.parent, parent_fd)
        _write_private_manifest(private_manifest, result)
        return result
    finally:
        try:
            os.close(parent_fd)
        except OSError:
            # Closing the held identity cannot invalidate a published success.
            pass
