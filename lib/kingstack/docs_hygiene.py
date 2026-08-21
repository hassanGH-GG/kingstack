"""Classify every tracked Markdown file. Fail if any file is missing a status."""

import json
from pathlib import Path
import subprocess
from typing import List


STATUSES = {"rewrite", "historical", "upstream", "fixture", "delete-at-final-acceptance"}


def tracked_markdown(root: Path) -> List[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "*.md"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def hygiene_errors(root: Path) -> List[str]:
    manifest = json.loads((Path(root) / "docs/markdown-surfaces.json").read_text(encoding="utf-8"))
    classified = manifest.get("files", {})
    errors = []
    for path in tracked_markdown(root):
        status = classified.get(path)
        if status is None:
            errors.append("unclassified {}".format(path))
        elif status not in STATUSES:
            errors.append("unknown status for {}".format(path))
    for path in sorted(set(classified) - set(tracked_markdown(root))):
        if not (Path(root) / path).is_file():
            errors.append("classified but missing {}".format(path))
    return errors
