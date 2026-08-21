"""Classify SubagentStart spawn lines. Inherit is fail. Named model+effort is pass."""

import re
from pathlib import Path
from typing import List, Mapping, TextIO


SPAWN = re.compile(r"↳ spawn \[[^\]]+\] .* · model=(\S+) effort=(\S+)")


def classify(model: str, effort: str) -> bool:
    return bool(model) and bool(effort) and model != "inherit" and effort != "inherit"


def scan_spawns(text: str) -> List[Mapping[str, object]]:
    rows = []
    for line in text.splitlines():
        match = SPAWN.search(line)
        if match is None:
            continue
        model, effort = match.group(1), match.group(2)
        rows.append(
            {
                "model": model,
                "effort": effort,
                "ok": classify(model, effort),
                "line": line.strip(),
            }
        )
    return rows


def scan_file(path: Path) -> List[Mapping[str, object]]:
    return scan_spawns(Path(path).read_text(encoding="utf-8"))


def scan_stream(handle: TextIO) -> List[Mapping[str, object]]:
    return scan_spawns(handle.read())


def failed(rows: List[Mapping[str, object]]) -> List[Mapping[str, object]]:
    return [row for row in rows if not row["ok"]]
