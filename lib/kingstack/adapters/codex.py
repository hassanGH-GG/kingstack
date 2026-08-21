from pathlib import Path

from kingstack.skills import render_skill_files


HOOK_FILES = ("hooks.json", "hooks/run.py")


def render(root, declaration, shared_sources):
    bundle = {
        "AGENTS.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
    for path, content in render_skill_files("codex", root).items():
        bundle["skills/" + path] = content
    hooks = Path(root) / "adapters/codex"
    bundle["hooks.json"] = (hooks / "hooks.json").read_bytes()
    bundle["hooks/run.py"] = (hooks / "hooks/run.py").read_bytes()
    bundle["config-owned.json"] = (hooks / "config-owned.json").read_bytes()
    return bundle
