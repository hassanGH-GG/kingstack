# pstack model configuration (Claude Code adaptation)

**Routing policy lives in `~/.claude/model-routing.md`**; it governs every subagent call
that a skill does not explicitly prescribe. The roles below are pstack's prescribed
defaults for its own workflow skills (interrogate, arena, reflect, swarm, architect).

pstack's skills reference model roles. Upstream (Cursor) split roles across
vendors; this install maps every role onto the Claude family, using the model
values the Agent tool accepts (`fable`, `opus`, `sonnet`, `haiku`).

| Role | Upstream default | Here |
|---|---|---|
| Prose, judgment, synthesis, review | claude-fable-5-thinking-max | `fable` |
| Precisely-specified code | gpt-5.6-sol-max | `opus` |
| Fast mechanical code, bulk edits | grok-4.6-fast-xhigh | `haiku` |
| Heavy reasoning fallback | claude-opus-5-thinking-xhigh | `opus` |

Notes:
- Upstream's "different model family for review" diversity is approximated here
  by using a different Claude tier (e.g. reviewer on `opus` when the author ran
  on `fable`), since only Claude models are available in this harness.
- Omitting `model` on an Agent call inherits the session model — usually right;
  set a role model only where a skill explicitly prescribes one.
- To retune: edit this table; skills reference this file as the source of truth.
