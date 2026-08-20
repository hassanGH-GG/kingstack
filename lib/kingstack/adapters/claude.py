def render(root, declaration, shared_sources):
    return {
        "CLAUDE.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
