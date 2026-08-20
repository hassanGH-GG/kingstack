from kingstack.skills import render_skill_files


def render(root, declaration, shared_sources):
    bundle = {
        "CLAUDE.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
    for path, content in render_skill_files("claude", root).items():
        bundle["skills/" + path] = content
    return bundle
