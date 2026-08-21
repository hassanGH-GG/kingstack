#!/bin/bash
# kingstack nightly: roll yesterday's usage and this period's rework into the permanent
# ledgers, because transcripts expire after ~30 days and the history would be lost with them.
# Loaded by launchd as com.hassan.claude-usage-snapshot (00:23).
set -uo pipefail
KINGSTACK_ROOT="${KINGSTACK_ROOT:-$HOME/Desktop/Work/kingstack}"
if ! PYTHONPATH="$KINGSTACK_ROOT/lib" python3 -c "from kingstack.schedule_lock import claim; claim('com.hassan.claude-usage-snapshot', 'launchd')"; then
  echo "duplicate prevented"
  exit 0
fi
. "$KINGSTACK_ROOT/scripts/lib-headless.sh"
python3 "$KINGSTACK_ROOT/scripts/usage-snapshot.py"
python3 "$KINGSTACK_ROOT/scripts/rework-report.py" --days 14 --snapshot | tail -1
