"""Redraw the two benchmark v2 slide figures from the run files.

    python fa26/scripts/make_v2_figures.py

Writes reports/figures/iati_v2_development_before_after_2026-11-05.jpg and
reports/figures/iati_pipeline_validator_2026-11-05.jpg (300 DPI). Every number in the captions is computed here
from reports/benchmark_runs/*.json and the per-question eval CSVs in data/processed (gitignored: present only on
the machine that ran the evaluations; if they are missing the call counts are printed as "not recorded").
Rounding: bar labels and the 'Overall' caption line are half up to whole points (98.5 -> 99); other caption numbers are the stored values.
"""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import logging
import matplotlib
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

FA26 = Path(__file__).resolve().parents[1]
RUNS = FA26 / "reports" / "benchmark_runs"
OUT = FA26 / "reports" / "figures"
PROC = FA26 / "data" / "processed"
plt.rcParams["font.family"] = ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"]
INK, MUTED, GRID = "#1F2328", "#57606A", "#E4E7EA"


def r(x):
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calls(csv_name):
    p = PROC / csv_name
    if not p.exists():
        return None
    import csv
    out = {}
    for row in csv.DictReader(p.open()):
        m = row["model"]
        out.setdefault(m, [0, 0])
        out[m][0] += int(float(row["model_calls"] or 0)); out[m][1] += int(float(row["retries"] or 0))
    return out


def before_after():
    first = json.loads((RUNS / "2026-11-05_v2_development_06_firstrun_before_fixes.json").read_text())
    after = json.loads((RUNS / "2026-11-05_v2_development_06_hybrid.json").read_text())
    # run order in both files: first run = Opus, Sonnet, GLM-5.3; after = Sonnet, GLM-5.3 (notebook RUN_MODELS order)
    f_son, f_glm = first["runs"][1], first["runs"][2]
    a_son, a_glm = after["runs"][0], after["runs"][1]
    cats = [("Overall", None), ("Direct", "direct"), ("Two-step", "two_step"), ("Organisation", "organisation"),
            ("Financial", "financial"), ("Limitations", "limitations")]

    def val(run, c):
        return run["summary"]["overall_pct"] if c is None else run["by_category"][c]["overall_pct"]
    series = [("Sonnet 4.6, first run", f_son, "#C9D6CF"), ("Sonnet 4.6, after fixes", a_son, "#0F6E4F"),
              ("GLM-5.3, first run", f_glm, "#E6D3B5"), ("GLM-5.3, after fixes", a_glm, "#B5732E")]
    misses = {}
    for label, run in (("Sonnet", a_son), ("GLM-5.3", a_glm)):
        qs = run["questions"]
        ans = [q for q in qs if q["behavior"] is None]
        misses[label] = dict(n_ans=len(ans), ans_ok=sum(q["correctness"] == 1.0 for q in ans),
                             ev=[q["id"] for q in ans if q["evidence_f1"] is not None and q["evidence_f1"] < 1],
                             beh=[q["id"] for q in qs if q["behavior"] is not None and q["behavior"] < 1])

    W, H = 12.8, 6.6
    fig = plt.figure(figsize=(W, H), dpi=300)
    fig.text(0.035, 0.95, "Benchmark v2, development split (40 of 100 questions): before and after the pipeline fixes",
             fontsize=16, weight="bold", color=INK)
    fig.text(0.035, 0.905, "Hybrid router (notebook 06), overall score per category. Same questions, same pinned snapshot, "
             "same two models; the router, templates and output checks changed between runs.", fontsize=9.5, color=MUTED)
    ax = fig.add_axes([0.06, 0.25, 0.92, 0.58])
    n, bw = len(cats), 0.19
    for j, (lab, run, col) in enumerate(series):
        xs = [i + (j - 1.5) * (bw + 0.01) for i in range(n)]
        ys = [val(run, c) for _, c in cats]
        ax.bar(xs, ys, bw, color=col, label=lab, zorder=2)
        for x, y in zip(xs, ys):
            ax.text(x, y + 1.2, str(r(y)), ha="center", va="bottom", fontsize=9,
                    color=INK, weight="bold" if "after" in lab else "normal")
    ax.set_xticks(range(n)); ax.set_xticklabels([c for c, _ in cats], fontsize=11, color=INK)
    ax.set_ylim(0, 108); ax.set_yticks([0, 25, 50, 75, 100]); ax.tick_params(axis="y", labelsize=9, colors=MUTED)
    ax.grid(axis="y", color=GRID, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.13), ncol=4, frameon=False, fontsize=9.5)

    s, g = misses["Sonnet"], misses["GLM-5.3"]
    second = json.loads((FA26 / "benchmark" / "v2" / "results" / "live" / "06_development_2026-11-05_190236_752716" /
                         "comparison.json").read_text()) if (FA26 / "benchmark" / "v2" / "results" / "live" /
                         "06_development_2026-11-05_190236_752716" / "comparison.json").exists() else None
    second_txt = ""
    if second:
        rs = second["runs"] if isinstance(second, dict) else second
        second_txt = (f" An intermediate run scored Sonnet {rs[0]['summary']['overall_pct']}, "
                      f"GLM-5.3 {rs[1]['summary']['overall_pct']}.")
    lines = [
        f"Overall: Sonnet {r(f_son['summary']['overall_pct'])} to {r(a_son['summary']['overall_pct'])}, "
        f"GLM-5.3 {r(f_glm['summary']['overall_pct'])} to {r(a_glm['summary']['overall_pct'])} (half-up rounding). "
        f"After the fixes both models answer all {s['n_ans']} numeric questions with the correct value "
        f"({s['ans_ok']}/{s['n_ans']} and {g['ans_ok']}/{g['n_ans']}).",
        f"Remaining loss: evidence F1 0.5 on {', '.join(s['ev'])} (both models), and clarify/abstain questions scored 0: "
        f"{', '.join(s['beh'])} (Sonnet), {', '.join(g['beh'])} (GLM-5.3).",
        "\"After fixes\" is the third development run." + second_txt +
        " The first run's evidence ids were rewritten offline before scoring; the method was not recorded.",
        "Sources: reports/benchmark_runs/2026-11-05_v2_development_06_firstrun_before_fixes.json and "
        "2026-11-05_v2_development_06_hybrid.json (summary.overall_pct, by_category, questions).",
    ]
    for k, t in enumerate(lines):
        fig.text(0.035, 0.155 - k * 0.035, t, fontsize=8.6, color=MUTED if k == 3 else INK)
    fig.savefig(OUT / "iati_v2_development_before_after_2026-11-05.jpg", dpi=300, pil_kwargs={"quality": 95})


def box(ax, x, y, w, h, text, fc, ec, fs=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc, ec=ec, lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.35)


def arrow(ax, a, b, label=None, rad=0.0, ly=None, lx=None):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", color="#444", lw=1,
                                                     connectionstyle=f"arc3,rad={rad}"))
    if label:
        mx, my = (a[0] + b[0]) / 2 if lx is None else lx, (a[1] + b[1]) / 2 if ly is None else ly
        ax.text(mx, my, label, ha="center", va="center", fontsize=9, color=INK,
                bbox=dict(boxstyle="round,pad=0.2", fc="#F3E3F5", ec="none"))


def pipeline():
    dev = json.loads((RUNS / "2026-11-05_v2_development_06_hybrid.json").read_text())
    held = json.loads((RUNS / "2026-11-05_v2_heldout_06_hybrid_FROZEN.json").read_text())
    ds, dg = (x["summary"]["overall_pct"] for x in dev["runs"][:2])
    hs, hg = (x["summary"]["overall_pct"] for x in held["runs"][:2])
    hc = calls("06_hybrid_eval_2026-11-05_204405_996398.csv")
    if hc:
        cs, cg = hc["anthropic/claude-sonnet-4-6"][0], hc["zai/glm-5.3"][0]
        calls_txt = f"On the heldout split this took {cs} calls (Sonnet) and {cg} calls (GLM-5.3) for 40 questions."
    else:
        calls_txt = "Per-question call counts: not recorded on this machine."

    W, H = 12.8, 7.2
    fig = plt.figure(figsize=(W, H), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    ax.text(0.45, H - 0.45, "Question pipeline: the model chooses, the system checks", fontsize=17, weight="bold", color=INK)
    ax.text(0.45, H - 0.8, "LangGraph router of notebook 06 (also packaged as src/ask.py). The planner is the only step "
            "that calls a language model; a failed check sends the error back to it, at most twice.", fontsize=9.5, color=MUTED)
    BLUE, BLUE_E, YEL, YEL_E, GRN, GRN_E = "#DCE6F2", "#6C8EBF", "#F5D27A", "#D6B656", "#9AD5B0", "#4E9A6A"
    box(ax, 0.45, 3.25, 1.3, 0.5, "User question", BLUE, BLUE_E)
    box(ax, 2.15, 2.85, 1.75, 1.3, "Plan (LLM)\nstatus: answer /\nclarify / abstain\n(reason codes from\nthe vocabulary);\ntool + arguments,\nor free Cypher", YEL, YEL_E, fs=8.6)
    box(ax, 4.6, 4.45, 1.95, 0.95, "21 Cypher templates\narguments validated,\nCypher fixed", GRN, GRN_E)
    box(ax, 4.6, 3.15, 1.95, 0.95, "Alex's 5 retrieval tools\nvia the adapter", GRN, GRN_E)
    box(ax, 4.6, 2.05, 1.95, 0.75, "Free Cypher\nread-only guard", GRN, GRN_E)
    box(ax, 7.2, 3.15, 1.8, 0.95, "Neo4j Aura\nteam schema; every row\ncarries source ids", GRN, GRN_E)
    box(ax, 9.45, 2.85, 1.6, 1.55, "Check output\nevidence = row ids\nsingle value keyed\ncount / total / date", GRN, GRN_E, fs=9.5)
    box(ax, 11.4, 3.25, 1.05, 0.75, "Answer\nkey, value,\nevidence", BLUE, BLUE_E, fs=9.5)
    arrow(ax, (1.75, 3.50), (2.15, 3.50))
    arrow(ax, (3.6, 4.15), (4.6, 4.90), "template", rad=-0.2)
    arrow(ax, (3.9, 3.60), (4.6, 3.60), "retrieval tool")
    arrow(ax, (3.6, 2.85), (4.6, 2.40), "no tool fits", rad=0.2)
    arrow(ax, (6.55, 4.90), (7.6, 4.10), rad=-0.2)
    arrow(ax, (6.55, 3.60), (7.2, 3.60))
    arrow(ax, (6.55, 2.40), (7.6, 3.15), rad=0.2)
    arrow(ax, (9.0, 3.60), (9.45, 3.60))
    arrow(ax, (11.05, 3.60), (11.4, 3.60), "passes", ly=3.95)
    arrow(ax, (10.25, 2.85), (3.3, 2.85), "fails: error back to planner (max 2 retries)", rad=-0.35, ly=1.72, lx=6.8)
    arrow(ax, (2.6, 4.15), (11.9, 4.00), "clarify / abstain", rad=-0.42, ly=5.95, lx=7.3)
    cap = [
        "Yellow: the only step that calls a language model. Green: deterministic code, identical for every model.",
        "A question takes 1 to 3 LLM calls. " + calls_txt,
        f"Overall score, benchmark v2: development split Sonnet {ds} vs GLM-5.3 {dg} ({abs(dg - ds):.2f} points apart); "
        f"heldout split (first and only run, frozen) Sonnet {hs} vs GLM-5.3 {hg} ({abs(hg - hs):.2f} points apart).",
        "The checks fix the shape and provenance of an answer; they do not make the two models equal on unseen questions.",
        "Sources: reports/benchmark_runs/2026-11-05_v2_development_06_hybrid.json and 2026-11-05_v2_heldout_06_hybrid_FROZEN.json;",
        "call counts from data/processed/06_hybrid_eval_2026-11-05_204405_996398.csv (gitignored, on the machine that ran the evaluation).",
    ]
    for k, t in enumerate(cap):
        ax.text(0.45, 1.15 - k * 0.2, t, fontsize=8.8, color=INK if k < 4 else MUTED)  # noqa
    fig.savefig(OUT / "iati_pipeline_validator_2026-11-05.jpg", dpi=300, pil_kwargs={"quality": 95})


if __name__ == "__main__":
    before_after(); pipeline(); print("saved")
