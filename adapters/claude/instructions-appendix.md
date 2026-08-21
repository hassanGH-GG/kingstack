
# Claude model routing

`~/.claude/model-routing.md` is Claude's global routing ruler, injected into every
session. Economical maps to Haiku, balanced maps to Sonnet, and frontier maps to
Opus by default; Fable may replace Opus only through a private availability
override for that spawn. Select the main-thread model once through `/model`, keep
effort medium, and report the chosen model and effort. Past ~150k tokens of
context, propose `/clear`.

Context cost is on the Claude status line via `hooks/ctx-status.py`. The line
shows model, effort, context, and which models subagents used. Same command:
`kingstack status`. `kingstack effort --file` scans `↳ spawn` lines. Inherit
is fail. Shared memory is `~/.kingstack/memory`. The working-set index is
`~/.kingstack/sessions`. Fat tool text is
`~/.kingstack/headroom`. A teammate starts at `docs/SETUP.md`.
