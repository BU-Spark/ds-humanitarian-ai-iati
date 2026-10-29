"""
evaluate_filter.py -- draw and score hand-labelled samples for the hunger
filter. Builds on John's evaluate_hunger_filter.py (branch `john`).

  python src/evaluate_filter.py sample data/hunger_filter_sample_devansh_50.csv \
         --exclude data/hunger_filter_sample_50.csv
      Draw a blind labelling sheet from hotspot activities in data/raw/:
      random within each publisher (QUOTAS), no filter predictions shown.
      Parsed records go to a sidecar <name>_records.json, because some are
      too long for a spreadsheet cell.

  python src/evaluate_filter.py score data/hunger_filter_sample_50.csv
      Score the current hunger_match() against manual_label (yes/no).
      keyword_weak counts as kept, as in the pipeline; --weak-as-no to
      score it as dropped.

Records are read from a record_json column if the CSV has one (John's
format), otherwise from the sidecar.
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import parse_filter as pf
from config import PUBLISHERS, RAW_DIR

QUOTAS = {"oxfamgb": 25, "wfp": 15, "oxfamus": 10}
SEED = 2026
SHEET_FIELDS = ["activity_id", "publisher", "hotspot_countries", "title",
                "description", "sector_codes", "sector_names",
                "manual_label", "notes"]

csv.field_size_limit(10_000_000)


def hotspot_records():
    """Every distinct activity in data/raw/ that passes the geography
    filter, as {publisher: [rec, ...]}."""
    out, seen = {p: [] for p in PUBLISHERS}, set()
    for pub in PUBLISHERS:
        for xml_path in sorted((RAW_DIR / pub).glob("*.xml")):
            for _, act in ET.iterparse(xml_path, events=("end",)):
                if act.tag != "iati-activity":
                    continue
                rec = pf.parse_activity(act, pub)
                act.clear()
                if rec is None:
                    continue
                iid = rec["activity"]["iati_identifier"]
                if iid in seen or not pf.hotspot_codes(rec):
                    continue
                seen.add(iid)
                out[pub].append(rec)
    return out


def records_path(sheet: Path) -> Path:
    return sheet.with_name(sheet.stem + "_records.json")


def read_ids(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["activity_id"] for r in csv.DictReader(f)}


def sample(out: Path, exclude):
    skip = set().union(*(read_ids(p) for p in exclude)) if exclude else set()
    pool = hotspot_records()
    rng = random.Random(SEED)
    picked = []
    for pub, n in QUOTAS.items():
        candidates = [r for r in pool[pub]
                      if r["activity"]["iati_identifier"] not in skip]
        picked += rng.sample(candidates, min(n, len(candidates)))
        print(f"{pub}: {min(n, len(candidates))} of {len(candidates)} hotspot activities")
    rng.shuffle(picked)  # mix publishers so labelling order carries no signal

    rows = [{
        "activity_id": r["activity"]["iati_identifier"],
        "publisher": r["activity"]["publisher"],
        "hotspot_countries": "; ".join(sorted(pf.hotspot_codes(r))),
        "title": r["activity"]["title"],
        "description": r["activity"]["description"],
        "sector_codes": "; ".join(f'{s["code"]} (vocab {s["vocabulary"]})'
                                  for s in r["sectors"]),
        "sector_names": "; ".join(s["name"] for s in r["sectors"] if s["name"]),
        "manual_label": "", "notes": "",
    } for r in picked]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(records_path(out), "w", encoding="utf-8") as f:
        json.dump({r["activity"]["iati_identifier"]: r for r in picked}, f)
    print(f"{len(rows)} rows -> {out}\nrecords -> {records_path(out)}")


def load_labelled(path: Path):
    """[(row, rec)] for every row with a yes/no manual_label."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    sidecar = {}
    if rows and "record_json" not in rows[0]:
        with open(records_path(path), encoding="utf-8") as f:
            sidecar = json.load(f)
    return [(r, json.loads(r["record_json"]) if "record_json" in r
             else sidecar[r["activity_id"]])
            for r in rows if r["manual_label"].strip().lower() in ("yes", "no")]


def confusion(labelled, weak_as_yes=True):
    """(tp, fp, tn, fn, misses) where misses lists disagreeing rows."""
    tp = fp = tn = fn = 0
    misses = []
    for row, rec in labelled:
        actual = row["manual_label"].strip().lower() == "yes"
        kept, basis = pf.hunger_match(rec)
        predicted = kept and (weak_as_yes or basis != "keyword_weak")
        tp += predicted and actual
        fp += predicted and not actual
        tn += not predicted and not actual
        fn += actual and not predicted
        if predicted != actual:
            misses.append((row, basis))
    return tp, fp, tn, fn, misses


def score(path: Path, weak_as_yes=True):
    labelled = load_labelled(path)
    if not labelled:
        sys.exit(f"no yes/no labels in {path}")
    tp, fp, tn, fn, misses = confusion(labelled, weak_as_yes)
    n = len(labelled)
    print(f"{path.name}: n={n}  TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"  accuracy {(tp + tn) / n:.0%}  "
          f"precision {tp / (tp + fp) if tp + fp else 0:.0%}  "
          f"recall {tp / (tp + fn) if tp + fn else 0:.0%}")
    for row, basis in misses:
        print(f"  label={row['manual_label']:<3} filter={basis:<15} {row['title'][:70]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("out", type=Path)
    s.add_argument("--exclude", type=Path, nargs="*", default=[])
    c = sub.add_parser("score")
    c.add_argument("csv", type=Path)
    c.add_argument("--weak-as-no", action="store_true")
    args = ap.parse_args()
    if args.cmd == "sample":
        sample(args.out, args.exclude)
    else:
        score(args.csv, weak_as_yes=not args.weak_as_no)
