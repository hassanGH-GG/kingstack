
# Model and effort routing

The shared routing policy classifies work by portable capability tier. The main
thread model remains user-controlled at effort medium, set once by the user. Every
subagent sets its adapter model and effort explicitly, reports both to the parent
or user, and starts with the cheapest suitable tier (mechanical → economical,
precise → balanced, judgment → frontier). Escalate only on evidence and name the
choice in one clause. If a selected model is unavailable, fall back exactly one
adjacent tier for that spawn, report the reason, and never apply a blanket
override. Polling and waiting are never model turns (monitor, until-loop, or
hook). Bulk over ~200 lines never enters the main thread; an economical-tier
subagent returns a summary. Past ~150k tokens of context, propose the adapter's
fresh-context command. Context and compaction ceilings otherwise remain native
to the adapter.
