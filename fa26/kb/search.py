"""
kb/search.py -- keyword search over the knowledge base, with filters,
citations (IATI identifiers) and CSV export.

    python -m kb.search "cash vouchers for food" --country YE
    python -m kb.search "school meals" --publisher wfp --limit 20 --export out.csv
    python -m kb.search "malnutrition" --min-confidence medium --json

A question is turned into an OR of its content words, so an activity that
matches more of them (and rarer ones) ranks higher, BM25-style. Words in
"double quotes" must appear together as a phrase.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

from config import HOTSPOTS, KB_PATH

# bm25() weights, in activities_fts column order:
# iati_identifier (unindexed), title, description, organisations, sectors, places
WEIGHTS = (0.0, 5.0, 1.0, 1.5, 1.5, 2.0)
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
# question words and words that describe every row, so they carry no signal
STOPWORDS = set("""
a an and are as at be by did do does for from has have how in into is it its
of on or that the their them there these this those to was were what when where
which who whom why will with about any all also show list find give me tell
project projects activity activities programme programmes program programs
""".split())

EXPORT_FIELDS = ["rank", "iati_identifier", "title", "publisher_name",
                 "country_names", "status", "start_date", "end_date",
                 "confidence", "match_basis", "funders", "implementers",
                 "sectors", "score", "snippet", "description"]


def to_fts_query(text):
    """Free text -> FTS5 query string, or "" if nothing searchable is left.
    Every term is quoted, so punctuation and FTS5 keywords (AND, NOT, NEAR)
    in a question can't cause syntax errors."""
    phrases = re.findall(r'"([^"]+)"', text)
    rest = re.sub(r'"[^"]*"', " ", text)
    terms = [f'"{p.strip()}"' for p in phrases if p.strip()]
    seen = set()
    for w in re.findall(r"\w+", rest.lower()):
        if len(w) > 1 and w not in STOPWORDS and w not in seen:
            seen.add(w)
            terms.append(f'"{w}"')
    return " OR ".join(terms)


def _country_code(value):
    if not value:
        return None
    v = value.strip()
    if v.upper() in HOTSPOTS:
        return v.upper()
    for code, info in HOTSPOTS.items():
        if info["name"].lower() == v.lower():
            return code
    raise ValueError(f"unknown hotspot country {value!r}; use a code such as YE")


def search(query, country=None, publisher=None, min_confidence=None,
           limit=10, kb_path=KB_PATH):
    """Ranked hits as dicts: every activities column plus rank, score
    (higher is better) and snippet (matched words in [brackets])."""
    fts = to_fts_query(query)
    if not fts:
        return []
    if not Path(kb_path).exists():
        raise FileNotFoundError(f"{kb_path} not found; run `python -m kb.build` first")
    where, params = ["activities_fts MATCH ?"], [fts]
    code = _country_code(country)
    if code:
        where.append("('|' || a.countries || '|') LIKE ?")
        params.append(f"%|{code}|%")
    if publisher:
        where.append("a.publisher = ?")
        params.append(publisher)
    if min_confidence:
        allowed = [c for c, n in CONFIDENCE_ORDER.items()
                   if n >= CONFIDENCE_ORDER[min_confidence]]
        where.append(f"a.confidence IN ({', '.join('?' * len(allowed))})")
        params += allowed
    sql = f"""
        SELECT a.*, bm25(activities_fts, {', '.join(map(str, WEIGHTS))}) AS bm25,
               snippet(activities_fts, -1, '[', ']', ' ... ', 24) AS snippet
        FROM activities_fts JOIN activities a USING (iati_identifier)
        WHERE {' AND '.join(where)}
        ORDER BY bm25 LIMIT ?"""
    db = sqlite3.connect(kb_path)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(sql, [*params, limit]).fetchall()
    finally:
        db.close()
    hits = []
    for i, r in enumerate(rows, 1):
        h = dict(r)
        h["rank"] = i
        h["score"] = round(-h.pop("bm25"), 3)  # SQLite's bm25 is lower-is-better
        hits.append(h)
    return hits


def export_csv(hits, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction="ignore",
                           lineterminator="\n")
        w.writeheader()
        w.writerows(hits)


def _print(hits):
    if not hits:
        print("no matches")
    for h in hits:
        print(f'{h["rank"]:>2}. {h["title"][:90]}')
        print(f'    {h["iati_identifier"]} | {h["publisher_name"]} | '
              f'{h["country_names"]} | confidence {h["confidence"] or "-"} | '
              f'score {h["score"]}')
        print(f'    {h["snippet"][:200]}')


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--country", help="hotspot country code or name, e.g. YE")
    ap.add_argument("--publisher", choices=["oxfamgb", "oxfamus", "wfp"])
    ap.add_argument("--min-confidence", choices=list(CONFIDENCE_ORDER))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--export", type=Path, help="write the hits to this CSV")
    ap.add_argument("--json", action="store_true", help="print hits as JSON")
    ap.add_argument("--kb", type=Path, default=KB_PATH)
    args = ap.parse_args()
    try:
        hits = search(args.query, args.country, args.publisher,
                      args.min_confidence, args.limit, args.kb)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(str(e))
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    else:
        _print(hits)
    if args.export:
        export_csv(hits, args.export)
        print(f"\n{len(hits)} hits -> {args.export}")
