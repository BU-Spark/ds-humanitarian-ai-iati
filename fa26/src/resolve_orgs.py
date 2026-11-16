"""
05_resolve_orgs.py -- First-pass entity resolution for organisations.

The raw IATI data references the same organisation inconsistently:
  - bare DAC/CRS channel refs with no name (XM-DAC-302, XM-DAC-41140)
  - name-only references we stored as pseudo-refs (name:World Food Programme)
  - case/whitespace variants of the same ref or name

This script rewrites the graph CSVs in place (with .bak backups):
  1. canonicalize refs (trim, uppercase the ref part)
  2. propagate names: if any record supplies a name for a ref, all get it
  3. merge name-only pseudo-refs into a real ref whose name matches
  4. merge orgs whose normalized names match across different pseudo-refs
  5. fill names for bare XM-DAC refs from the official codelists
     (CRS channel codes + DAC donors, fetched at runtime; --offline skips)
  6. apply the manual alias table below for known variants

It is deliberately conservative: refs are never merged with other real refs
unless listed in ALIASES, because two distinct refs may legitimately share
a name. Everything it does is written to resolution_report.json.

Usage:
    python 05_resolve_orgs.py             # resolve + rewrite CSVs
    python 05_resolve_orgs.py --dry-run   # report only, no rewrites
    python 05_resolve_orgs.py --offline   # skip codelist download
"""
import argparse
import csv
import json
import re
import shutil
import urllib.request

from config import GRAPH_DIR

# Known same-organisation ref variants (canonical <- variants). Extend as
# found; keep to cases you are sure about.
ALIASES = {
    "XM-DAC-12-1": ["GB-GOV-1"],            # FCDO (formerly DFID)
    "XM-DAC-41140": ["XM-DAC-41140-CERF"],  # example pattern; adjust to data
}

# CRS channel codes (multilaterals/NGOs): XM-DAC-41140 = WFP, etc.
CHANNEL_URL = "https://codelists.codeforiati.org/api/json/en/CRSChannelCode.json"
# OECD DAC donor + agency lists (bilaterals): XM-DAC-302 = United States,
# XM-DAC-918-1 = EU institutions agency 1. Stable r-links from
# https://datahub.io/core/dac-and-crs-code-lists
DATAHUB = "https://datahub.io/core/dac-and-crs-code-lists/_r/-/data/"
DAC_MEMBERS_CSV = "dac_members.csv"   # NOTE: columns shifted upstream --
AGENCY_CSV = "agencies.csv"           # name_en holds ISO3, name_fr holds the
                                      # English name; handled in the parser.
# The upstream multilateral/non-DAC donor files are unusable (empty or
# column-mangled), so the common multilateral donor codes are built in,
# transcribed from the recoverable rows of the OECD list:
MULTILATERAL_DONORS = {
    "26": "Nordic Development Fund", "30": "UNEP",
    "45": "Global Environment Facility", "55": "Montreal Protocol Fund",
    "62": "IBRD (World Bank)", "70": "MIGA", "72": "IFC",
    "77": "IDA (World Bank)", "87": "Caribbean Development Bank",
    "130": "IMF", "133": "Inter-American Development Bank",
    "358": "Central American Bank for Economic Integration",
    "543": "African Development Bank", "546": "African Development Fund",
    "552": "Asian Development Bank", "561": "Arab Fund (AFESD)",
    "566": "UN Peacebuilding Fund", "576": "Council of Europe",
    "611": "WHO", "613": "FAO", "732": "ILO", "764": "IAEA", "765": "UNECE",
}

ORG_FILES_REF_COLS = [
    ("rel_reports.csv", "org_ref"),
    ("rel_participates.csv", "org_ref"),
    ("rel_transaction_edges.csv", "org_ref"),
]


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    s = re.sub(r"\b(the|of|for|and)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def canon_ref(ref: str) -> str:
    ref = ref.strip()
    if ref.lower().startswith("name:"):
        return "name:" + ref[5:].strip()
    return ref.upper()


def read(name):
    with open(GRAPH_DIR / name, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames


def write(name, rows, fields):
    shutil.copy(GRAPH_DIR / name, GRAPH_DIR / (name + ".bak"))
    with open(GRAPH_DIR / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_codelist_names():
    """Map XM-DAC-* refs to names from three official sources:
    CRS channel codes, DAC donor lists, and the DAC agency list."""
    names = {}
    try:  # channels (JSON)
        data = json.loads(_get(CHANNEL_URL))
        for item in data.get("data", []):
            code, name = str(item.get("code", "")), item.get("name", "")
            if code and name:
                names[f"XM-DAC-{code}"] = name
    except Exception as e:
        print(f"[warn] channel codelist fetch failed: {e}")
    try:  # DAC members: code / ISO3 / English name (headers mislabeled)
        for row in csv.DictReader(_get(DATAHUB + DAC_MEMBERS_CSV).splitlines()):
            code = row.get("code", "")
            name = row.get("name_fr") or row.get("name_en") or ""
            if code.isdigit() and name and not re.fullmatch(r"[A-Z]{2,3}", name):
                names.setdefault(f"XM-DAC-{code}", name)
    except Exception as e:
        print(f"[warn] DAC members fetch failed: {e}")
    for code, name in MULTILATERAL_DONORS.items():
        names.setdefault(f"XM-DAC-{code}", name)
    try:  # LOWEST priority: some publishers (e.g. WFP) reference host
        # governments and non-DAC state donors by DAC *recipient* codes
        # under the same XM-DAC prefix; fill remaining gaps from there
        for row in csv.DictReader(_get(DATAHUB + "recipients.csv").splitlines()):
            if row.get("code") and row.get("name_en"):
                names.setdefault(f'XM-DAC-{row["code"]}', row["name_en"])
    except Exception as e:
        print(f"[warn] recipients fetch failed: {e}")
    try:  # agencies (CSV: code,donor_name_en,...,agency_code,agency_name_en,...,acronym)
        for row in csv.DictReader(_get(DATAHUB + AGENCY_CSV).splitlines()):
            d, a = row.get("code", ""), row.get("agency_code", "")
            label = row.get("acronym") or row.get("agency_name_en") or ""
            if d and a and label:
                names[f"XM-DAC-{d}-{a}"] = label
    except Exception as e:
        print(f"[warn] agency codelist fetch failed: {e}")
    return names


def codelist_lookup(ref, names):
    """Exact ref, else strip the agency suffix and use the donor name."""
    if ref in names:
        return names[ref]
    m = re.fullmatch(r"(XM-DAC-\d+)-[\w.]+", ref)
    if m and m.group(1) in names:
        return names[m.group(1)]
    return ""


def main(dry_run=False, offline=False):
    orgs, org_fields = read("nodes_organisations.csv")
    report = {"merges": [], "names_filled": 0, "refs_canonicalized": 0}

    # pass 1: canonical refs
    mapping = {}
    for o in orgs:
        c = canon_ref(o["ref"])
        if c != o["ref"]:
            report["refs_canonicalized"] += 1
        mapping[o["ref"]] = c
        o["ref"] = c

    # collapse duplicates created by canonicalization, keep best name
    by_ref = {}
    for o in orgs:
        cur = by_ref.get(o["ref"])
        if cur is None or (not cur["name"] and o["name"]):
            by_ref[o["ref"]] = {**(cur or {}), **{k: v for k, v in o.items() if v}} \
                if cur else o

    # pass 2: merge name-only pseudo-refs into real refs by normalized name
    name_to_ref = {norm_name(o["name"]): r for r, o in by_ref.items()
                   if o["name"] and not r.startswith("name:")}
    for r in [r for r in by_ref if r.startswith("name:")]:
        target = name_to_ref.get(norm_name(r[5:]))
        if target:
            mapping.update({k: target for k, v in mapping.items() if v == r})
            report["merges"].append({"from": r, "to": target, "rule": "name_match"})
            by_ref.pop(r)

    # pass 3: manual aliases
    for canonical, variants in ALIASES.items():
        for v in variants:
            v = canon_ref(v)
            if v in by_ref:
                if canonical not in by_ref:
                    by_ref[canonical] = {**by_ref[v], "ref": canonical}
                elif not by_ref[canonical]["name"] and by_ref[v]["name"]:
                    by_ref[canonical]["name"] = by_ref[v]["name"]
                by_ref.pop(v)
                mapping.update({k: canonical for k, val in mapping.items() if val == v})
                report["merges"].append({"from": v, "to": canonical, "rule": "alias"})

    # pass 4: fill missing names from official codelists
    if not offline:
        codelist = fetch_codelist_names()
        for r, o in by_ref.items():
            # repair earlier bad fills: bare ISO codes on XM-DAC refs
            if (o["name"] and re.fullmatch(r"[A-Z]{2,3}", o["name"])
                    and re.fullmatch(r"XM-DAC-\d+", r)):
                o["name"] = ""
            if not o["name"]:
                found = codelist_lookup(r, codelist)
                if found:
                    o["name"] = found
                    report["names_filled"] += 1

    report["orgs_before"] = len(orgs)
    report["orgs_after"] = len(by_ref)
    print(f"organisations: {len(orgs)} -> {len(by_ref)} "
          f"({len(report['merges'])} merges, {report['names_filled']} names filled, "
          f"{report['refs_canonicalized']} refs canonicalized)")

    if dry_run:
        print(json.dumps(report["merges"][:20], indent=2))
        return

    new_orgs = [{f: o.get(f, "") for f in org_fields} for o in by_ref.values()]
    write("nodes_organisations.csv", new_orgs, org_fields)
    for fname, col in ORG_FILES_REF_COLS:
        rows, fields = read(fname)
        for row in rows:
            row[col] = mapping.get(row[col], canon_ref(row[col]))
        write(fname, rows, fields)
    with open(GRAPH_DIR / "resolution_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"CSVs rewritten (.bak backups kept); report -> resolution_report.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    main(args.dry_run, args.offline)