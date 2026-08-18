---
name: kingstack-health
enabled: true
schedule: daily
cwd: ~
model: haiku
max_turns: 8
report: log
owner: hassan
allow: Bash(~/.claude/scripts/check-setup.sh*), Bash(/Users/mac/.claude/scripts/check-setup.sh*)
---
You are an unattended sweep. Run `~/.claude/scripts/check-setup.sh` with Bash and read its
output. If the last line is `SETUP HEALTHY`, reply exactly `OK: setup healthy, N checks`.
Otherwise reply `ATTENTION:` followed by every line starting with ✗, verbatim, one per line.
Do not attempt to fix anything.
