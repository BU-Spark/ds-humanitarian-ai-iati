"""Entity resolver: free text ("UK government", "WFP", "ECHO") -> every Organisation.ref that represents it.

Two layers:
1. Curated alias groups for the organisations that appear under several identifiers across publishers
   (Oxfam GB names funders as text 'name:...', WFP uses IATI refs).
2. Name search over the Organisation table (exact, token containment, then difflib similarity).

Returns candidates with a score so the caller can decide; it never merges silently.
"""
from __future__ import annotations
import csv
import difflib
import re
from pathlib import Path

# canonical group -> (aliases people type, regexes matched against lower-cased "ref | name")
ALIAS_GROUPS = {
    "WFP":        (["wfp", "world food programme", "un wfp"],                 [r"world food programme", r"\bwfp\b", r"xm-dac-41140"]),
    "OXFAM_GB":   (["oxfam gb", "oxfam great britain", "oxfam uk"],           [r"^gb-chc-202918 \|", r"\| oxfam gb$"]),
    "OXFAM_US":   (["oxfam america", "oxfam us", "oxfam usa"],                [r"us-ein-23-?7069110", r"oxfam america"]),
    "OXFAM_FAMILY": (["oxfam", "oxfam affiliates"],                           [r"oxfam"]),
    "UK_GOV":     (["uk", "uk government", "united kingdom", "fcdo", "dfid", "british government"],
                   [r"^xm-dac-12\b", r"united kingdom", r"\bfcdo\b", r"\bdfid\b", r"gb-gov-1"]),
    "US_GOV":     (["us", "usa", "us government", "united states", "usaid", "bha", "ofda"],
                   [r"^xm-dac-302\b", r"united states", r"\busaid\b", r"\bofda\b", r"us-gov-1"]),
    "GERMANY":    (["germany", "german government", "bmz", "giz", "federal foreign office"],
                   [r"^xm-dac-5\b", r"^de-1\b", r"\bgermany\b(?!.*oxfam)", r"\bgiz\b", r"\bbmz\b"]),
    "FRANCE":     (["france", "french government", "afd"],                     [r"^xm-dac-4\b", r"^fr-6\b", r"\bfrance\b(?!.*oxfam)"]),
    "EU_ECHO":    (["echo", "eu humanitarian", "european commission humanitarian", "dg echo"],
                   [r"\becho\b", r"ec_echo", r"humanitarian aid & civil"]),
    "EU":         (["eu", "european union", "european commission"],            [r"^name:eu\b", r"european commission", r"xi-iati-ec_", r"european development fund"]),
    "UNICEF":     (["unicef", "united nations children's fund"],               [r"unicef", r"children'?s fund", r"xm-dac-41122"]),
    "OCHA":       (["ocha", "cerf", "cbpf", "pooled funds"],                   [r"\bocha\b", r"\bcerf\b", r"\bcbpf\b", r"central emergency response fund"]),
    "WORLD_BANK": (["world bank", "wb", "ida", "ibrd"],                        [r"world bank", r"\bida\b", r"\bibrd\b", r"^44000 \|", r"xm-dac-44000"]),
    "SOMALIA_GOV": (["somalia", "somali government"],                           [r"^xm-dac-273\b", r"\| somalia$"]),
}

_NON_ORG_PLACEHOLDERS = {"MU", "ODM"}

COUNTRY_ALIASES = {  # hotspot countries in the snapshot
    "SD": ["sudan"], "SS": ["south sudan"], "YE": ["yemen"], "PS": ["palestine", "gaza", "west bank", "opt"],
    "NG": ["nigeria"], "SO": ["somalia"], "AF": ["afghanistan"], "CD": ["drc", "congo", "democratic republic of the congo", "dr congo"],
    "HT": ["haiti"], "LB": ["lebanon"], "MG": ["madagascar"], "MM": ["myanmar", "burma"], "ML": ["mali"],
}  # 'Multilateral' / 'Other Directed Multilateral' are pooled-fund placeholders, not organisations


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


class OrgResolver:
    def __init__(self, organisations: list[dict]):
        """organisations: rows with ref, name (and optionally type_label, source_id)."""
        self.orgs = [dict(o) for o in organisations]
        for o in self.orgs:
            o["_key"] = f"{o['ref']} | {o['name']}".lower()
            o["_norm"] = _norm(o["name"])
        self.alias_index = {}
        for group, (aliases, _) in ALIAS_GROUPS.items():
            for a in aliases:
                self.alias_index[_norm(a)] = group

    @classmethod
    def from_csv(cls, path: str | Path) -> "OrgResolver":
        with Path(path).open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for i, r in enumerate(rows, 1):
            r.setdefault("source_id", f"nodes_organisations.csv:row:{i}")
        return cls(rows)

    def resolve_country(self, q: str) -> dict | None:
        for code, aliases in COUNTRY_ALIASES.items():
            if q == code.lower() or any(q == a for a in aliases):
                return {"code": code, "name": aliases[-1] if code == "CD" else aliases[0].title()}
        return None

    def group_members(self, group: str) -> list[dict]:
        pats = [re.compile(p) for p in ALIAS_GROUPS[group][1]]
        return [o for o in self.orgs if any(p.search(o["_key"]) for p in pats)]

    def resolve(self, text: str, limit: int = 10) -> dict:
        """-> {query, kind, group, refs: [...], candidates: [{ref, name, score, via}], note}"""
        q = _norm(text)
        out = {"query": text, "kind": "organisation", "group": None, "refs": [], "candidates": [], "note": ""}
        country = self.resolve_country(q)
        if country:
            out.update(kind="country", refs=[country["code"]], candidates=[dict(country, score=1.0, via="country-alias")],
                       note="Country code for TARGETS / recipient filters, not an organisation.")
            return out
        exact = [o for o in self.orgs if (q == o["_norm"] or q == o["ref"].lower()) and o["ref"] not in _NON_ORG_PLACEHOLDERS]
        if not exact and any(q == o["_norm"] for o in self.orgs if o["ref"] in _NON_ORG_PLACEHOLDERS):
            out["note"] = "Pooled-fund placeholder ('Multilateral'), not an organisation; no identifier returned."
            return out
        if exact:  # an exact organisation name wins over a contained alias ("Oxfam Novib" is not "Oxfam")
            out["candidates"] = [{"ref": o["ref"], "name": o["name"], "score": 1.0, "via": "exact-name"} for o in exact]
            out["refs"] = [c["ref"] for c in out["candidates"]]
            out["note"] = "Exact organisation name."
            return out
        group = self.alias_index.get(q)
        if group is None:  # alias contained in the query ("the UK government")
            for alias, g in sorted(self.alias_index.items(), key=lambda kv: -len(kv[0])):
                if re.search(rf"\b{re.escape(alias)}\b", q):
                    group = g
                    break
        if group:
            members = self.group_members(group)
            out["group"] = group
            out["candidates"] = [{"ref": o["ref"], "name": o["name"], "score": 1.0, "via": f"alias:{group}"} for o in members]
            out["note"] = f"{len(members)} identifiers represent {group}; include all of them unless the question names one agency."
        else:
            scored = []
            for o in self.orgs:
                if o["ref"] in _NON_ORG_PLACEHOLDERS:
                    continue
                if q == o["_norm"] or q == o["ref"].lower():
                    score = 1.0
                elif q and q in o["_norm"]:
                    score = 0.9
                else:
                    score = difflib.SequenceMatcher(None, q, o["_norm"]).ratio()
                if score >= 0.6:
                    scored.append({"ref": o["ref"], "name": o["name"], "score": round(score, 3), "via": "name-search"})
            out["candidates"] = sorted(scored, key=lambda c: -c["score"])[:limit]
            out["note"] = "No curated alias; candidates are name matches, confirm before aggregating."
        out["refs"] = [c["ref"] for c in out["candidates"]]
        return out

    def duplicate_groups(self) -> list[dict]:
        """Organisations that appear under several identifiers (the merge list for the pipeline)."""
        groups = []
        for g in ALIAS_GROUPS:
            m = self.group_members(g)
            if len(m) > 1:
                groups.append({"group": g, "n": len(m), "refs": [o["ref"] for o in m]})
        return groups
