"""
01_download.py -- Pull IATI activity XML via the IATI Bulk Data Service.

The old IATI Registry (CKAN) was replaced in December 2025. This script now
uses the Bulk Data Service (https://bulk-data.iatistandard.org/), which
exposes two JSON indices:

  /datasets-minimal   every registered dataset, incl. a cached XML URL
                      hosted on the bulk service itself (more reliable
                      than publishers' own servers)
  /reporting-orgs     every publisher, for slug lookup

We fetch the dataset index once, filter to our publishers, keep only files
likely to contain hotspot-country activities (per-country file naming like
"oxfamgb-ss"), and download the cached XML for each.

Usage:
    python 01_download.py                       # all configured publishers
    python 01_download.py --publisher wfp       # one publisher
    python 01_download.py --find-publisher oxfam    # look up publisher slugs
    python 01_download.py --all-files           # skip country heuristic
    python 01_download.py --index-file idx.json # reuse a saved index
    python 01_download.py --dry-run             # list what would be fetched
"""
import argparse
import json
import re
import sys
import time
import urllib.request

from config import PUBLISHERS, HOTSPOTS, RAW_DIR, EXTRA_DATASETS

BULK = "https://bulk-data.iatistandard.org"
UA = {"User-Agent": "BU-Spark-IATI-prototype/0.2 (feasibility research)"}


def get_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def find_publisher(query: str) -> None:
    data = get_json(f"{BULK}/reporting-orgs")
    orgs = data.get("reporting_orgs", data) if isinstance(data, dict) else data
    q = query.lower()
    hits = 0
    for org in orgs:
        blob = json.dumps(org).lower()
        if q in blob:
            short = org.get("short_name", "?")
            name = org.get("title") or org.get("name") or ""
            print(f"  slug={short:<25} {name}")
            hits += 1
    if not hits:
        print(f"  no publisher matching '{query}'")


# --- which dataset files to fetch -----------------------------------------
ISO2 = {c.lower() for c in HOTSPOTS}
GLOBAL_HINTS = ("998", "global", "regional", "activities", "activity")
ORG_FILE_SUFFIXES = ("org", "orgfile", "organisation", "organization")


def wanted(short_name: str, all_files: bool) -> bool:
    suffix = short_name.rsplit("-", 1)[-1].lower()
    if suffix in ORG_FILE_SUFFIXES:
        return False                     # organisation file, no activities
    if short_name in EXTRA_DATASETS:
        return True                      # forced include from config
    if all_files:
        return True
    if suffix in ISO2:
        return True                      # per-country file for a hotspot
    if any(h in short_name.lower() for h in GLOBAL_HINTS):
        return True                      # global/regional file
    if not re.fullmatch(r"[a-z]{2}|\d{3}", suffix):
        return True                      # not per-country naming: take whole file
    return False                         # per-country file for a non-hotspot


def run(publishers, all_files=False, index_file=None, dry_run=False):
    if index_file:
        with open(index_file, encoding="utf-8") as f:
            index = json.load(f)
    else:
        print(f"Fetching dataset index {BULK}/datasets-minimal ...")
        index = get_json(f"{BULK}/datasets-minimal")

    datasets = index["datasets"]
    print(f"Index contains {len(datasets)} datasets total")

    for pub in publishers:
        mine = [d for d in datasets if d.get("reporting_org_short_name") == pub]
        if not mine:
            print(f"[{pub}] NOT FOUND in index -- check slug with --find-publisher")
            continue
        picked = [d for d in mine if wanted(d.get("short_name", ""), all_files)]
        skipped = sorted(d.get("short_name", "?") for d in mine if d not in picked)
        print(f"[{pub}] {len(mine)} datasets, {len(picked)} selected"
              + (f", excluded: {', '.join(skipped)}" if skipped else ""))

        outdir = RAW_DIR / pub
        outdir.mkdir(parents=True, exist_ok=True)
        ok = fail = 0
        for d in picked:
            good = d.get("last_known_good_dataset") or {}
            url = good.get("cached_dataset_url_xml") or d.get("source_url")
            name = d.get("short_name", d.get("id", "unknown"))
            if not url:
                print(f"  skip {name}: no usable URL (never validated?)")
                continue
            if dry_run:
                print(f"  would fetch {name}  <- {url}")
                continue
            dest = outdir / f"{name}.xml"
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                    f.write(r.read())
                ok += 1
                print(f"  ok   {name}")
            except Exception as e:
                fail += 1
                print(f"  FAIL {name}: {e}", file=sys.stderr)
            time.sleep(0.3)
        if not dry_run:
            print(f"[{pub}] downloaded {ok} files ({fail} failed) -> {outdir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--publisher", help="single publisher slug")
    ap.add_argument("--find-publisher", help="search reporting-orgs index for slugs")
    ap.add_argument("--all-files", action="store_true",
                    help="download every activity file, not just hotspot/global")
    ap.add_argument("--index-file", help="path to a saved datasets-minimal JSON")
    ap.add_argument("--dry-run", action="store_true",
                    help="show selection without downloading")
    args = ap.parse_args()

    if args.find_publisher:
        find_publisher(args.find_publisher)
        sys.exit(0)

    pubs = [args.publisher] if args.publisher else list(PUBLISHERS)
    run(pubs, args.all_files, args.index_file, args.dry_run)
