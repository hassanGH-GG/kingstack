from kingstack.skills import render_skill_files


ALWAYS_ON = frozenset(
    {
        "10-correction-rule",
        "35-constraints",
        "40-model-and-context",
        "adapter",
    }
)


def _heading(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "kingstack"


def _rule_bytes(body, description, always_apply):
    text = body.lstrip("\n")
    if not text.endswith("\n"):
        text += "\n"
    return (
        "---\ndescription: {}\nalwaysApply: {}\n---\n\n{}".format(
            description, "true" if always_apply else "false", text
        )
    ).encode("utf-8")


def render(root, declaration, shared_sources):
    bundle = {}
    fragments = shared_sources["instruction_fragments"]
    for name, text in fragments.items():
        stem = name[:-3] if name.endswith(".md") else name
        bundle["rules/kingstack/{}.mdc".format(stem)] = _rule_bytes(
            text, _heading(text), stem in ALWAYS_ON
        )
    appendix = shared_sources["appendix"].decode("utf-8")
    if appendix.strip():
        bundle["rules/kingstack/adapter.mdc"] = _rule_bytes(
            appendix, _heading(appendix), True
        )
    for path, content in render_skill_files(declaration.id, root).items():
        bundle["skills/" + path] = content
    for path, content in shared_sources.get("adapter_files", {}).items():
        bundle[path] = content
    return bundle
