"""
02_parse_and_filter.py -- Parse IATI activity XML into graph-ready CSVs (v0.3).

Keeps an activity if BOTH are true:
  (a) geography: a recipient-country (activity or transaction level) is a
      Hunger Hotspot country (June-Nov 2026 outlook)
  (b) theme: hunger-relevant sector coding (DAC codes/categories or
      humanitarian clusters), keyword fallback only when no sectors exist

v0.3 additions: Budget nodes, Emergency nodes (humanitarian-scope: GLIDE +
HRP codes), SDG tag nodes, PolicyMarker nodes, Region nodes, typed
related-activity edges, and aid/finance/flow/tied-status/scope properties
on the Activity node.

Usage:
    python 02_parse_and_filter.py                 # default filters
    python 02_parse_and_filter.py --no-theme      # geography-only coverage scan
    python 02_parse_and_filter.py --publisher wfp
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

from config import (PUBLISHERS, HOTSPOTS, HUNGER_DAC_CODES,
                    HUNGER_DAC_CATEGORIES, HUNGER_CLUSTER_CODES,
                    INCLUDE_GENERAL_EMERGENCY, HUNGER_KEYWORDS_STRONG,
                    HUNGER_KEYWORDS_WEAK, ORG_NAME_PATTERNS, SDG_HUNGER_GOAL,
                    RAW_DIR, GRAPH_DIR)

STRONG_RE = re.compile("|".join(re.escape(k) for k in HUNGER_KEYWORDS_STRONG), re.I)
WEAK_RE = re.compile("|".join(re.escape(k) for k in HUNGER_KEYWORDS_WEAK), re.I)
ORG_RE = re.compile("|".join(ORG_NAME_PATTERNS), re.I)
DESCRIPTION_MAX = 2000  # chars stored on the Activity node
DAC = HUNGER_DAC_CODES | ({"72010"} if INCLUDE_GENERAL_EMERGENCY else set())

# IATI 1.x used string vocabulary/type codes; normalize to 2.x numerics
VOCAB_MAP = {"DAC": "1", "DAC-3": "2", "RO": "99", "RO2": "98"}
TX_TYPE_MAP = {"IF": "1", "C": "2", "D": "3", "E": "4", "IR": "5",
               "LR": "6", "R": "7", "QP": "8", "Q3": "9", "CG": "10"}
RECOGNIZED_VOCABS = {"1", "2", "10"}

# tag vocabularies for SDGs: 2 = goals, 3 = targets
SDG_VOCABS = {"2", "3"}


# ---------------------------------------------------------------- helpers --
def text(el, path, default=""):
    node = el.find(path)
    if node is None:
        return default
    narr = node.find("narrative")
    src = narr if narr is not None else node
    return (src.text or default).strip()


def narratives(el, path):
    return "; ".join(
        (n.text or "").strip()
        for node in el.findall(path)
        for n in ([node.find("narrative")] if node.find("narrative") is not None else [node])
        if n is not None and n.text
    )


def attr(el, path, name, default=""):
    node = el.find(path)
    return node.get(name, default) if node is not None else default


def is_hunger_sector(code: str, vocab: str) -> bool:
    vocab = VOCAB_MAP.get(vocab, vocab) or "1"
    if vocab in ("1", ""):
        return code in DAC
    if vocab == "2":
        return code in HUNGER_DAC_CATEGORIES or code[:3] in HUNGER_DAC_CATEGORIES
    if vocab == "10":
        return code in HUNGER_CLUSTER_CODES
    return False


def get_date(act, code, name_1x):
    """activity-date: numeric @type in 2.x, string @type (and sometimes the
    date only as element text) in 1.x."""
    for t in (code, name_1x):
        node = act.find(f"activity-date[@type='{t}']")
        if node is not None:
            return node.get("iso-date") or (node.text or "").strip()
    return ""


# ---------------------------------------------------------------- parsing --
def parse_activity(act, publisher):
    iid = text(act, "iati-identifier")
    if not iid:
        return None

    rep = act.find("reporting-org")
    rec = {
        "activity": {
            "iati_identifier": iid,
            "title": text(act, "title"),
            # full text here so the keyword fallback sees all of it;
            # truncated to DESCRIPTION_MAX when the activity is written
            "description": narratives(act, "description"),
            "status": attr(act, "activity-status", "code"),
            "humanitarian": act.get("humanitarian", ""),
            "start_planned": get_date(act, "1", "start-planned"),
            "start_actual": get_date(act, "2", "start-actual"),
            "end_planned": get_date(act, "3", "end-planned"),
            "end_actual": get_date(act, "4", "end-actual"),
            "default_currency": act.get("default-currency", ""),
            "publisher": publisher,
            "hierarchy": act.get("hierarchy", "1"),
            "last_updated": act.get("last-updated-datetime", ""),
            # v0.3 classification properties (IATI codelists)
            "aid_type": attr(act, "default-aid-type", "code"),
            "finance_type": attr(act, "default-finance-type", "code"),
            "flow_type": attr(act, "default-flow-type", "code"),
            "tied_status": attr(act, "default-tied-status", "code"),
            "collaboration_type": attr(act, "collaboration-type", "code"),
            "scope": attr(act, "activity-scope", "code"),
            "capital_spend": attr(act, "capital-spend", "percentage"),
        },
        "reporting_org": {
            "ref": (rep.get("ref", "") if rep is not None else "") or f"unknown:{publisher}",
            "name": text(act, "reporting-org"),
            "type": rep.get("type", "") if rep is not None else "",
        },
        "participating": [],
        "countries": [],
        "regions": [],
        "locations": [],
        "sectors": [],
        "transactions": [],
        "budgets": [],
        "emergencies": [],
        "tags": [],
        "markers": [],
        "related": [],
    }

    for p in act.findall("participating-org"):
        rec["participating"].append({
            "ref": p.get("ref", ""),
            "name": text(p, ".") or (p.findtext("narrative") or "").strip(),
            "role": p.get("role", ""),
            "type": p.get("type", ""),
        })

    for c in act.findall("recipient-country"):
        rec["countries"].append({
            "code": c.get("code", "").upper(),
            "percentage": c.get("percentage", ""),
        })

    for r in act.findall("recipient-region"):
        rec["regions"].append({
            "code": r.get("code", ""),
            "vocabulary": r.get("vocabulary", "1"),
            "percentage": r.get("percentage", ""),
            "name": text(r, "."),
        })

    for loc in act.findall("location"):
        point = loc.find("point/pos")
        coords = (point.text or "").strip() if point is not None else ""
        lat, lon = (coords.split() + ["", ""])[:2] if coords else ("", "")
        rec["locations"].append({
            "name": text(loc, "name"),
            "ref": loc.get("ref", ""),
            "lat": lat, "lon": lon,
            "adm_code": attr(loc, "administrative", "code"),
            "adm_vocab": attr(loc, "administrative", "vocabulary"),
            "feature": attr(loc, "feature-designation", "code"),
        })

    for s in act.findall("sector"):
        v = s.get("vocabulary", "1") or "1"
        rec["sectors"].append({
            "code": s.get("code", ""),
            "vocabulary": VOCAB_MAP.get(v, v),
            "percentage": s.get("percentage", ""),
            "name": text(s, "."),
        })

    for i, t in enumerate(act.findall("transaction")):
        val = t.find("value")
        rec["transactions"].append({
            "tx_id": f"{iid}#tx{i}",
            "type": TX_TYPE_MAP.get(attr(t, "transaction-type", "code"),
                                     attr(t, "transaction-type", "code")),
            "date": attr(t, "transaction-date", "iso-date"),
            "value": (val.text or "").strip() if val is not None else "",
            # IATI: value/@currency defaults to iati-activity/@default-currency
            "currency": (val.get("currency", "") if val is not None else "")
                        or act.get("default-currency", ""),
            "value_date": val.get("value-date", "") if val is not None else "",
            "provider_ref": attr(t, "provider-org", "ref"),
            "provider_name": text(t, "provider-org"),
            "receiver_ref": attr(t, "receiver-org", "ref"),
            "receiver_name": text(t, "receiver-org"),
            "recipient_country": attr(t, "recipient-country", "code").upper(),
            "sector_code": attr(t, "sector", "code"),
            "sector_vocab": attr(t, "sector", "vocabulary"),
            "aid_type": attr(t, "aid-type", "code"),
            "humanitarian": t.get("humanitarian", ""),
        })

    for i, b in enumerate(act.findall("budget")):
        val = b.find("value")
        rec["budgets"].append({
            "budget_id": f"{iid}#b{i}",
            "type": b.get("type", "1"),          # 1 original, 2 revised
            "status": b.get("status", "1"),      # 1 indicative, 2 committed
            "period_start": attr(b, "period-start", "iso-date"),
            "period_end": attr(b, "period-end", "iso-date"),
            "value": (val.text or "").strip() if val is not None else "",
            "currency": (val.get("currency", "") if val is not None else "")
                        or act.get("default-currency", ""),
        })

    for h in act.findall("humanitarian-scope"):
        rec["emergencies"].append({
            "type": h.get("type", ""),           # 1 emergency, 2 appeal
            "vocabulary": h.get("vocabulary", ""),  # 1-2 GLIDE, 2-1 HRP
            "code": h.get("code", ""),
            "name": text(h, "."),
        })

    for tg in act.findall("tag"):
        rec["tags"].append({
            "vocabulary": tg.get("vocabulary", ""),
            "code": tg.get("code", ""),
            "name": text(tg, "."),
        })

    for m in act.findall("policy-marker"):
        rec["markers"].append({
            "vocabulary": m.get("vocabulary", "1"),
            "code": m.get("code", ""),
            "significance": m.get("significance", ""),
            "name": text(m, "."),
        })

    for r in act.findall("related-activity"):
        rec["related"].append({"ref": r.get("ref", ""), "type": r.get("type", "")})

    return rec


def hotspot_codes(rec):
    codes = {c["code"] for c in rec["countries"] if c["code"] in HOTSPOTS}
    codes |= {t["recipient_country"] for t in rec["transactions"]
              if t["recipient_country"] in HOTSPOTS}
    return codes


def hunger_match(rec, dropped_codes=None):
    """Sector codes are authoritative only for recognized vocabularies (DAC
    5-digit, DAC categories, humanitarian clusters). Publishers like Oxfam GB
    use their own sector vocabulary ("5 Aims"), which we can't code-match --
    for those, fall back to SDG 2 sector tags, then keywords over title +
    description (organisation names removed). Returns (matched, basis) with
    basis one of: sector, sector_no_match, sdg, keyword, keyword_weak,
    no_signal."""
    sectors = rec["sectors"] + [
        {"code": t["sector_code"],
         "vocabulary": VOCAB_MAP.get(t["sector_vocab"], t["sector_vocab"]) or "1",
         "name": ""}
        for t in rec["transactions"] if t["sector_code"]
    ]
    # 998/998xx = "unallocated/unspecified": no thematic signal, so it must
    # not block the keyword fallback (Oxfam America publishes only 998)
    recognized = [s for s in sectors
                  if s["code"] and (s.get("vocabulary") or "1") in RECOGNIZED_VOCABS
                  and not s["code"].startswith("998")]
    if recognized:
        for s in recognized:
            if is_hunger_sector(s["code"], s.get("vocabulary", "1")):
                return True, "sector"
        if dropped_codes is not None:
            for s in recognized:
                dropped_codes[f'{s.get("vocabulary","1")}:{s["code"]}'] += 1
        return False, "sector_no_match"
    if any(s["code"] == SDG_HUNGER_GOAL if s.get("vocabulary") == "7"
           else s["code"].startswith(SDG_HUNGER_GOAL + ".")
           for s in sectors if s.get("vocabulary") in ("7", "8")):
        return True, "sdg"
    blob = ORG_RE.sub(" ", " ".join([rec["activity"]["title"],
                                     rec["activity"]["description"]]))
    if STRONG_RE.search(blob):
        return True, "keyword"
    if WEAK_RE.search(blob):
        return True, "keyword_weak"
    return False, "no_signal"


# ------------------------------------------------------------------ main --
def run(publisher_filter=None, apply_theme=True):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)

    activities, locations, budgets, transactions = [], [], [], []
    orgs, sectors, emergencies, tags, markers, regions = {}, {}, {}, {}, {}, {}
    rel = defaultdict(list)
    stats = Counter()
    funnel = defaultdict(Counter)
    dropped_sectors = defaultdict(Counter)
    per_pub_country = defaultdict(Counter)
    years = defaultdict(Counter)

    seen_ids = set()

    def process(rec, pub):
        iid0 = rec["activity"]["iati_identifier"]
        if iid0 in seen_ids:
            stats["dropped_duplicate"] += 1
            return
        seen_ids.add(iid0)
        funnel[pub]["seen"] += 1
        hs = hotspot_codes(rec)
        if not hs:
            stats["dropped_geography"] += 1
            funnel[pub]["dropped_geography"] += 1
            return
        matched, how = (True, "geo_only")
        if apply_theme:
            matched, how = hunger_match(rec, dropped_sectors[pub])
        if not matched:
            stats[f"dropped_theme_{how}"] += 1
            funnel[pub][f"dropped_theme_{how}"] += 1
            return

        stats["kept"] += 1
        stats[f"kept_via_{how}"] += 1
        funnel[pub][f"kept_via_{how}"] += 1
        a = rec["activity"]
        iid = a["iati_identifier"]
        a["hotspot_countries"] = "|".join(sorted(hs))
        a["match_basis"] = how
        a["description"] = a["description"][:DESCRIPTION_MAX]
        activities.append(a)

        start = a["start_actual"] or a["start_planned"]
        if start[:4].isdigit():
            years[pub][start[:4]] += 1
        for c in hs:
            per_pub_country[pub][c] += 1

        ro = rec["reporting_org"]
        orgs.setdefault(ro["ref"], ro)
        rel["reports"].append({"org_ref": ro["ref"], "iati_identifier": iid})

        for p in rec["participating"]:
            ref = p["ref"] or f"name:{p['name']}"
            if not p["ref"] and not p["name"]:
                continue
            orgs.setdefault(ref, {"ref": ref, "name": p["name"], "type": p["type"]})
            rel["participates"].append({
                "org_ref": ref, "iati_identifier": iid, "role": p["role"],
            })

        for c in rec["countries"]:
            if c["code"]:
                rel["targets"].append({
                    "iati_identifier": iid, "country_code": c["code"],
                    "percentage": c["percentage"],
                    "is_hotspot": str(c["code"] in HOTSPOTS).lower(),
                })

        for r in rec["regions"]:
            if not r["code"]:
                continue
            key = f'{r["vocabulary"]}:{r["code"]}'
            regions.setdefault(key, {"region_key": key, "code": r["code"],
                                     "vocabulary": r["vocabulary"], "name": r["name"]})
            rel["targets_region"].append({
                "iati_identifier": iid, "region_key": key,
                "percentage": r["percentage"],
            })

        for j, loc in enumerate(rec["locations"]):
            loc_id = f"{iid}#loc{j}"
            locations.append({"location_id": loc_id, **loc})
            rel["located_at"].append({"iati_identifier": iid, "location_id": loc_id})

        for s in rec["sectors"]:
            if not s["code"]:
                continue
            key = f'{s["vocabulary"]}:{s["code"]}'
            sectors.setdefault(key, {
                "sector_key": key, "code": s["code"], "vocabulary": s["vocabulary"],
                "name": s["name"],
                "is_hunger": str(is_hunger_sector(s["code"], s["vocabulary"])).lower(),
            })
            rel["classified"].append({
                "iati_identifier": iid, "sector_key": key,
                "percentage": s["percentage"],
            })

        for t in rec["transactions"]:
            transactions.append({k: v for k, v in t.items()
                                 if k not in ("provider_name", "receiver_name")}
                                | {"iati_identifier": iid})
            for side, refk, namek in (("PROVIDED_BY", "provider_ref", "provider_name"),
                                      ("RECEIVED_BY", "receiver_ref", "receiver_name")):
                ref = t[refk] or (f"name:{t[namek]}" if t[namek] else "")
                if ref:
                    orgs.setdefault(ref, {"ref": ref, "name": t[namek], "type": ""})
                    rel["tx_edges"].append({"tx_id": t["tx_id"], "org_ref": ref,
                                            "edge": side})

        for b in rec["budgets"]:
            budgets.append(b | {"iati_identifier": iid})

        for e in rec["emergencies"]:
            if not e["code"]:
                continue
            key = f'{e["vocabulary"]}:{e["code"]}'
            emergencies.setdefault(key, {"emergency_key": key, "code": e["code"],
                                         "vocabulary": e["vocabulary"],
                                         "type": e["type"], "name": e["name"]})
            rel["responds_to"].append({"iati_identifier": iid, "emergency_key": key})

        for tg in rec["tags"]:
            if not tg["code"] or tg["vocabulary"] not in SDG_VOCABS:
                continue
            key = f'{tg["vocabulary"]}:{tg["code"]}'
            level = "goal" if tg["vocabulary"] == "2" else "target"
            tags.setdefault(key, {"sdg_key": key, "code": tg["code"],
                                  "level": level, "name": tg["name"]})
            rel["contributes_to"].append({"iati_identifier": iid, "sdg_key": key})

        for m in rec["markers"]:
            if not m["code"] or m["vocabulary"] not in ("1", ""):
                continue
            markers.setdefault(m["code"], {"code": m["code"], "name": m["name"]})
            rel["marked_with"].append({
                "iati_identifier": iid, "marker_code": m["code"],
                "significance": m["significance"],
            })

        for r in rec["related"]:
            if r["ref"]:
                rel["related"].append({
                    "iati_identifier": iid, "related_ref": r["ref"],
                    "type": r["type"],
                })

    pubs = [publisher_filter] if publisher_filter else list(PUBLISHERS)
    for pub in pubs:
        pdir = RAW_DIR / pub
        if not pdir.exists():
            print(f"[warn] no raw data for {pub}; run 01_download.py first")
            continue
        for xml_path in sorted(pdir.glob("*.xml")):
            # Stream with iterparse: WFP regional files can be hundreds of
            # MB, so never hold the whole tree in memory.
            try:
                for _, act in ET.iterparse(xml_path, events=("end",)):
                    if act.tag != "iati-activity":
                        continue
                    stats["total_seen"] += 1
                    rec = parse_activity(act, pub)
                    act.clear()
                    if rec is not None:
                        process(rec, pub)
            except ET.ParseError as e:
                print(f"[warn] bad XML {xml_path.name}: {e}")
                continue

    # ------------------------------------------------------------- write --
    def dump(name, rows, fields):
        with open(GRAPH_DIR / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"  {name:<28} {len(rows):>7} rows")

    print("\nWriting graph CSVs:")
    dump("nodes_activities.csv", activities,
         ["iati_identifier", "title", "description", "status", "humanitarian",
          "start_planned", "start_actual", "end_planned", "end_actual",
          "default_currency", "publisher", "hierarchy", "last_updated",
          "aid_type", "finance_type", "flow_type", "tied_status",
          "collaboration_type", "scope", "capital_spend",
          "hotspot_countries", "match_basis"])
    dump("nodes_organisations.csv", list(orgs.values()), ["ref", "name", "type"])
    dump("nodes_countries.csv",
         [{"code": k, "name": v["name"], "hotspot_tier": v["tier"]}
          for k, v in HOTSPOTS.items()],
         ["code", "name", "hotspot_tier"])
    dump("nodes_regions.csv", list(regions.values()),
         ["region_key", "code", "vocabulary", "name"])
    dump("nodes_locations.csv", locations,
         ["location_id", "name", "ref", "lat", "lon", "adm_code", "adm_vocab", "feature"])
    dump("nodes_sectors.csv", list(sectors.values()),
         ["sector_key", "code", "vocabulary", "name", "is_hunger"])
    dump("nodes_transactions.csv", transactions,
         ["tx_id", "iati_identifier", "type", "date", "value", "currency",
          "value_date", "recipient_country", "sector_code", "sector_vocab",
          "aid_type", "humanitarian"])
    dump("nodes_budgets.csv", budgets,
         ["budget_id", "iati_identifier", "type", "status",
          "period_start", "period_end", "value", "currency"])
    dump("nodes_emergencies.csv", list(emergencies.values()),
         ["emergency_key", "code", "vocabulary", "type", "name"])
    dump("nodes_sdgs.csv", list(tags.values()), ["sdg_key", "code", "level", "name"])
    dump("nodes_policy_markers.csv", list(markers.values()), ["code", "name"])
    dump("rel_reports.csv", rel["reports"], ["org_ref", "iati_identifier"])
    dump("rel_participates.csv", rel["participates"],
         ["org_ref", "iati_identifier", "role"])
    dump("rel_targets_country.csv", rel["targets"],
         ["iati_identifier", "country_code", "percentage", "is_hotspot"])
    dump("rel_targets_region.csv", rel["targets_region"],
         ["iati_identifier", "region_key", "percentage"])
    dump("rel_located_at.csv", rel["located_at"], ["iati_identifier", "location_id"])
    dump("rel_classified_as.csv", rel["classified"],
         ["iati_identifier", "sector_key", "percentage"])
    dump("rel_transaction_edges.csv", rel["tx_edges"], ["tx_id", "org_ref", "edge"])
    dump("rel_responds_to.csv", rel["responds_to"],
         ["iati_identifier", "emergency_key"])
    dump("rel_contributes_to.csv", rel["contributes_to"],
         ["iati_identifier", "sdg_key"])
    dump("rel_marked_with.csv", rel["marked_with"],
         ["iati_identifier", "marker_code", "significance"])
    dump("rel_related_activity.csv", rel["related"],
         ["iati_identifier", "related_ref", "type"])

    report = {
        "filters": {"theme_applied": apply_theme,
                    "include_general_emergency": INCLUDE_GENERAL_EMERGENCY},
        "counts": dict(stats),
        "per_publisher_funnel": {p: dict(c) for p, c in funnel.items()},
        "top_dropped_sector_codes": {p: dict(c.most_common(15))
                                     for p, c in dropped_sectors.items()},
        "activities_per_publisher_per_hotspot": {p: dict(c) for p, c in per_pub_country.items()},
        "activities_per_publisher_per_start_year": {p: dict(sorted(c.items())) for p, c in years.items()},
        "enrichment_coverage": {
            "activities_with_budgets": len({b["iati_identifier"] for b in budgets}),
            "activities_with_emergency_links": len({r["iati_identifier"] for r in rel["responds_to"]}),
            "activities_with_sdg_tags": len({r["iati_identifier"] for r in rel["contributes_to"]}),
            "activities_with_policy_markers": len({r["iati_identifier"] for r in rel["marked_with"]}),
            "distinct_emergencies": len(emergencies),
        },
    }
    with open(GRAPH_DIR / "coverage_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nCoverage report -> {GRAPH_DIR/'coverage_report.json'}")
    print(json.dumps({k: v for k, v in report.items() if k != "filters"}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--publisher")
    ap.add_argument("--no-theme", action="store_true",
                    help="skip hunger filter; geography-only coverage scan")
    args = ap.parse_args()
    run(args.publisher, apply_theme=not args.no_theme)
