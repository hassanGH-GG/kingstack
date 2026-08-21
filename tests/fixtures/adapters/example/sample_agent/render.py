def render(root, declaration, shared_sources):
    return {
        "hooks/session-start": b"sample-agent-start\n",
        "GUIDANCE.md": shared_sources["instructions"] + shared_sources["appendix"],
    }
