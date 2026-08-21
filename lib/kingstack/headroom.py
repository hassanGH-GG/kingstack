"""Pinned Headroom absorb: lossless CCR for large tool text. No wrap."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Mapping, Optional

from kingstack.memory_store import _atomic_write
from kingstack.ownership import native_homes


PIN_NAME = "headroom-upstream.txt"
DEFAULT_CHECKOUT = Path.home() / "Desktop/Work/headroom"
STORE_NAME = "headroom"
ERROR_RE = re.compile(r"error|fatal|exception|failed|critical", re.I)
HEAD = 20
TAIL = 20
LINE_CAP = 400


class HeadroomError(ValueError):
    """Raised when the Headroom pin, store, or retrieve path is invalid."""


def pin_revision(root: Path) -> str:
    first = (Path(root) / PIN_NAME).read_text(encoding="utf-8").splitlines()[0].strip()
    if not first:
        raise HeadroomError("headroom pin is empty")
    return first


def checkout_revision(checkout: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), "log", "-1", "--format=%h"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise HeadroomError("cannot inspect headroom checkout: {}".format(error)) from error
    actual = result.stdout.strip()
    if not actual:
        raise HeadroomError("headroom checkout has no revision")
    return actual


def check_pin(root: Path, checkout: Optional[Path] = None) -> Mapping[str, str]:
    expected = pin_revision(root)
    source = Path(checkout) if checkout is not None else Path(root).resolve().parent / "headroom"
    actual = checkout_revision(source)
    if actual != expected:
        raise HeadroomError(
            "headroom revision drift: pin {} != checkout {}".format(expected, actual)
        )
    return {"upstream": "headroom", "revision": actual, "status": "clean"}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def default_store() -> Path:
    override = os.environ.get("KINGSTACK_HEADROOM_ROOT")
    if override:
        return Path(override)
    return Path.home() / ".kingstack" / STORE_NAME


def assert_private_store(store: Path, root: Path) -> Path:
    resolved = Path(store).expanduser().resolve()
    home = Path.home().resolve()
    for name in native_homes(root):
        native = (home / name).resolve()
        if resolved == native or str(resolved).startswith(str(native) + os.sep):
            raise HeadroomError("refusing native home {}".format(native))
    return resolved


def archive_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _digest_lines(text: str) -> str:
    lines = text.splitlines()
    keep = {}
    for index, line in enumerate(lines):
        if ERROR_RE.search(line):
            for nearby in range(max(0, index - 2), min(len(lines), index + 3)):
                keep[nearby] = lines[nearby]
    for index in range(min(HEAD, len(lines))):
        keep[index] = lines[index]
    for index in range(max(0, len(lines) - TAIL), len(lines)):
        keep[index] = lines[index]
    ordered = [_cap_line(keep[index]) for index in sorted(keep)]
    return "\n".join(ordered)


def _cap_line(line: str) -> str:
    if len(line) <= LINE_CAP:
        return line
    match = ERROR_RE.search(line)
    if match:
        start = max(0, match.start() - 40)
        end = min(len(line), match.end() + 80)
        return (
            line[:80]
            + " … "
            + line[start:end]
            + " …[{} chars omitted]… ".format(len(line) - LINE_CAP)
            + line[-40:]
        )
    return line[:LINE_CAP] + " …[{} chars omitted]… ".format(len(line) - LINE_CAP) + line[-80:]


def crush(text: str, store: Path, root: Path, tool: str = "tool") -> Mapping[str, object]:
    store = assert_private_store(store, root)
    store.mkdir(parents=True, exist_ok=True)
    identity = archive_id(text)
    original_path = store / "{}.txt".format(identity)
    original_path.write_text(text, encoding="utf-8")
    digest = _digest_lines(text)
    tokens_in = estimate_tokens(text)
    tokens_out = estimate_tokens(digest)
    record = {
        "id": identity,
        "tool": tool,
        "bytes": len(text.encode("utf-8")),
        "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "saved": max(0, tokens_in - tokens_out),
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (store / "{}.meta.json".format(identity)).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    record_live(store, identity)
    notice = (
        "headroom archived {tool} output id={identity} "
        "tokens {tokens_in} -> {tokens_out} (saved {saved}). "
        "Do not keep the raw blob in the thread. "
        "Retrieve with `kingstack headroom retrieve {identity}`.\n\n"
        "{digest}\n"
    ).format(tool=tool, identity=identity, tokens_in=tokens_in, tokens_out=tokens_out, saved=record["saved"], digest=digest)
    record["notice"] = notice
    return record


def retrieve(identity: str, store: Path, root: Path) -> str:
    store = assert_private_store(store, root)
    if not re.fullmatch(r"[0-9a-f]{16}", identity):
        raise HeadroomError("invalid headroom id")
    path = store / "{}.txt".format(identity)
    if not path.is_file():
        raise HeadroomError("unknown headroom id")
    return path.read_text(encoding="utf-8")


def live_path(store: Path) -> Path:
    return Path(store) / "live.json"


def record_live(store: Path, identity: str) -> Mapping[str, object]:
    path = live_path(store)
    payload = {"ids": live_ids(store)}
    if identity not in payload["ids"]:
        payload["ids"].append(identity)
    _atomic_write(path, json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n")
    return payload


def live_ids(store: Path) -> list:
    path = live_path(store)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return list(payload.get("ids") or [])
    return sorted(path.stem.replace(".meta", "") for path in Path(store).glob("*.meta.json"))


def stats(store: Path, root: Path) -> Mapping[str, object]:
    store = assert_private_store(store, root)
    if not store.is_dir():
        return {"archives": 0, "tokens_in": 0, "tokens_out": 0, "saved": 0}
    tokens_in = tokens_out = saved = count = 0
    for path in store.glob("*.meta.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        count += 1
        tokens_in += int(record.get("tokens_in") or 0)
        tokens_out += int(record.get("tokens_out") or 0)
        saved += int(record.get("saved") or 0)
    return {
        "archives": count,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "saved": saved,
    }
