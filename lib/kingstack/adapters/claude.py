from pathlib import Path

from kingstack.skills import render_skill_files


HOOK_FILES = (
    "normalize.py",
    "post-tool-use.sh",
    "poteto-mode-context.md",
    "pre-compact.sh",
    "run.py",
    "session-start.sh",
    "stop.sh",
    "subagent-start.sh",
)


def render(root, declaration, shared_sources):
    bundle = {
        "CLAUDE.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
    for path, content in render_skill_files("claude", root).items():
        bundle["skills/" + path] = content
    hooks = Path(root) / "adapters/claude/hooks"
    for name in HOOK_FILES:
        bundle["hooks/" + name] = (hooks / name).read_bytes()
    return bundle
