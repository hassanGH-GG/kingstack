from pathlib import Path

from kingstack.skills import render_skill_files


def render(root, declaration, shared_sources):
    bundle = {
        "AGENTS.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
    for path, content in render_skill_files("cursor", root).items():
        bundle["skills/" + path] = content
    hooks = Path(root) / "adapters/cursor"
    bundle["hooks.json"] = (hooks / "hooks.json").read_bytes()
    bundle["hooks/run.py"] = (hooks / "hooks/run.py").read_bytes()
    return bundle
