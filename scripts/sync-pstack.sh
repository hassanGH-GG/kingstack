#!/bin/sh
# Compatibility front door for the pure, adapter-aware pstack source check and
# bundle manifest. It never pulls, installs, prunes, stages, or writes a native
# agent home.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$SCRIPT_DIR/kingstack" sync-upstream pstack "$@"
