"""Deterministic rendering for agent instruction files."""

import json
import os
from pathlib import Path
from typing import List

from kingstack.adapter_contract import (
    ADAPTER_ID_PATTERN,
    AdapterContractError,
    load_adapter,
    load_capability_catalog,
    validate_adapter,
)


class RenderError(ValueError):
    """Raised when instruction sources or staged output violate the contract."""


def _decode_utf8(path: Path, label: str, allow_empty: bool = False) -> str:
    try:
        content = path.read_bytes()
    except FileNotFoundError as error:
        raise RenderError("missing {}: {}".format(label, path)) from error
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RenderError("{} must be valid UTF-8: {}".format(label, path)) from error
    if allow_empty and not content:
        return ""
    if not content.endswith(b"\n") or content.endswith(b"\n\n"):
        raise RenderError("{} must end with exactly one trailing newline: {}".format(label, path))
    return text


def _load_order(instructions: Path) -> List[str]:
    order_path = instructions / "order.json"
    try:
        order = json.loads(order_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RenderError("missing instruction order: {}".format(order_path)) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RenderError("invalid instruction order: {}".format(error)) from error
    if not isinstance(order, list) or not all(isinstance(name, str) for name in order):
        raise RenderError("instruction order must be an array of fragment filenames")
    if len(order) != len(set(order)):
        raise RenderError("instruction order contains a duplicate fragment")
    for name in order:
        if Path(name).name != name or not name.endswith(".md"):
            raise RenderError("instruction order contains an invalid fragment name: {}".format(name))
    actual = {path.name for path in instructions.glob("*.md") if path.is_file()}
    listed = set(order)
    missing = sorted(listed - actual)
    unlisted = sorted(actual - listed)
    if missing:
        raise RenderError("instruction order names missing fragments: {}".format(", ".join(missing)))
    if unlisted:
        raise RenderError("instruction directory contains unlisted fragments: {}".format(", ".join(unlisted)))
    return order


def _load_declaration(adapter: str, root: Path):
    if not isinstance(adapter, str) or ADAPTER_ID_PATTERN.fullmatch(adapter) is None:
        raise RenderError("adapter must be a stable adapter ID")
    adapters = root / "adapters"
    adapter_directory = adapters / adapter
    adapter_file = adapter_directory / "adapter.json"
    for path in (adapters, adapter_directory, adapter_file):
        if path.is_symlink():
            raise RenderError("adapter selection may not traverse a symbolic link: {}".format(path))
    expected_parent = adapter_directory
    try:
        resolved_parent = adapter_file.parent.resolve()
    except OSError as error:
        raise RenderError("cannot resolve adapter '{}': {}".format(adapter, error)) from error
    if resolved_parent != expected_parent:
        raise RenderError("adapter selection escapes the canonical adapter directory")
    try:
        declaration = load_adapter(adapter_file)
        catalog = load_capability_catalog(root / "core/capabilities/catalog.json")
        errors = validate_adapter(declaration, catalog)
    except AdapterContractError as error:
        raise RenderError("invalid adapter '{}': {}".format(adapter, error)) from error
    if declaration.id != adapter:
        raise RenderError(
            "adapter selector '{}' loaded declaration id '{}'".format(adapter, declaration.id)
        )
    if errors:
        raise RenderError("invalid adapter '{}': {}".format(adapter, "; ".join(errors)))
    return declaration


def render_instructions(adapter: str, root: Path) -> str:
    """Render ordered shared fragments and the selected adapter appendix."""
    root = Path(root).resolve()
    _load_declaration(adapter, root)
    instructions = root / "core/instructions"
    order = _load_order(instructions)
    body = "".join(
        _decode_utf8(instructions / name, "instruction fragment") for name in order
    )
    appendix = _decode_utf8(
        root / "adapters" / adapter / "instructions-appendix.md",
        "adapter instruction appendix",
        allow_empty=True,
    )
    return body + appendix


def _instruction_filename(adapter: str, declaration) -> str:
    expected = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}.get(adapter)
    if expected is None or expected not in declaration.owned_paths:
        raise RenderError("adapter '{}' does not declare an owned instruction file".format(adapter))
    return expected


def _ensure_not_symlink(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise RenderError("staged output may not contain a symbolic link: {}".format(path))


def write_staged_instructions(adapter: str, output: Path, root: Path) -> Path:
    """Write one rendered instruction file into the adapter's confined staging dir."""
    supplied_root = Path(root)
    supplied_output = Path(output)
    root = supplied_root.resolve()
    declaration = _load_declaration(adapter, root)
    expected = root / ".staging" / adapter
    if supplied_output.is_absolute():
        try:
            relative_output = supplied_output.relative_to(supplied_root)
        except ValueError as error:
            raise RenderError("output must be inside the canonical repository") from error
        candidate = Path(os.path.abspath(str(root / relative_output)))
    else:
        candidate = Path(os.path.abspath(str(root / supplied_output)))
    if candidate != expected:
        raise RenderError("output must be the adapter staging directory: {}".format(expected))

    staging = root / ".staging"
    _ensure_not_symlink(staging)
    _ensure_not_symlink(candidate)
    if candidate.exists():
        if not candidate.is_dir():
            raise RenderError("staged output exists and is not a directory: {}".format(candidate))
        if any(candidate.iterdir()):
            raise RenderError("staged output directory is not empty: {}".format(candidate))
    else:
        staging.mkdir(mode=0o700, exist_ok=True)
        _ensure_not_symlink(staging)
        candidate.mkdir(mode=0o700)

    destination = candidate / _instruction_filename(adapter, declaration)
    _ensure_not_symlink(destination)
    content = render_instructions(adapter, root).encode("utf-8")
    try:
        with destination.open("xb") as stream:
            stream.write(content)
    except FileExistsError as error:
        raise RenderError("staged instruction output already exists: {}".format(destination)) from error
    return destination
