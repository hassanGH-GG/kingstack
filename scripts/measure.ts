#!/usr/bin/env bun
// measure: rerun a worker's quantitative claims on its real branch and flag drift.
// Ported (compacted) from cursor/plugins orchestrate/measurements.ts.
//
//   measure check --handoff handoffs/task.md --spec measurements.json --repo . [--tolerance 0.1]
//   measure parse --handoff handoffs/task.md            # just show the parsed claims
//
// handoff `## Measurements` lines:   <name>: <before> → <after>     (also <=,<,>=,>,==)
// spec (JSON array): [{ "name": "LOC(src/a.ts)", "command": "wc -l < src/a.ts", "tolerance": 0.1 }]
//   command runs under `bash -c` in a fresh clone of the worker's branch; its stdout's first
//   number is the observed value. Compared against the worker's claimed `after`.
// Exit 0 = all within tolerance, 1 = drift or unparseable, 2 = usage.
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

type Op = "→" | "<=" | "<" | ">=" | ">" | "==";
const OPS: Op[] = ["→", "<=", ">=", "==", "<", ">"];
interface Claim { name: string; before: string; op: Op; after: string }
interface Spec { name: string; command: string; tolerance?: number }
interface Check { name: string; claimed: string; observed: string | null; ok: boolean; note: string }

export function parseMeasurements(handoff: string): { none: boolean; claims: Claim[]; unparsed: string[] } | null {
  const lines = handoff.split("\n");
  const start = lines.findIndex(l => /^##\s+Measurements\s*$/i.test(l));
  if (start < 0) return null;
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) if (/^##\s/.test(lines[i])) { end = i; break; }
  const body = lines.slice(start + 1, end).join("\n").trim();
  if (/^\(none\)$/i.test(body)) return { none: true, claims: [], unparsed: [] };
  const claims: Claim[] = [], unparsed: string[] = [];
  for (const raw of body.split("\n")) {
    const line = raw.replace(/^[-*]\s+/, "").trim();
    if (!line) continue;
    const c = parseLine(line);
    c ? claims.push(c) : unparsed.push(line);
  }
  return { none: false, claims, unparsed };
}

export function parseLine(line: string): Claim | null {
  const colon = line.indexOf(":");
  if (colon < 1) return null;
  const name = line.slice(0, colon).trim(), rest = line.slice(colon + 1).trim();
  for (const op of OPS) {
    const i = rest.indexOf(op);
    if (i > 0) {
      const before = rest.slice(0, i).trim(), after = rest.slice(i + op.length).trim();
      if (before && after) return { name, before, op, after };
    }
  }
  return null;
}

export function firstNumber(s: string): { value: number; unit: string } | null {
  const m = s.match(/(-?\d[\d,]*\.?\d*)\s*([A-Za-z%]*)/);
  if (!m) return null;
  return { value: parseFloat(m[1].replace(/,/g, "")), unit: m[2].toLowerCase() };
}

export function compare(claimed: string, observed: string, tolerance: number): { ok: boolean; note: string } {
  const c = firstNumber(claimed), o = firstNumber(observed);
  if (!c || !o) return { ok: claimed.trim() === observed.trim(), note: "non-numeric, exact match" };
  if (c.unit && o.unit && c.unit !== o.unit) return { ok: false, note: `unit mismatch ${c.unit} vs ${o.unit}` };
  const base = Math.max(Math.abs(c.value), 1e-9);
  const drift = Math.abs(o.value - c.value) / base;
  return { ok: drift <= tolerance, note: `drift ${(drift * 100).toFixed(1)}% (tol ${(tolerance * 100).toFixed(0)}%)` };
}

function arg(name: string): string | undefined { const i = process.argv.indexOf(`--${name}`); return i > -1 ? process.argv[i + 1] : undefined; }

function main() {
  const cmd = process.argv[2];
  const handoffPath = arg("handoff");
  if (!cmd || !handoffPath || !["check", "parse"].includes(cmd)) {
    console.error("usage: measure check --handoff <md> --spec <json> --repo <dir> [--branch <ref>] [--tolerance 0.1]\n       measure parse --handoff <md>");
    process.exit(2);
  }
  const handoff = readFileSync(handoffPath, "utf8");
  const parsed = parseMeasurements(handoff);
  if (!parsed) { console.error("handoff has no ## Measurements section"); process.exit(1); }
  if (cmd === "parse") {
    for (const c of parsed.claims) console.log(`${c.name}: ${c.before} ${c.op} ${c.after}`);
    for (const u of parsed.unparsed) console.log(`unparsed: ${u}`);
    process.exit(parsed.unparsed.length ? 1 : 0);
  }
  const spec: Spec[] = JSON.parse(readFileSync(arg("spec")!, "utf8"));
  const repo = arg("repo") ?? ".";
  const branch = arg("branch") ?? (handoff.match(/^##\s+Branch\s*$\s*([^\s]+)/mi)?.[1]);
  const tol = parseFloat(arg("tolerance") ?? "0.1");
  const tmp = mkdtempSync(join(tmpdir(), "measure-"));
  try {
    execFileSync("git", ["clone", "--quiet", "--depth", "1", ...(branch ? ["--branch", branch] : []), repo, tmp], { stdio: "pipe", timeout: 600_000 });
    const checks: Check[] = [];
    for (const s of spec) {
      const claim = parsed.claims.find(c => c.name === s.name);
      if (!claim) { checks.push({ name: s.name, claimed: "(missing)", observed: null, ok: false, note: "worker did not report this measurement" }); continue; }
      const r = spawnSync("bash", ["-c", s.command], { cwd: tmp, encoding: "utf8", timeout: 300_000 });
      const observed = (r.stdout || "").trim().split("\n").pop() ?? "";
      const cmp = r.status === 0 ? compare(claim.after, observed, s.tolerance ?? tol) : { ok: false, note: `command exit ${r.status}: ${(r.stderr || "").trim().slice(0, 120)}` };
      checks.push({ name: s.name, claimed: claim.after, observed: r.status === 0 ? observed : null, ok: cmp.ok, note: cmp.note });
    }
    let bad = 0;
    for (const c of checks) { if (!c.ok) bad++; console.log(`${c.ok ? "ok  " : "DRIFT"} ${c.name}: claimed ${c.claimed} | observed ${c.observed ?? "-"} | ${c.note}`); }
    process.exit(bad ? 1 : 0);
  } finally { rmSync(tmp, { recursive: true, force: true }); }
}
if (import.meta.main) main();
