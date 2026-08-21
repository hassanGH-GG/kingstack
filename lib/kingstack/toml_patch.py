"""Narrow TOML key ownership. Unrelated keys and comments stay untouched."""

from typing import Mapping, Tuple


class TomlPatchError(ValueError):
    """Raised when an owned TOML key conflicts or the document is malformed."""


def owned_spans(original: str, owned: Mapping[str, object]) -> Tuple[str, Mapping[str, str]]:
    """Return patched text. Unowned lines are preserved byte-for-byte."""
    lines = original.splitlines(True)
    if not lines:
        lines = []
    present = set()
    output = []
    current = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and not stripped.startswith("[["):
            current = stripped[1:-1].split(".")
            output.append(line)
            continue
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            dotted = ".".join(current + [key]) if current else key
            if dotted in owned:
                present.add(dotted)
                value = owned[dotted]
                rendered = "true" if value is True else "false" if value is False else '"{}"'.format(value)
                output.append("{} = {}\n".format(key, rendered))
                continue
        output.append(line)
    missing = [key for key in owned if key not in present]
    for key in missing:
        table, _, name = key.rpartition(".")
        if table:
            output.append("\n[{}]\n".format(table))
        value = owned[key]
        rendered = "true" if value is True else "false" if value is False else '"{}"'.format(value)
        output.append("{} = {}\n".format(name or key, rendered))
    return "".join(output), {key: "owned" for key in owned}
