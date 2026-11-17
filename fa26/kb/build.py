"""
kb/build.py -- build the Milestone 1 knowledge base: one searchable entry
per activity in data/graph/, in a single SQLite file (data/kb/kb.sqlite).

Keyword search (SQLite FTS5, BM25 ranking) needs no model or server, gives
the same results every run, and the file can be copied or exported as is.
Embedding search is a later milestone, measured against this baseline.

Each entry carries the activity's source_id ("nodes_activities.csv:row:N",
rows counted from 1), so hits cite the same rows as the graph and the
query router. Build from benchmark/snapshot to cite the pinned snapshot.

Searchable fields: title, description, organisation names, standard sector
names (DAC / clusters / SDG; Oxfam's own categories are left out for the
same reason the hunger filter ignores them) and country names. Everything
else is stored alongside for filtering, citing and exporting.

    python -m kb.build                      # from fa26/, after the pipeline
    python -m kb.build --graph-dir DIR --out FILE
"""
import argparse
import csv
import datetime
import sqlite3
from collections import defaultdict
from pathlib import Path

from config import GRAPH_DIR, HOTSPOTS, KB_PATH, PUBLISHERS

csv.field_size_limit(10_000_000)

SCHEMA_VERSION = "2"
DESCRIPTION_CAP = 2000  # parse_filter.DESCRIPTION_MAX: longer text is cut there
STANDARD_SECTOR_VOCABS = {"1", "2", "7", "8", "10"}
STATUS = {"1": "Pipeline", "2": "Implementation", "3": "Finalisation",
          "4": "Closed", "5": "Cancelled", "6": "Suspended"}
ROLES = {"1": "funding", "2": "accountable", "3": "extending", "4": "implementing"}
# placeholders, not organisations (Oxfam GB anonymises partners and donors)
PLACEHOLDER_ORGS = {"Oxfam Partner(s)", "Oxfam Donor(s)"}

COLUMNS = ["iati_identifier", "source_id", "publisher", "publisher_name", "countries",
           "country_names", "title", "description", "description_truncated",
           "organisations", "funders", "implementers", "sectors", "status",
           "start_date", "end_date", "humanitarian", "match_basis",
           "confidence", "review_status", "match_terms"]
SEARCHED = ["title", "description", "organisations", "sectors", "places"]


def _rows(graph_dir, name):
    with open(graph_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _join(values):
    return "; ".join(sorted({v for v in values if v}))


def entries(graph_dir):
    """One dict per activity, ready to insert."""
    org_name = {o["ref"]: o["name"] for o in _rows(graph_dir, "nodes_organisations.csv")}
    sector_name = {s["sector_key"]: s["name"]
                   for s in _rows(graph_dir, "nodes_sectors.csv")
                   if s["vocabulary"] in STANDARD_SECTOR_VOCABS}

    orgs_by_role = defaultdict(lambda: defaultdict(set))
    for p in _rows(graph_dir, "rel_participates.csv"):
        name = org_name.get(p["org_ref"], "")
        if name and name not in PLACEHOLDER_ORGS:
            orgs_by_role[p["iati_identifier"]][ROLES.get(p["role"], "other")].add(name)
    sectors = defaultdict(set)
    for c in _rows(graph_dir, "rel_classified_as.csv"):
        if sector_name.get(c["sector_key"]):
            sectors[c["iati_identifier"]].add(sector_name[c["sector_key"]])

    out = []
    for n, a in enumerate(_rows(graph_dir, "nodes_activities.csv"), start=1):
        iid = a["iati_identifier"]
        codes = [c for c in a["hotspot_countries"].split("|") if c]
        roles = orgs_by_role[iid]
        out.append({
            "iati_identifier": iid,
            # same row id the Neo4j loader puts on the Activity node, and
            # the evidence format the query router checks
            "source_id": f"nodes_activities.csv:row:{n}",
            "publisher": a["publisher"],
            "publisher_name": PUBLISHERS.get(a["publisher"], {}).get("label", a["publisher"]),
            "countries": "|".join(codes),
            "country_names": _join(HOTSPOTS.get(c, {}).get("name", c) for c in codes),
            "title": a["title"],
            "description": a["description"],
            "description_truncated": int(len(a["description"]) >= DESCRIPTION_CAP),
            "organisations": _join(n for names in roles.values() for n in names),
            "funders": _join(roles["funding"]),
            "implementers": _join(roles["implementing"]),
            "sectors": _join(sectors[iid]),
            "status": STATUS.get(a["status"], a["status"]),
            "start_date": a["start_actual"] or a["start_planned"],
            "end_date": a["end_actual"] or a["end_planned"],
            "humanitarian": a["humanitarian"],
            "match_basis": a["match_basis"],
            "confidence": a.get("confidence", ""),
            "review_status": a.get("review_status", ""),
            "match_terms": a.get("match_terms", ""),
        })
    return out


def build(graph_dir=GRAPH_DIR, out=KB_PATH):
    graph_dir, out = Path(graph_dir), Path(out)
    rows = entries(graph_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute(f"CREATE TABLE activities ({', '.join(COLUMNS)}, "
               "PRIMARY KEY (iati_identifier))")
    # porter: "vouchers" finds "voucher"; remove_diacritics: "securite"
    # finds "sécurité" in WFP's French records
    db.execute("CREATE VIRTUAL TABLE activities_fts USING fts5("
               f"iati_identifier UNINDEXED, {', '.join(SEARCHED)}, "
               "tokenize = 'porter unicode61 remove_diacritics 2')")
    db.execute("CREATE TABLE kb_meta (key PRIMARY KEY, value)")
    db.executemany(f"INSERT INTO activities VALUES ({', '.join('?' * len(COLUMNS))})",
                   [[r[c] for c in COLUMNS] for r in rows])
    db.executemany("INSERT INTO activities_fts VALUES (?, ?, ?, ?, ?, ?)",
                   [(r["iati_identifier"], r["title"], r["description"],
                     r["organisations"], r["sectors"],
                     f'{r["country_names"]}; {r["publisher_name"]}') for r in rows])
    db.executemany("INSERT INTO kb_meta VALUES (?, ?)", [
        ("schema_version", SCHEMA_VERSION),
        ("built_on", datetime.date.today().isoformat()),
        ("source", str(graph_dir)),
        ("activities", str(len(rows))),
    ])
    db.commit()
    db.close()
    tmp.replace(out)  # a failed build never leaves a half-written KB
    truncated = sum(r["description_truncated"] for r in rows)
    print(f"[kb] {len(rows)} activities -> {out} "
          f"({truncated} descriptions cut at {DESCRIPTION_CAP} chars)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph-dir", type=Path, default=GRAPH_DIR)
    ap.add_argument("--out", type=Path, default=KB_PATH)
    args = ap.parse_args()
    build(args.graph_dir, args.out)
