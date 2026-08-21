"""Activation plans and throwaway apply. Native homes stay refused."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any, Mapping, Optional

from kingstack.json_patch import merge_json
from kingstack.ownership import load_ownership, native_homes
from kingstack.toml_patch import owned_spans


class ActivationError(ValueError):
    """Raised when an activation plan is invalid or a live home is requested."""


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_native_home(path: Path, root: Path) -> bool:
    resolved = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    for name in native_homes(root):
        native = (home / name).resolve()
        if resolved == native or str(resolved).startswith(str(native) + os.sep):
            return True
    return False


def plan_activation(adapter: str, root: Path, native_home: Path, release_id: str, runtime: Optional[Path] = None) -> Mapping[str, Any]:
    owned = load_ownership(root, adapter)
    if runtime is None:
        raise ActivationError("activation plan requires a private runtime and a real release")
    release_dir = Path(runtime) / "adapters" / adapter / "releases" / release_id
    if not (release_dir / "manifest.json").is_file():
        raise ActivationError("unknown release")
    manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    release_files = {item["path"] for item in manifest.get("files", [])}
    home = Path(native_home)
    owned_rows = []
    for relative in owned["fully_owned"]:
        if not any(path == relative or path.startswith(relative + "/") for path in release_files):
            raise ActivationError("release is missing owned path {}".format(relative))
        owned_rows.append({"live": str(home / relative), "release": relative})
    mixed_rows = []
    for relative in owned["mixed"]:
        mixed_rows.append({"live": str(home / relative), "mode": "merge"})
    return {
        "schema_version": 1,
        "adapter": adapter,
        "release": release_id,
        "release_dir": str(release_dir),
        "native_home": str(home),
        "writes": False,
        "owned": owned_rows,
        "mixed": mixed_rows,
        "forbidden_untouched": [str(home / relative) for relative in owned["forbidden"]],
        "mixed_payloads": owned["mixed_payloads"],
    }


def apply_activation(plan: Mapping[str, Any], root: Path, fail_after: Optional[str] = None) -> Mapping[str, Any]:
    home = Path(plan["native_home"])
    if _is_native_home(home, root):
        raise ActivationError("live apply is forbidden until Hassan approves the pre-link briefing")
    if home.exists() and home.is_symlink():
        raise ActivationError("native home may not be a symbolic link")
    if any(_is_native_home(parent, root) for parent in home.parents):
        raise ActivationError("parent symlink refusal")
    home.mkdir(parents=True, exist_ok=True)
    marker = home / ".kingstack-activation.json"
    if marker.is_file():
        existing = json.loads(marker.read_text(encoding="utf-8"))
        if existing.get("release") == plan["release"] and existing.get("activated"):
            return existing
    release_dir = Path(plan["release_dir"])
    stamp = _stamp()
    preserved = []
    merged = []

    def _fail(point: str) -> None:
        if fail_after == point:
            raise ActivationError("injected failure after {}".format(point))

    try:
        _apply_body(plan, home, release_dir, stamp, preserved, merged, _fail)
    except Exception:
        rollback_activation({"native_home": str(home), "preserved": preserved, "merged": merged})
        raise
    result = {
        "schema_version": 1,
        "adapter": plan["adapter"],
        "release": plan["release"],
        "native_home": str(home),
        "preserved": preserved,
        "merged": merged,
        "activated": True,
    }
    marker.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _apply_body(plan, home, release_dir, stamp, preserved, merged, _fail):
    for item in plan["owned"]:
        live = Path(item["live"])
        source = release_dir / item["release"]
        if not source.exists():
            raise ActivationError("release is missing {}".format(item["release"]))
        if live.exists() or live.is_symlink():
            sibling = live.with_name(live.name + ".kingstack-" + stamp)
            if sibling.exists():
                raise ActivationError("occupied rollback destination")
            os.rename(live, sibling)
            preserved.append({"live": str(live), "original": str(sibling)})
            _fail("owned-rename")
        live.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, live)
        else:
            shutil.copy2(source, live)
        _fail("owned-publish")

    for item in plan["mixed"]:
        live = Path(item["live"])
        original_text = live.read_text(encoding="utf-8") if live.is_file() else ""
        if live.name == "config.toml":
            owned = json.loads((release_dir / "config-owned.json").read_text(encoding="utf-8"))
            text, snapshot = owned_spans(original_text, owned)
        elif live.name == "settings.json":
            text, snapshot = merge_json(original_text, {})
        else:
            raise ActivationError("unknown mixed file")
        if live.exists():
            sibling = live.with_name(live.name + ".kingstack-" + stamp)
            if sibling.exists():
                raise ActivationError("occupied rollback destination")
            os.rename(live, sibling)
            preserved.append({"live": str(live), "original": str(sibling)})
        live.write_text(text, encoding="utf-8")
        merged.append({"live": str(live), "snapshot": snapshot})
        _fail("mixed-publish")

    current = home / ".kingstack-current"
    if current.exists() or current.is_symlink():
        current.unlink()
    os.symlink(release_dir, current)
    _fail("current")


def rollback_activation(manifest: Mapping[str, Any], fail_after: Optional[str] = None) -> Mapping[str, Any]:
    home = Path(manifest["native_home"])
    for item in reversed(manifest.get("merged", [])):
        live = Path(item["live"])
        original = next((row["original"] for row in manifest["preserved"] if row["live"] == item["live"]), None)
        if original and Path(original).exists():
            if live.exists():
                live.unlink()
            os.rename(original, live)
        if fail_after == "mixed-rollback":
            raise ActivationError("injected failure after mixed-rollback")
    for item in reversed(manifest.get("preserved", [])):
        live = Path(item["live"])
        original = Path(item["original"])
        if item["live"] in {row["live"] for row in manifest.get("merged", [])}:
            continue
        if live.exists() or live.is_symlink():
            if live.is_dir() and not live.is_symlink():
                shutil.rmtree(live)
            else:
                live.unlink()
        if original.exists():
            os.rename(original, live)
        if fail_after == "owned-rollback":
            raise ActivationError("injected failure after owned-rollback")
    current = home / ".kingstack-current"
    if current.exists() or current.is_symlink():
        current.unlink()
    marker = home / ".kingstack-activation.json"
    if marker.exists():
        marker.unlink()
    return {"activated": False, "native_home": str(home)}
