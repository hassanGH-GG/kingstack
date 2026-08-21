#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export KINGSTACK_RUNTIME="${KINGSTACK_RUNTIME:-$HOME/.claude}"
python3 "$here/run.py" PostToolUse
