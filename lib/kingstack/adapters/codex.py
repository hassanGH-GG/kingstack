def render(root, declaration, shared_sources):
    return {
        "AGENTS.md": shared_sources["instructions"] + shared_sources["appendix"]
    }
