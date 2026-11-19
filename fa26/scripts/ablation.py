"""Ablation runner for the deployed engine (src/ask.py): one upgrade at a time, same questions, same graph.

Configs (each is the baseline plus exactly one change):
  baseline  the engine as deployed
  cache     plan cache (exact question text) + result cache (same tool and args, or same Cypher); repeats share it,
            so repeat 1 is cold and repeat 2 is warm
  (repair, fewshot, review: added one at a time after the previous experiment is read)

Splits: regression and development only. A heldout bundle is refused (the heldout run is frozen).

    conda activate iati
    python fa26/benchmark/v2/export_inputs.py /tmp/iati_regression  --split regression     # once per split
    python fa26/benchmark/v2/export_inputs.py /tmp/iati_development --split development
    python fa26/scripts/ablation.py --bundle /tmp/iati_regression --bundle /tmp/iati_development \\
        --models anthropic/claude-sonnet-4-6,anthropic/claude-opus-4-6,zai/glm-5.3 --configs baseline,cache --repeats 2

    --limit 3     quick smoke (first 3 questions of each split; scores are not meaningful)

Writes fa26/reports/ablation/<run_id>/:
  log.jsonl           one line per question and repeat: status, path (tool / free_cypher / clarify / abstain), tool,
                      retries, model calls, tokens in/out, cache hits, stage timings, error kind
  submissions/, scores/   benchmark submissions and score_v2.py output per (config, model, repeat, split)
  summary.csv, summary.md one row per (config, model, repeat, split); every number comes from log.jsonl or scores/
"""
import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FA26 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FA26 / "benchmark")); sys.path.insert(0, str(FA26 / "src"))
from common import verify_snapshot, save_json                      # noqa: E402
from benchmark_bundle import load_bundle, submission, score_command  # noqa: E402

CONFIGS = {"baseline": {}, "cache": {"cache": True}}
OPEN_SPLITS = ("regression", "development")


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def score(sub_path, bundle, out_dir):
    proc = subprocess.run(score_command(sys.executable, FA26, [sub_path], out_dir, bundle), capture_output=True, text=True, cwd=FA26.parent)
    if proc.returncode != 0:
        print(proc.stdout[-1500:], proc.stderr[-1500:]); return {}
    runs = json.loads((Path(out_dir) / "comparison.json").read_text())
    runs = runs["runs"] if isinstance(runs, dict) else runs
    return runs[0].get("summary", runs[0]) if runs else {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", action="append", required=True, help="exported public bundle directory (repeatable)")
    ap.add_argument("--models", default=os.environ.get("IATI_RUN_MODELS", "anthropic/claude-sonnet-4-6"))
    ap.add_argument("--configs", default="baseline,cache")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=str(FA26 / "reports" / "ablation"))
    a = ap.parse_args()

    from ask import Engine
    snapshot_id = verify_snapshot()["snapshot_id"]
    bundles = [load_bundle(b, snapshot_id) for b in a.bundle]
    for b in bundles:
        if b["template"]["split"] not in OPEN_SPLITS:
            sys.exit(f"refusing split {b['template']['split']!r}: only {OPEN_SPLITS} are open for experiments")
    configs = [c.strip() for c in a.configs.split(",") if c.strip()]
    for c in configs:
        if c not in CONFIGS: sys.exit(f"unknown config {c!r}; available: {list(CONFIGS)}")
    models = [m.strip() for m in a.models.split(",") if m.strip()]

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    out = Path(a.out) / run_id
    (out / "submissions").mkdir(parents=True, exist_ok=True); (out / "scores").mkdir(exist_ok=True)
    save_json(out / "run.json", {"run_id": run_id, "snapshot_id": snapshot_id, "models": models, "configs": configs,
                                 "repeats": a.repeats, "splits": [b["template"]["split"] for b in bundles], "limit": a.limit})
    log = (out / "log.jsonl").open("w", encoding="utf-8")
    summary = []

    for model in models:
        for cfg in configs:
            eng = Engine(model=model, **CONFIGS[cfg])          # one engine per (model, config): a cache lives across repeats
            for rep in range(1, a.repeats + 1):
                for b in bundles:
                    split = b["template"]["split"]
                    qs = b["questions"][: a.limit] if a.limit else b["questions"]
                    answers, recs = [], []
                    for q in qs:
                        ans = eng.ask(q["question"], qid=q["id"], contract=q.get("contract", ""), value_type=q.get("value_type", "auto"))
                        answers.append({"id": q["id"], "status": ans["status"], "facts": ans["facts"], "reasons": ans["reasons"],
                                        "latency_ms": ans["latency_ms"]})
                        rec = {"run_id": run_id, "model": model, "config": cfg, "repeat": rep, "split": split, "qid": q["id"],
                               "status": ans["status"], "path": ans["path"], "tool": ans["tool"], "retries": ans["retries"],
                               "model_calls": ans["model_calls"], "tokens_in": ans["tokens"]["in"], "tokens_out": ans["tokens"]["out"],
                               "cache_plan": ans["cache"]["plan"], "cache_result": ans["cache"]["result"],
                               "latency_ms": ans["latency_ms"], **{k: v for k, v in ans["timings"].items() if k != "total_ms"},
                               "error_kind": (ans["error"] or "").split(":")[0][:60] or None}
                        recs.append(rec); log.write(json.dumps(rec) + "\n"); log.flush()
                        print(f"{model:<32} {cfg:<9} r{rep} {split:<11} {q['id']:<7} {ans['status']:<8} {ans['path']:<12} "
                              f"calls={ans['model_calls']} tok={ans['tokens']['in']}/{ans['tokens']['out']} {ans['latency_ms']:>8.0f} ms"
                              f"{'  cache' if ans['cache']['plan'] else ''}")
                    tag = f"{cfg}__{model.replace('/', '_')}__r{rep}__{split}"
                    sub = out / "submissions" / f"{tag}.json"
                    save_json(sub, submission(b, f"ablation__{tag}__{run_id}", snapshot_id, answers))
                    sc = score(sub, b, out / "scores" / tag) if not a.limit else {}
                    lat = [r["latency_ms"] for r in recs]
                    paths = Counter(r["path"] for r in recs)
                    summary.append({
                        "config": cfg, "model": model, "repeat": rep, "split": split, "n": len(recs),
                        "overall_pct": sc.get("overall_pct"), "correctness_pct": sc.get("correctness_pct"),
                        "evidence_f1_pct": sc.get("evidence_f1_pct"), "behavior_pct": sc.get("behavior_pct"),
                        "latency_mean_ms": round(statistics.mean(lat), 1), "latency_p50_ms": pct(lat, 50), "latency_p95_ms": pct(lat, 95),
                        "model_calls": sum(r["model_calls"] for r in recs), "tokens_in": sum(r["tokens_in"] for r in recs),
                        "tokens_out": sum(r["tokens_out"] for r in recs), "retries": sum(r["retries"] for r in recs),
                        "errors": sum(1 for r in recs if r["error_kind"]), "plan_cache_hits": sum(r["cache_plan"] for r in recs),
                        "path_tool": paths.get("tool", 0), "path_free_cypher": paths.get("free_cypher", 0),
                        "path_clarify": paths.get("clarify", 0), "path_abstain": paths.get("abstain", 0)})
            eng.close()
    log.close()

    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
    cols = ["config", "model", "repeat", "split", "n", "overall_pct", "correctness_pct", "evidence_f1_pct", "latency_mean_ms",
            "latency_p95_ms", "model_calls", "tokens_in", "tokens_out", "plan_cache_hits", "errors"]
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in summary]
    (out / "summary.md").write_text(f"# Ablation {run_id}\n\nSource: log.jsonl and scores/ in this folder.\n\n" + "\n".join(md) + "\n")
    print("\n".join(md)); print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
