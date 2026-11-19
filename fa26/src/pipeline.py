"""
pipeline.py -- one entrypoint for the whole IATI hunger-graph pipeline.

Stages (in order):
  download   fetch activity XML from the IATI Bulk Data Service
  update     live update: re-download only if due (every 7-14 days),
             rebuild graph CSVs only if files changed (live_updates.py)
  parse      filter to hunger x hotspot activities, write graph CSVs
  resolve    entity-resolve organisations, fill donor names
  sync       copy graph CSVs into spaces/data/ -- ONLY needed when
             preparing a Hugging Face Spaces upload; local runs of the
             app read data/graph/ directly

Usage:
    python src/pipeline.py all              # download -> parse -> resolve -> sync
    python src/pipeline.py refresh          # parse -> resolve -> sync (no download)
    python src/pipeline.py update           # scheduled live update (see live_updates.py)
    python src/pipeline.py update -- --force --interval-days 14
    python src/pipeline.py parse resolve    # any subset, in the order given
    python src/pipeline.py download -- --publisher wfp --dry-run
                                            # pass args through to one stage

Individual stages remain runnable directly (download.py, parse_filter.py,
resolve_orgs.py, visualize_html.py).
"""
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent

STAGES = {
    "download": SRC / "download.py",
    "parse": SRC / "parse_filter.py",
    "resolve": SRC / "resolve_orgs.py",
    "update": SRC / "live_updates.py",
}
ORDER = ["download", "update", "parse", "resolve", "sync"]
DEFAULT = ["download", "parse", "resolve"]


def sync():
    src, dst = ROOT / "data" / "graph", ROOT / "spaces" / "data"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src.glob("*.csv"):
        shutil.copy(f, dst / f.name)
        n += 1
    print(f"[sync] {n} CSVs -> {dst}")


def run_stage(name, extra):
    if name == "sync":
        return sync()
    print(f"[{name}] running {STAGES[name].name} ...")
    r = subprocess.run([sys.executable, str(STAGES[name]), *extra], cwd=SRC)
    if r.returncode != 0:
        sys.exit(f"[{name}] failed (exit {r.returncode}); stopping.")


if __name__ == "__main__":
    args = sys.argv[1:]
    extra = []
    if "--" in args:
        i = args.index("--")
        args, extra = args[:i], args[i + 1:]

    if not args or args == ["all"]:
        stages = DEFAULT
    elif args == ["refresh"]:
        stages = ["parse", "resolve"]
    else:
        bad = [a for a in args if a not in ORDER]
        if bad:
            sys.exit(f"unknown stage(s) {bad}; choose from {ORDER} or 'all'/'refresh'")
        stages = args

    if extra and len(stages) != 1:
        sys.exit("passthrough args (--) require exactly one stage")
    for s in stages:
        run_stage(s, extra)
    print("done.")
