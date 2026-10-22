"""
resolve_entity.py -- map free text to canonical graph IDs.

    from retrieval.resolve_entity import resolve_entity
    resolve_entity("UK government", "organisation")
    resolve_entity("Somalia", "country")

Matching order: exact (ref or name) -> curated alias -> acronym -> fuzzy
(rapidfuzz). Short inputs (< 4 chars) never reach the fuzzy stage. The
result always says HOW it matched and never returns a single answer when
the top candidates are close.

Return shape (same status vocabulary as the Phase 4 tools):
  {
    "status": "ok" | "ambiguous" | "no_results" | "error",
    "kind": "organisation" | "country",
    "query": "<input>",
    "match": {            # present when status == "ok"
      "id": "XM-DAC-12",            # the ref that matched
      "name": "United Kingdom",
      "ids": ["XM-DAC-12", "XM-DAC-12-1", ...],   # all refs a tool should filter on
      "relation": "same" | "agency_of" | None,    # why ids has >1 entry
      "parent": "<ref>" | None,     # set when id is itself an agency of a parent
      "publisher": "oxfamgb" | None,              # slug if this org is one of the 3 publishers
      "type": "10", "type_name": "Government",
      "confidence": 0.0-1.0, "method": "exact|alias|acronym|fuzzy"
    },
    "candidates": [ {id, name, type_name, degree, confidence}, ... ],
    "note": "..."
  }
Country matches carry id/ids = ISO2 code, name, hotspot_tier.

CLI:
    python retrieval/resolve_entity.py "World Food Program"
    python retrieval/resolve_entity.py Somalia --kind country
    python retrieval/resolve_entity.py --demo
    python retrieval/resolve_entity.py --report-duplicates   # -> retrieval/org_duplicates.csv
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
import entities as E  # noqa: E402

HERE = Path(__file__).resolve().parent
FUZZY_OK = 90          # top score at or above this, clearly ahead of #2 -> ok
FUZZY_MIN = 60         # below this nothing is even a candidate
FUZZY_GAP = 5          # #1 must beat #2 by this much, unless they are in one group
MIN_FUZZY_LEN = 4


# -------------------------------------------------------------- normalise --
def normalise(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(the|of)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def acronyms_of(name):
    """'United Nations Children's Fund (UNICEF)' -> {'unicef'};
    'UN-Int Organization for Migration (IOM)' -> {'iom'}; plus any all-caps
    token of 3+ letters and the initials of the name."""
    out = set()
    for m in re.findall(r"\(([A-Za-z]{2,10})\)", name or ""):
        out.add(m.lower())
    for tok in re.findall(r"\b[A-Z]{3,}\b", name or ""):
        if tok not in ("THE", "AND", "FOR"):
            out.add(tok.lower())
    words = [w for w in re.findall(r"[A-Za-z]+", re.sub(r"\(.*?\)", "", name or ""))
             if w.lower() not in ("the", "of", "for", "and", "de", "la")]
    if 2 <= len(words) <= 6:
        out.add("".join(w[0] for w in words).lower())
    return out


# ---------------------------------------------------------------- catalog --
class Catalog:
    """Organisation + country records, loaded once from Neo4j or injected
    (list of dicts with ref/name/type/publisher/degree) for tests."""

    def __init__(self, orgs=None, countries=None):
        if orgs is None or countries is None:
            import db
            orgs = orgs if orgs is not None else db.read_query(
                "MATCH (o:Organisation) OPTIONAL MATCH (o)-[r]-() "
                "RETURN o.ref AS ref, o.name AS name, o.type AS type, o.publisher AS publisher, "
                "count(r) AS degree LIMIT 100000")
            countries = countries if countries is not None else db.read_query(
                "MATCH (c:Country) RETURN c.code AS code, c.name AS name, c.hotspot_tier AS hotspot_tier LIMIT 1000")
        self.orgs = {o["ref"]: {**o, "name": o.get("name") or ""} for o in orgs}
        self.countries = {c["code"]: c for c in countries}

        # lookup tables (normalised string -> ref). Names and refs are both
        # candidates because WFP put bare names in the ref field.
        self.by_norm = {}
        self.by_acronym = {}
        for ref, o in self.orgs.items():
            for key in {normalise(o["name"]), normalise(ref[5:] if ref.startswith("name:") else ref)}:
                if key:
                    self.by_norm.setdefault(key, []).append(ref)
            for a in acronyms_of(o["name"]):
                self.by_acronym.setdefault(a, []).append(ref)
        self.choices = {ref: normalise(o["name"]) or normalise(ref) for ref, o in self.orgs.items()}

        self.same_group = {}        # ref -> frozenset of refs that are the same org
        for canon, variants in E.SAME_AS.items():
            grp = frozenset([canon, *variants])
            for r in grp:
                self.same_group[r] = grp
        self.parent_of = {}         # agency ref -> parent ref
        for parent, agencies in E.AGENCY_OF.items():
            for a in agencies:
                self.parent_of[a] = parent
        self.canonical = {v: canon for canon, vs in E.SAME_AS.items() for v in vs if canon in self.orgs}
        # curated tables with normalised keys so lookups match normalise(text)
        self.aliases = {normalise(k): v for k, v in E.ALIASES.items()}
        self.ambiguous = {normalise(k): v for k, v in E.AMBIGUOUS.items()}
        self.country_aliases = {normalise(k): v for k, v in E.COUNTRY_ALIASES.items()}
        self.hotspot_names = {normalise(c["name"]) for c in self.countries.values()} | {"west bank and gaza strip"}

    # -- expansion ----------------------------------------------------------
    def ids_for(self, ref):
        """All refs a tool should filter on for `ref`: its SAME_AS group, and
        if it is a parent, every agency (plus their SAME_AS groups)."""
        ref = self.canonical.get(ref, ref)
        ids = set(self.same_group.get(ref, {ref}))
        relation = "same" if len(ids) > 1 else None
        for a in E.AGENCY_OF.get(ref, []):
            ids |= set(self.same_group.get(a, {a}))
            relation = "agency_of"
        ids = [r for r in ids if r in self.orgs]  # only refs that exist in this graph
        order = sorted(ids, key=lambda r: (r != ref, -self.orgs[r]["degree"]))
        return order, relation

    def card(self, ref, confidence=None):
        o = self.orgs[ref]
        d = {"id": ref, "name": o["name"] or ref, "type": o.get("type"),
             "type_name": E.ORG_TYPES.get(o.get("type") or ""), "degree": o["degree"]}
        if confidence is not None:
            d["confidence"] = round(confidence, 3)
        return d

    def match(self, ref, confidence, method):
        ref = self.canonical.get(ref, ref)      # report the canonical ref of a SAME_AS group
        ids, relation = self.ids_for(ref)
        m = {**self.card(ref, confidence), "ids": ids, "relation": relation,
             "parent": self.parent_of.get(ref), "publisher": self.orgs[ref].get("publisher"),
             "method": method}
        return m


_CATALOG = None


def get_catalog():
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = Catalog()
    return _CATALOG


# ---------------------------------------------------------------- resolve --
def _note_for(cat, m):
    notes = []
    if m["id"] in E.PLACEHOLDERS:
        notes.append(f"warning: {E.PLACEHOLDERS[m['id']]}")
    if m["relation"] == "same":
        notes.append(f"{len(m['ids'])} refs identify this organisation; filter on all of them")
    elif m["relation"] == "agency_of":
        notes.append(f"ids include {len(m['ids']) - 1} agencies/funds of this organisation; use ids=[id] to exclude them")
    if m["parent"]:
        notes.append(f"this is an agency of {cat.orgs[m['parent']]['name']} ({m['parent']}); resolve that for the whole government")
    if normalise(m["name"]) in cat.hotspot_names and m["id"].startswith("XM-DAC-"):
        notes.append("host government of a hotspot country, published under its DAC recipient code (WFP records government contributions this way)")
    return "; ".join(notes)


def resolve_organisation(text, cat):
    q = normalise(text)
    if not q:
        return {"status": "error", "note": "empty query"}

    # 1. exact on ref or name
    raw = (text or "").strip()
    if raw in cat.orgs or raw.upper() in cat.orgs:
        ref = raw if raw in cat.orgs else raw.upper()
        return {"status": "ok", "match": cat.match(ref, 1.0, "exact")}
    hits = cat.by_norm.get(q, [])
    if len(hits) == 1:
        return {"status": "ok", "match": cat.match(hits[0], 1.0, "exact")}
    if len(hits) > 1 and len({frozenset(cat.same_group.get(h, {h})) for h in hits}) == 1:
        best = max(hits, key=lambda r: cat.orgs[r]["degree"])
        return {"status": "ok", "match": cat.match(best, 1.0, "exact")}
    if len(hits) > 1:
        return {"status": "ambiguous", "candidates": [cat.card(h, 1.0) for h in hits],
                "note": "several organisations carry exactly this name"}

    # 2. curated aliases
    if q in cat.ambiguous:
        a = cat.ambiguous[q]
        cands = [cat.card(r, 0.9) for r in a["candidates"] if r in cat.orgs]
        extra = [r for _, _, r in process.extract(q, cat.choices, scorer=fuzz.partial_ratio, limit=25)
                 if r not in a["candidates"] and q in cat.choices[r] and r not in E.PLACEHOLDERS]
        cands += [cat.card(r, 0.6) for r in extra[:10]]
        return {"status": "ambiguous", "candidates": cands, "note": a["note"]}
    if q in cat.aliases:
        ref = cat.aliases[q]
        if ref is None:
            return {"status": "no_results", "candidates": [], "note": f"'{text}' is a known organisation but it does not appear in this graph"}
        if ref in cat.orgs:
            return {"status": "ok", "match": cat.match(ref, 0.98, "alias")}

    # 3. acronyms derived from names
    hits = cat.by_acronym.get(q.replace(" ", ""), [])
    groups = {frozenset(cat.same_group.get(h, {h})) for h in hits}
    if len(groups) == 1:
        best = max(hits, key=lambda r: cat.orgs[r]["degree"])
        return {"status": "ok", "match": cat.match(best, 0.95, "acronym")}
    if len(groups) > 1:
        return {"status": "ambiguous", "candidates": [cat.card(h, 0.8) for h in hits],
                "note": "acronym matches several organisations"}

    # 4. fuzzy
    if len(q) < MIN_FUZZY_LEN:
        return {"status": "no_results", "candidates": [],
                "note": f"'{text}' is too short for fuzzy matching and is not a known alias"}
    scored = process.extract(q, cat.choices, scorer=fuzz.token_set_ratio, limit=8)
    scored = [(ref, score) for _, score, ref in scored if score >= FUZZY_MIN]
    scored.sort(key=lambda t: (-t[1], -cat.orgs[t[0]]["degree"]))
    if not scored:
        return {"status": "no_results", "candidates": [], "note": "no organisation name resembles the query"}
    # rank by token_set (robust to extra words) but REPORT a blended score:
    # "Red Cross" is a subset of "British Red Cross" (set score 100) and
    # should not claim certainty. Fuzzy confidence is capped at 0.95.
    def conf(ref, set_score):
        sort_score = fuzz.token_sort_ratio(q, cat.choices[ref])
        return min(0.95, (set_score + sort_score) / 200)
    cands = [cat.card(r, conf(r, s)) for r, s in scored]
    top_ref, top = scored[0]
    second = scored[1][1] if len(scored) > 1 else 0
    same_grp = len(scored) > 1 and scored[1][0] in cat.same_group.get(top_ref, {top_ref})
    top_conf = conf(top_ref, top)
    if top_conf * 100 >= FUZZY_OK and (top - second >= FUZZY_GAP or same_grp):
        return {"status": "ok", "match": cat.match(top_ref, top_conf, "fuzzy"), "candidates": cands[1:]}
    return {"status": "ambiguous", "candidates": cands,
            "note": "fuzzy match is not decisive; pick a candidate or rephrase"}


def resolve_country(text, cat):
    q = normalise(text)
    if not q:
        return {"status": "error", "note": "empty query"}
    code = None
    up = (text or "").strip().upper()
    if up in cat.countries:
        code, method = up, "exact"
    elif up in E.ISO3_TO_ISO2:
        code, method = E.ISO3_TO_ISO2[up], "alias"
    elif q in cat.country_aliases:
        code, method = cat.country_aliases[q], "alias"
    else:
        by_name = {normalise(c["name"]): k for k, c in cat.countries.items()}
        if q in by_name:
            code, method = by_name[q], "exact"
        elif len(q) >= MIN_FUZZY_LEN:
            scored = process.extract(q, by_name, scorer=fuzz.token_set_ratio, limit=3)
            scored = [(by_name[name], s) for name, s, _ in scored if s >= FUZZY_MIN]
            if scored and scored[0][1] >= FUZZY_OK and (len(scored) == 1 or scored[0][1] - scored[1][1] >= FUZZY_GAP):
                code, method = scored[0][0], "fuzzy"
            elif scored:
                return {"status": "ambiguous", "note": "no decisive match among hotspot countries",
                        "candidates": [{"id": c, "name": cat.countries[c]["name"], "confidence": s / 100} for c, s in scored]}
    if code is None or code not in cat.countries:
        return {"status": "no_results", "candidates": [],
                "note": f"'{text}' is not one of the 13 hotspot countries in this graph "
                        f"({', '.join(sorted(cat.countries))})"}
    c = cat.countries[code]
    conf = {"exact": 1.0, "alias": 0.98}.get(method, 0.9)
    return {"status": "ok", "match": {"id": code, "name": c["name"], "ids": [code],
                                       "hotspot_tier": c.get("hotspot_tier"), "confidence": conf, "method": method}}


def resolve_entity(text, kind, catalog=None):
    """Resolve free text to graph IDs. kind: "organisation" or "country"."""
    cat = catalog or get_catalog()
    kind = (kind or "").lower().rstrip("s")
    kind = {"org": "organisation", "organization": "organisation"}.get(kind, kind)
    if kind not in ("organisation", "country"):
        return {"status": "error", "kind": kind, "query": text, "note": "kind must be 'organisation' or 'country'"}
    out = resolve_organisation(text, cat) if kind == "organisation" else resolve_country(text, cat)
    out = {"status": out["status"], "kind": kind, "query": text, "match": out.get("match"),
           "candidates": out.get("candidates", []), "note": out.get("note", "")}
    if kind == "organisation" and out["match"]:
        out["note"] = "; ".join(n for n in (out["note"], _note_for(cat, out["match"])) if n)
    return out


# ------------------------------------------------------- duplicate report --
def find_duplicates(cat):
    """Pairs of refs that look like the same organisation (or a parent/agency
    pair). Detection rules run first; the curated tables then confirm or add
    pairs, so the `curated` column shows what the rules alone would catch.
    Returns rows: group, canonical_ref, ref, name, degree, relation, rule,
    score, curated, note."""
    rows, seen = {}, {}

    def add(canon, ref, relation, rule, score, note=""):
        key = frozenset((canon, ref))
        if canon == ref or key in seen:
            return
        seen[key] = rows[key] = {"group": canon, "canonical_ref": canon, "ref": ref,
                                 "name": cat.orgs[ref]["name"], "degree": cat.orgs[ref]["degree"],
                                 "relation": relation, "rule": rule, "score": score, "curated": "no", "note": note}

    refs = list(cat.orgs)
    named = [r for r in refs if cat.orgs[r]["name"]]          # empty names cannot be compared
    real = {r: cat.choices[r] for r in named if not r.startswith("name:")}
    # R1: name:-pseudo-ref whose name resembles a real ref's name. token_sort
    # (not token_set) so "Oxfam Germany" does not collapse into "Germany".
    for r in named:
        if r.startswith("name:") and real:
            best = process.extractOne(cat.choices[r], real, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 90:
                add(best[2], r, "same", "pseudo_ref_name_match", int(best[1]),
                    "name-only ref resembles a real ref's name")
    # R2: a ref string equal to another org's name (FRO / FAROE ISLANDS pattern)
    name_to_ref = {}
    for r in refs:
        name_to_ref.setdefault(cat.choices[r], []).append(r)
    for r in refs:
        for other in name_to_ref.get(normalise(r), []):
            if other != r:
                hi, lo = sorted((r, other), key=lambda x: -cat.orgs[x]["degree"])
                add(hi, lo, "same", "ref_equals_other_name", 100, "one org's ref is the other's name")
    # R3: shared acronym across refs
    for acr, hits in cat.by_acronym.items():
        if len(acr) >= 3 and len(set(hits)) > 1:
            hits = sorted(set(hits), key=lambda x: -cat.orgs[x]["degree"])
            for h in hits[1:]:
                add(hits[0], h, "same", "shared_acronym", 90, f"both carry acronym {acr.upper()}; review")
    # R4: DAC donor vs agency code
    for r in refs:
        m = re.fullmatch(r"(XM-DAC-\d+)-[\w.]+", r)
        if m and m.group(1) in cat.orgs:
            add(m.group(1), r, "agency_of", "dac_agency_code", 100, "XM-DAC-<donor>-<agency> under same donor")
    # R5: two real refs with near-identical names
    real_refs = list(real)
    for i, r in enumerate(real_refs):
        for _, score, other in process.extract(real[r], {x: real[x] for x in real_refs[i + 1:]},
                                               scorer=fuzz.token_sort_ratio, limit=3):
            if score >= 93 and len(real[r]) >= 6:
                add(r, other, "same", "real_ref_name_match", int(score), "two real refs, near-identical names")

    # curated tables: confirm detected pairs or add missed ones
    for table, relation in ((E.SAME_AS, "same"), (E.AGENCY_OF, "agency_of")):
        for canon, variants in table.items():
            for v in variants:
                if canon not in cat.orgs or v not in cat.orgs:
                    continue
                key = frozenset((canon, v))
                if key in rows:
                    rows[key].update({"curated": "yes", "relation": relation, "group": canon, "canonical_ref": canon})
                else:
                    add(canon, v, relation, "curated_only", 100, "hand-checked; not caught by detection rules")
                    rows[key]["curated"] = "yes"
    out = list(rows.values())
    out.sort(key=lambda x: (x["curated"] != "yes", x["group"], -x["degree"]))
    return out


def write_duplicates(cat, path):
    rows = find_duplicates(cat)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return rows


# -------------------------------------------------------------------- cli --
DEMO = [("Oxfam", "organisation"), ("WFP", "organisation"), ("World Food Program", "organisation"),
        ("UK government", "organisation"), ("Somalia", "country"), ("SO", "country"),
        ("Oxfam America", "organisation"), ("FCDO", "organisation"), ("USAID", "organisation"),
        ("ECHO", "organisation"), ("DRC", "country"), ("Kenya", "country"), ("World Bank", "organisation"),
        ("Save the Children", "organisation"), ("Somalia", "organisation"), ("Multilateral", "organisation"),
        ("unicef", "organisation"), ("Oxfam Novib", "organisation"), ("German Foreign Office", "organisation"),
        ("US", "organisation"), ("MSF", "organisation"), ("Palestine", "country"), ("COD", "country")]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?")
    ap.add_argument("--kind", default="organisation")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--report-duplicates", action="store_true")
    args = ap.parse_args()
    cat = get_catalog()
    if args.report_duplicates:
        out = HERE / "org_duplicates.csv"
        rows = write_duplicates(cat, out)
        from collections import Counter
        print(f"{len(rows)} duplicate-looking pairs in {len({r['group'] for r in rows})} groups -> {out}")
        print(Counter((r["rule"], r["relation"]) for r in rows))
    elif args.demo:
        for text, kind in DEMO:
            r = resolve_entity(text, kind, cat)
            m = r["match"]
            head = f"{text!r:<24} {kind:<13} {r['status']:<11}"
            if m:
                head += f" -> {m['id']} ({m['name']}) conf={m['confidence']} via {m['method']} ids={m['ids']}"
            else:
                head += " candidates=" + ", ".join(f"{c['id']}" for c in r["candidates"][:5])
            print(head + (f"\n{'':<50} note: {r['note']}" if r["note"] else ""))
    elif args.text:
        print(json.dumps(resolve_entity(args.text, args.kind, cat), indent=2, ensure_ascii=False))
    else:
        ap.print_help()
