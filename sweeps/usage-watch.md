---
name: usage-watch
enabled: true
schedule: daily
cwd: ~
model: haiku
max_turns: 6
report: log
owner: hassan
allow: Bash(cat /Users/mac/.claude/usage-summary.md*), Bash(cat /Users/mac/.claude/docs/token-projection-2026-08.md*), Bash(head *), Bash(tail *)
---
You are an unattended sweep testing whether context enforcement functions as intended.
Read /Users/mac/.claude/usage-summary.md. Find the most recent day's row (turns, ctx/turn,
cost). The enforcement predictions live in /Users/mac/.claude/docs/token-projection-2026-08.md;
the two you test daily: no day above 250k ctx/turn, and the trend should settle toward
120-180k.

Reply `OK: <day> ctx/turn <value>, ceiling holding (target band 120-180k)` when the most
recent day is at or under 250k. Reply `ATTENTION: <day> averaged <value>k ctx/turn, above
the 250k line; the 200k auto-compact ceiling is NOT functioning as intended; check
autoCompactWindow in settings.json and whether long sessions predate the ceiling` when it
is above. Include the cost figure either way. Never suggest changing models; weight is
the lever.
