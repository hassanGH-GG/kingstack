
# Model and effort routing

`~/.claude/model-routing.md` is the global ruler, injected into every session. Main
thread: Fable or Opus at effort medium, set once by me. Every subagent is routed by
class of work, cheapest tier first (mechanical → haiku, precise → sonnet/opus,
judgment → fable/opus), escalated on evidence, pick named in one clause. Polling
and waiting are never LLM turns (Monitor / until-loop / hook). Bulk over ~200 lines
never enters the main thread; a haiku subagent returns a summary. Past ~150k tokens
of context, propose `/clear`.
