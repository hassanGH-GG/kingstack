<EXTREMELY_IMPORTANT>
Kingstack policy applies on Codex. poteto-mode and the other Task/loop skills are unsupported here. Do not pretend they are installed. Follow AGENTS.md, use the cheapest model that can do the work, and keep shared memory under ~/.kingstack/memory.

Before starting work, restate the goal as a checkable finish condition ("done means ..."); if the request has none, derive one and state it.

Model and effort routing is a global ruler: read ~/Desktop/Work/kingstack/model-routing.md. Waiting or polling is never an LLM turn. Anything over ~200 lines the main thread would read goes to an economical-tier helper that returns a summary. `kingstack effort --file` scans spawn lines. Inherit is fail. Fat tool text is `~/.kingstack/headroom`. Live jobs are `~/.kingstack/sessions`. Open a handoff packet with `kingstack handoff` output. Do not invent a host spawn or a loop primitive.
</EXTREMELY_IMPORTANT>
