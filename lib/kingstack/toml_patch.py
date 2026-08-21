"""Owned-key TOML merge that keeps unowned lines and can invert."""

from collections import OrderedDict
from typing import Any, List, Mapping, Optional, Tuple


class TomlPatchError(ValueError):
    """Raised when an owned TOML key conflicts or the document is malformed."""


def _render(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json_dumps_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_render(item) for item in value) + "]"
    raise TomlPatchError("unsupported owned TOML value type")


def json_dumps_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"{}"'.format(escaped)


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        items = []
        for part in inner.split(","):
            items.append(_parse_scalar(part))
        return items
    if text in ("true", "false"):
        return text == "true"
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    try:
        return int(text)
    except ValueError:
        raise TomlPatchError("cannot parse owned TOML value")


def _table_header(line: str) -> Optional[str]:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
        return stripped[1:-1].strip()
    return None


def _table_range(lines: List[str], table: str) -> Optional[Tuple[int, int]]:
    start = None
    for index, line in enumerate(lines):
        if _table_header(line) == table:
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _table_header(lines[index]) is not None:
            end = index
            break
    return start, end


def _first_related_table(lines: List[str], table: str) -> Optional[int]:
    prefix = table + "."
    for index, line in enumerate(lines):
        name = _table_header(line)
        if name == table or (name is not None and name.startswith(prefix)):
            return index
    return None


def _insert_owned_rows(lines: List[str], table: str, items: List[Tuple[str, Any]]) -> None:
    rows = ["{} = {}\n".format(name, _render(value)) for name, value in items]
    existing = _table_range(lines, table) if table else None
    if existing is not None:
        _, end = existing
        insert_at = end
        while insert_at > existing[0] + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        lines[insert_at:insert_at] = rows
        return
    block = []
    if table:
        related = _first_related_table(lines, table)
        block.append("[{}]\n".format(table))
        block.extend(rows)
        if related is None:
            if lines and lines[-1].strip():
                block.insert(0, "\n")
            lines.extend(block)
            return
        if related > 0 and lines[related - 1].strip():
            block.insert(0, "\n")
        if not block[-1].endswith("\n"):
            block[-1] += "\n"
        block.append("\n")
        lines[related:related] = block
        return
    if lines and lines[-1].strip():
        lines.append("\n")
    lines.extend(rows)


def owned_spans(original: str, owned: Mapping[str, object]) -> Tuple[str, Mapping[str, Any]]:
    lines = original.splitlines(True)
    present = set()
    snapshot = {}
    output = []
    current = []
    for line in lines:
        stripped = line.strip()
        header = _table_header(line)
        if header is not None:
            current = [part.strip() for part in header.split(".")]
            output.append(line)
            continue
        if "=" in stripped and not stripped.startswith("#"):
            key, raw = stripped.split("=", 1)
            key = key.strip()
            dotted = ".".join(current + [key]) if current else key
            if dotted in owned:
                snapshot[dotted] = _parse_scalar(raw)
                if snapshot[dotted] != owned[dotted]:
                    raise TomlPatchError("conflicting owned key {}".format(dotted))
                present.add(dotted)
                output.append("{} = {}\n".format(key, _render(owned[dotted])))
                continue
        output.append(line)
    missing = [key for key in owned if key not in present]
    groups = OrderedDict()
    for key in missing:
        snapshot[key] = None
        table, _, name = key.rpartition(".")
        groups.setdefault(table, []).append((name, owned[key]))
    for table, items in groups.items():
        _insert_owned_rows(output, table, items)
    return "".join(output), snapshot


def inverse_spans(current: str, snapshot: Mapping[str, Any]) -> str:
    restore = {key: value for key, value in snapshot.items() if value is not None}
    remove = [key for key, value in snapshot.items() if value is None]
    text, _ = owned_spans(current, restore) if restore else (current, {})
    if not remove:
        return text
    lines = text.splitlines(True)
    output = []
    current_table = []
    for line in lines:
        stripped = line.strip()
        header = _table_header(line)
        if header is not None:
            current_table = [part.strip() for part in header.split(".")]
            output.append(line)
            continue
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            dotted = ".".join(current_table + [key]) if current_table else key
            if dotted in remove:
                continue
        output.append(line)
    return "".join(output)
