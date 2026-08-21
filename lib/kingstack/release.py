"""Immutable content-addressed releases under a private runtime."""

import hashlib
import json
import os
from pathlib import Path
from typing import List, Mapping


class ReleaseError(ValueError):
    """Raised when a release cannot be built or retargeted safely."""


def assert_private_runtime(runtime: Path, root: Path = None) -> Path:
    from kingstack.ownership import native_homes

    resolved = Path(runtime).expanduser().resolve()
    home = Path.home().resolve()
    repo = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    for name in native_homes(repo):
        native = (home / name).resolve()
        if resolved == native or str(resolved).startswith(str(native) + os.sep):
            raise ReleaseError("refusing native home {}".format(native))
    return resolved


def _digest(bundle: Mapping[str, bytes]) -> str:
    material = hashlib.sha256()
    for path, content in bundle.items():
        material.update(path.encode("utf-8"))
        material.update(b"\0")
        material.update(hashlib.sha256(content).digest())
    return material.hexdigest()


def _release_dir(runtime: Path, adapter: str, release_id: str) -> Path:
    return Path(runtime) / "adapters" / adapter / "releases" / release_id


def _current(runtime: Path, adapter: str) -> Path:
    return Path(runtime) / "adapters" / adapter / "current"


def build_release(adapter: str, root: Path, runtime: Path) -> Mapping[str, object]:
    from kingstack.render import render_bundle

    runtime = assert_private_runtime(runtime)
    bundle = render_bundle(adapter, root)
    digest = _digest(bundle)
    destination = _release_dir(runtime, adapter, digest)
    if (destination / "manifest.json").is_file():
        return json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    staging = destination.with_name(digest + ".staging")
    if staging.exists():
        raise ReleaseError("release staging path already exists")
    staging.mkdir(parents=True, mode=0o700)
    files = []
    for path, content in bundle.items():
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        os.chmod(target, 0o600)
        files.append({"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {
        "schema_version": 1,
        "adapter": adapter,
        "id": digest,
        "activated": False,
        "files": files,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.rename(staging, destination)
    os.chmod(destination, 0o700)
    return manifest


def list_releases(adapter: str, runtime: Path) -> List[Mapping[str, object]]:
    runtime = assert_private_runtime(runtime)
    root = Path(runtime) / "adapters" / adapter / "releases"
    if not root.is_dir():
        return []
    records = []
    current = _current(runtime, adapter)
    current_id = current.resolve().name if current.is_symlink() or current.exists() else None
    for path in sorted(root.iterdir()):
        manifest = path / "manifest.json"
        if not manifest.is_file():
            continue
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["current"] = record.get("id") == current_id
        records.append(record)
    return records


def select_release(adapter: str, runtime: Path, release_id: str) -> Mapping[str, object]:
    runtime = assert_private_runtime(runtime)
    destination = _release_dir(runtime, adapter, release_id)
    if not (destination / "manifest.json").is_file():
        raise ReleaseError("unknown release")
    current = _current(runtime, adapter)
    current.parent.mkdir(parents=True, exist_ok=True)
    tmp = current.with_name("current.tmp")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    os.symlink(destination, tmp)
    os.replace(tmp, current)
    return {"adapter": adapter, "id": release_id, "activated": True, "path": str(current)}


def rollback_release(adapter: str, runtime: Path, to_id: str) -> Mapping[str, object]:
    runtime = assert_private_runtime(runtime)
    current = _current(runtime, adapter)
    if not current.exists() and not current.is_symlink():
        raise ReleaseError("nothing activated under this private runtime")
    if current.resolve() == _release_dir(runtime, adapter, to_id).resolve():
        return {"adapter": adapter, "id": to_id, "activated": True, "unchanged": True}
    return select_release(adapter, runtime, to_id)
