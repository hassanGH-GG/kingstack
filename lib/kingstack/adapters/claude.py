from kingstack.skills import render_skill_files


def render(root, declaration, shared_sources):
    bundle = {
        "CLAUDE.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
    for path, content in render_skill_files(declaration.id, root).items():
        bundle["skills/" + path] = content
    for path, content in shared_sources.get("adapter_files", {}).items():
        bundle[path] = content
    return bundle
