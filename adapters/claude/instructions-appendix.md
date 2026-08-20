
# Claude model routing

`~/.claude/model-routing.md` is Claude's global routing ruler, injected into every
session. Economical maps to Haiku, balanced maps to Sonnet, and frontier maps to
Opus by default; Fable may replace Opus only through a private availability
override for that spawn. Select the main-thread model once through `/model`, keep
effort medium, and report the chosen model and effort. Past ~150k tokens of
context, propose `/clear`.
