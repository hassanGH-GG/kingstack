# Shared setup for every kingstack script that runs `claude -p` unattended.
# Source it, do not execute it:  . "$HOME/.claude/scripts/lib-headless.sh"
#
# Solves two things that bite only in scheduled and headless runs, never interactively:
#   1. PATH. launchd gives a job almost nothing, and node lives under nvm, so plugin hooks
#      that shell out to node fail with "node: command not found" on every run.
#   2. Transient API errors. A 529 or a rate limit is a blip interactively and a skipped
#      fortnight for a biweekly job, so a bare call is never good enough here.

_node_bin=$(ls -td "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | head -1)
export PATH="$HOME/.claude/bin:$HOME/.local/bin${_node_bin:+:$_node_bin}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
unset _node_bin

# claude_retry <attempts> <base-delay-seconds> -- <claude args...>
# Retries only on errors that are worth retrying. A refusal, a bad flag or a permission
# denial fails immediately, because repeating it just burns tokens.
claude_retry() {
  local attempts="$1" delay="$2" out rc n=1
  shift 2; [ "${1:-}" = "--" ] && shift
  while :; do
    out=$(claude "$@" 2>&1); rc=$?
    if [ "$rc" = 0 ] && ! printf '%s' "$out" | grep -qiE 'api error: (429|500|502|503|529)|overloaded|rate limit|temporarily unavailable'; then
      printf '%s\n' "$out"; return 0
    fi
    if printf '%s' "$out" | grep -qiE 'api error: (429|500|502|503|529)|overloaded|rate limit|temporarily unavailable|usage credits'; then
      if [ "$n" -ge "$attempts" ]; then
        printf '%s\n' "$out"
        echo "claude_retry: gave up after $n attempt(s) on a transient error" >&2
        return 75   # EX_TEMPFAIL: the work did not happen, and it was not our fault
      fi
      echo "claude_retry: transient failure, attempt $n of $attempts, sleeping ${delay}s" >&2
      sleep "$delay"; delay=$((delay * 2)); n=$((n + 1)); continue
    fi
    printf '%s\n' "$out"; return "$rc"   # a real failure: do not retry
  done
}
