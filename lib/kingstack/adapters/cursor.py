from kingstack.skills import render_skill_files


def render(root, declaration, shared_sources):
    bundle = {
        "AGENTS.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
    for path, content in render_skill_files("cursor", root).items():
        bundle["skills/" + path] = content
    return bundle
