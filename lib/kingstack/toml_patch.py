"""Owned-key TOML merge that keeps unowned lines and can invert."""

from typing import Any, Mapping, Tuple


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


def owned_spans(original: str, owned: Mapping[str, object]) -> Tuple[str, Mapping[str, Any]]:
    lines = original.splitlines(True)
    present = set()
    snapshot = {}
    output = []
    current = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            current = [part.strip() for part in stripped[1:-1].split(".")]
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
    for key in missing:
        snapshot[key] = None
        table, _, name = key.rpartition(".")
        if table:
            output.append("\n[{}]\n".format(table))
        output.append("{} = {}\n".format(name or key, _render(owned[key])))
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
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            current_table = [part.strip() for part in stripped[1:-1].split(".")]
            output.append(line)
            continue
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            dotted = ".".join(current_table + [key]) if current_table else key
            if dotted in remove:
                continue
        output.append(line)
    return "".join(output)
