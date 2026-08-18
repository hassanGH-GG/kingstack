#!/usr/bin/env python3
"""usage-report: token usage rolled up from Claude Code transcripts (both profiles share ~/.claude/projects).

  usage-report                 last 7 days, by day
  usage-report --days 30       last 30 days
  usage-report --by model      by model instead of day
  usage-report --by project    by project
  usage-report --today         today only, by model + project

Counts every assistant turn's `usage` block. Dedupes streamed partial rows by message id
(keeps the last, most complete row per message). Cost is an estimate at Anthropic list
prices; edit PRICES for your tier. Cache reads are ~10% of fresh-input price, cache
writes ~125%, which is why the split matters.
"""
import json, os, sys, glob, argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PROJ = os.path.expanduser("~/.claude/projects")
# $ per 1M tokens: (input, cache_write, cache_read, output). Approximate list prices.
PRICES = {
    "fable":  (15.0, 18.75, 1.50, 75.0),
    "opus":   (15.0, 18.75, 1.50, 75.0),
    "sonnet": (3.0,  3.75,  0.30, 15.0),
    "haiku":  (0.80, 1.00,  0.08, 4.0),
}
def price(model):
    m = model.lower()
    for k, v in PRICES.items():
        if k in m: return v
    return PRICES["sonnet"]

def slug_to_project(slug):
    # -Users-mac-Desktop-Work-plugins -> plugins ; drop worktree/scratchpad noise
    parts = slug.strip("-").split("-")
    return parts[-1] if parts else slug

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--by", choices=["day", "model", "project"], default="day")
    ap.add_argument("--today", action="store_true")
    a = ap.parse_args()
    since = datetime.now(timezone.utc) - timedelta(days=a.days)
    if a.today:
        since = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)

    # message_id -> (key fields, usage) ; keep last row per message id (streaming emits partials)
    rows = {}
    for f in glob.glob(f"{PROJ}/*/*.jsonl"):
        if os.path.getmtime(f) < since.timestamp(): continue
        proj = slug_to_project(os.path.basename(os.path.dirname(f)))
        try:
            with open(f, errors="ignore") as fh:
                for line in fh:
                    if '"usage"' not in line: continue
                    try: r = json.loads(line)
                    except: continue
                    if r.get("type") != "assistant": continue
                    m = r.get("message") or {}
                    u = m.get("usage"); ts = r.get("timestamp")
                    if not u or not ts: continue
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if t < since: continue
                    mid = m.get("id") or f"{f}:{ts}"
                    rows[mid] = (t.astimezone(), m.get("model", "?"), proj, u)
        except OSError: continue

    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0.0])  # inp, cw, cr, out, turns, cost
    for t, model, proj, u in rows.values():
        key = {"day": t.strftime("%Y-%m-%d"), "model": model, "project": proj}[a.by]
        if a.today: key = f"{model} · {proj}"
        inp = u.get("input_tokens", 0); cw = u.get("cache_creation_input_tokens", 0)
        cr = u.get("cache_read_input_tokens", 0); out = u.get("output_tokens", 0)
        p = price(model)
        cost = (inp*p[0] + cw*p[1] + cr*p[2] + out*p[3]) / 1e6
        g = agg[key]; g[0]+=inp; g[1]+=cw; g[2]+=cr; g[3]+=out; g[4]+=1; g[5]+=cost

    label = "model · project" if a.today else a.by
    print(f"{label:<28} {'turns':>6} {'fresh_in':>9} {'cache_wr':>9} {'cache_rd':>10} {'output':>8} {'~cost':>8}")
    tot = [0,0,0,0,0,0.0]
    for k in sorted(agg, reverse=(a.by=="day" and not a.today)):
        g = agg[k]
        for i in range(6): tot[i]+=g[i]
        print(f"{k[:28]:<28} {g[4]:>6} {g[0]/1e3:>8.0f}k {g[1]/1e6:>8.1f}M {g[2]/1e6:>9.1f}M {g[3]/1e3:>7.0f}k {g[5]:>7.2f}$")
    print(f"{'TOTAL':<28} {tot[4]:>6} {tot[0]/1e3:>8.0f}k {tot[1]/1e6:>8.1f}M {tot[2]/1e6:>9.1f}M {tot[3]/1e3:>7.0f}k {tot[5]:>7.2f}$")
    if tot[4]:
        print(f"\nper turn: {(tot[0]+tot[1]+tot[2])/tot[4]/1e3:.0f}k in (of which {tot[2]/max(1,tot[0]+tot[1]+tot[2])*100:.0f}% cache reads), {tot[3]/tot[4]:.0f} out")

if __name__ == "__main__": main()
