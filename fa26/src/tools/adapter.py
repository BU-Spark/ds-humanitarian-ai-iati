"""Adapter: Alex's retrieval tools (fa26/retrieval/tools.py) -> (key, value, evidence) rows for the router.

The router in notebook 06 knows one calling convention: ``run_tool(run_cypher, name, args)`` returning
``{"rows": [{"key", "value", "evidence"}, ...], ...}``. The retrieval tools are Python callables with
free-text arguments ("Somalia", "WFP") and their own column names. This module

* registers the five retrieval tools in the same catalogue format as src/tools/templates.py,
* maps each result row to one fact ``{key, value, evidence}`` in the benchmark's key style
  (``total`` / currency code / ``<ref> [<CUR>]`` / period / iati_identifier),
* maps the retrieval status vocabulary (ok, no_results, error+candidates) to the router's
  (rows, manifest-cited zero, ToolClarification / ToolError),
* exposes ``run_any`` and ``catalog_all`` so the router can mix both tool families.

Money tools take a ``measure`` argument: ``amount`` (positive transactions only, the client's headline
figure since 2026-10-23), ``adjustments`` (negative transactions) or ``net`` (amount + adjustments).
Exactly one measure becomes the fact value; its ``evidence_<measure>`` list becomes the evidence.

Evidence for ``activities`` and ``shared_partners`` is reconstructed from the pinned snapshot
(iati_identifier -> ``nodes_activities.csv:row:<n>``) because those rows carry identifiers, not row ids.
``shared_partners`` returns at most 20 activity ids per organisation (retrieval MAX_IDS_PER_ROW), so its
evidence can be incomplete; the result says so in ``coverage``.

No Neo4j connection is made here. The retrieval callables are imported lazily on first use, or injected
through ``impl=`` for offline tests.
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

from .templates import TOOLS as TEMPLATE_TOOLS, run_tool as run_template, tool_catalog as template_catalog

FA26 = Path(__file__).resolve().parents[2]
RETRIEVAL_DIR = FA26 / "retrieval"
SNAPSHOT_DIR = FA26 / "benchmark" / "snapshot"

MEASURES = ("amount", "adjustments", "net")
TX_TYPES = ("Incoming Funds", "Outgoing Commitment", "Disbursement", "Expenditure")  # exact names in Alex's TRANSACTION_TYPE_NAMES
MATCH_TYPES = ("sector", "sdg", "keyword", "keyword_over_sector", "keyword_weak")


class ToolError(ValueError):
    """The retrieval tool rejected the call or the query failed."""


class ToolClarification(ToolError):
    """An entity was ambiguous; ``candidates`` lists what the user could mean."""

    def __init__(self, message, candidates):
        super().__init__(message)
        self.candidates = candidates or []


# --------------------------------------------------------------------------------------- catalogue --
def _p(type_, required=False, values=None, default=None, doc=""):
    s = {"type": type_, "required": required}
    if values:
        s["values"] = list(values)
    if default is not None:
        s["default"] = default
    if doc:
        s["doc"] = doc
    return s


RETRIEVAL_TOOLS = {
    "rt_activities": {
        "fn": "activities",
        "description": "List hunger-related activities (one fact per activity: key=iati_identifier, "
                       "value=publisher). Free-text country/publisher; year range = active in range; "
                       "match_type = why the hunger filter kept it.",
        "params": {"country": _p("text"), "publisher": _p("text"), "year_from": _p("int"), "year_to": _p("int"),
                   "match_type": _p("enum", values=MATCH_TYPES), "limit": _p("int", default=50)},
    },
    "rt_shared_partners": {
        "fn": "shared_partners",
        "description": "Organisations that work with EVERY listed publisher (participation, funder or "
                       "recipient), optionally within a country. key=organisation ref, value=n_activities.",
        "params": {"publishers": _p("list", required=True, doc="e.g. ['Oxfam GB','WFP']"),
                   "country": _p("text"), "limit": _p("int", default=50)},
    },
    "rt_top_funders": {
        "fn": "top_funders",
        "description": "Top provider organisations of money INTO a hotspot country, per currency "
                       "(never converted). key='<funder ref> [<CUR>]', value=measure. Excludes the "
                       "reporting publisher itself unless exclude_self=false.",
        "params": {"country": _p("text", required=True), "measure": _p("enum", values=MEASURES, default="amount"),
                   "transaction_types": _p("list", default=["Incoming Funds"]), "year_from": _p("int"),
                   "year_to": _p("int"), "limit": _p("int", default=10), "publisher": _p("text"),
                   "exclude_self": _p("bool", default=True)},
    },
    "rt_funding_over_time": {
        "fn": "funding_over_time",
        "description": "Money per period (year|quarter|month) for ONE transaction type, by publisher and "
                       "currency. key=period (plus ' [<CUR>]' when several currencies), value=measure.",
        "params": {"publisher": _p("text"), "country": _p("text"), "measure": _p("enum", values=MEASURES, default="amount"),
                   "transaction_type": _p("enum", values=TX_TYPES, default="Incoming Funds"),
                   "by": _p("enum", values=("year", "quarter", "month"), default="year"),
                   "year_from": _p("int"), "year_to": _p("int"), "limit": _p("int", default=200)},
    },
    "rt_transaction_totals": {
        "fn": "transaction_totals",
        "description": "Total of ONE transaction type, one fact per currency (key=currency code, or "
                       "'total' when a single currency; key=publisher when by_publisher). value=measure. "
                       "Mixing types is refused (WFP mirrors commitments as expenditure).",
        "params": {"transaction_type": _p("enum", values=TX_TYPES, default="Incoming Funds"),
                   "measure": _p("enum", values=MEASURES, default="amount"), "publisher": _p("text"),
                   "currency": _p("text"), "country": _p("text"), "year_from": _p("int"), "year_to": _p("int"),
                   "by_publisher": _p("bool", default=False)},
    },
}
MONEY_TOOLS = {"rt_top_funders", "rt_funding_over_time", "rt_transaction_totals"}


def retrieval_catalog() -> str:
    lines = []
    for name, t in RETRIEVAL_TOOLS.items():
        ps = ", ".join(f"{p}{'' if s['required'] else '?'}: {s['type']}"
                       f"{'=' + '|'.join(s['values']) if s['type'] == 'enum' else ''}"
                       for p, s in t["params"].items())
        lines.append(f"- {name}({ps}): {t['description']}")
    return "\n".join(lines)


def catalog_all() -> str:
    """Template catalogue first (deterministic Cypher), then the retrieval tools."""
    return template_catalog() + "\n" + retrieval_catalog()


# ----------------------------------------------------------------------------------- arg handling --
def validate_retrieval_args(name: str, args: dict) -> tuple[dict, str]:
    """Return (kwargs for the retrieval callable, measure). Raises ToolError."""
    if name not in RETRIEVAL_TOOLS:
        raise ToolError(f"unknown retrieval tool {name!r}")
    spec = RETRIEVAL_TOOLS[name]["params"]
    args = dict(args or {})
    unknown = set(args) - set(spec)
    if unknown:
        raise ToolError(f"unknown parameters for {name}: {sorted(unknown)}")
    out, measure = {}, "amount"
    for p, s in spec.items():
        v = args.get(p, s.get("default"))
        if v in (None, ""):
            if s["required"]:
                raise ToolError(f"{name}: {p} is required")
            if p != "measure":
                out[p] = None if s["type"] != "list" else s.get("default")
            continue
        if s["type"] == "enum" and v not in s["values"]:
            raise ToolError(f"{name}: {p}={v!r} not in {s['values']}")
        if s["type"] == "int":
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ToolError(f"{name}: {p} must be an integer, got {v!r}")
        if s["type"] == "bool" and isinstance(v, str):
            v = v.strip().lower() in ("true", "1", "yes")
        if s["type"] == "list" and isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        if p == "measure":
            measure = v
        else:
            out[p] = v
    return out, measure


# -------------------------------------------------------------------------------- evidence lookup --
_ACTIVITY_INDEX: dict[str, str] | None = None


def activity_index(snapshot_dir: Path = SNAPSHOT_DIR) -> dict[str, str]:
    """iati_identifier -> 'nodes_activities.csv:row:<n>' from the pinned snapshot (rows counted from 1)."""
    global _ACTIVITY_INDEX
    if _ACTIVITY_INDEX is None:
        csv.field_size_limit(10_000_000)
        with (snapshot_dir / "nodes_activities.csv").open(encoding="utf-8", newline="") as fh:
            _ACTIVITY_INDEX = {r["iati_identifier"]: f"nodes_activities.csv:row:{i}"
                               for i, r in enumerate(csv.DictReader(fh), start=1)}
    return _ACTIVITY_INDEX


# ------------------------------------------------------------------------------------ row mapping --
def _suffix(rows, col="currency"):
    """Append ' [CUR]' to keys only when the result spans several currencies."""
    return len({r.get(col) for r in rows}) > 1


def rows_to_facts(name: str, result: dict, measure: str, index: dict[str, str] | None = None) -> list[dict]:
    rows = result.get("rows") or []
    index = activity_index() if index is None else index
    out = []
    if name == "rt_activities":
        for r in rows:
            out.append({"key": r["iati_identifier"], "value": r.get("publisher"),
                        "evidence": [index[r["iati_identifier"]]] if r["iati_identifier"] in index else []})
    elif name == "rt_shared_partners":
        for r in rows:
            ev = sorted(index[a] for a in (r.get("activity_ids") or []) if a in index)
            out.append({"key": r["organisation_id"], "value": r.get("n_activities"), "evidence": ev})
    elif name == "rt_top_funders":
        for r in rows:
            out.append({"key": f"{r['funder_id']} [{r['currency']}]", "value": r[measure],
                        "evidence": list(r.get(f"evidence_{measure}") or [])})
    elif name == "rt_funding_over_time":
        multi = _suffix(rows)
        for r in rows:
            key = f"{r['period']} [{r['currency']}]" if multi else str(r["period"])
            if r.get("publisher") and len({x.get("publisher") for x in rows}) > 1:
                key = f"{r['publisher']}:{key}"
            out.append({"key": key, "value": r[measure], "evidence": list(r.get(f"evidence_{measure}") or [])})
    elif name == "rt_transaction_totals":
        multi = _suffix(rows)
        for r in rows:
            if r.get("publisher"):
                key = f"{r['publisher']} [{r['currency']}]" if multi else r["publisher"]
            else:
                key = r["currency"] if multi else "total"
            out.append({"key": key, "value": r[measure], "evidence": list(r.get(f"evidence_{measure}") or [])})
    else:
        raise ToolError(f"no row mapping for {name}")
    for f in out:
        f["evidence"] = sorted({e for e in f["evidence"] if e})
    return out


def for_model(result: dict) -> dict:
    """Result without evidence lists (they can reach 1 MB); keep the full result for citations."""
    def slim(r):
        return {kk: vv for kk, vv in r.items() if kk != "evidence" and not kk.startswith("evidence_")}
    return {k: ([slim(r) for r in v] if k == "rows" else v) for k, v in result.items() if k != "evidence"}


# ---------------------------------------------------------------------------------------- running --
_IMPL: dict | None = None


def load_retrieval(retrieval_dir: Path = RETRIEVAL_DIR) -> dict:
    """Import fa26/retrieval/tools.py under a private module name (it is also called 'tools')."""
    global _IMPL
    if _IMPL is None:
        if str(retrieval_dir) not in sys.path:
            sys.path.insert(0, str(retrieval_dir))
        spec = importlib.util.spec_from_file_location("iati_retrieval_tools", retrieval_dir / "tools.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _IMPL = {t["fn"]: getattr(mod, t["fn"]) for t in RETRIEVAL_TOOLS.values()}
    return _IMPL


def run_retrieval(name: str, args: dict, impl: dict | None = None, index: dict | None = None) -> dict:
    """Call one retrieval tool and return the router's shape:
    {"tool", "params", "measure", "cypher", "rows": [{key, value, evidence}], "coverage", "raw"}."""
    kwargs, measure = validate_retrieval_args(name, args)
    fn = (impl or load_retrieval())[RETRIEVAL_TOOLS[name]["fn"]]
    res = fn(**kwargs)
    status = res.get("status")
    if status == "error":
        if res.get("candidates"):
            raise ToolClarification(res.get("coverage_note") or "ambiguous entity", res["candidates"])
        raise ToolError(res.get("coverage_note") or "retrieval tool error")
    rows = rows_to_facts(name, res, measure, index)
    if status == "no_results":
        if name in MONEY_TOOLS:   # benchmark convention: a zero cites the tables searched
            rows = [{"key": "total", "value": 0, "evidence": sorted(res.get("evidence") or [])}]
    coverage = res.get("coverage_note") or ""
    if name == "rt_shared_partners" and rows:
        coverage = (coverage + " | evidence limited to the first 20 activities per organisation").strip(" |")
    return {"tool": name, "params": res.get("params", kwargs), "measure": measure if name in MONEY_TOOLS else None,
            "cypher": res.get("cypher", ""), "rows": rows, "coverage": coverage, "raw": for_model(res)}


def run_any(run_cypher, name: str, args: dict, **kw) -> dict:
    """Dispatch: retrieval tools by their 'rt_' name, otherwise a Cypher template."""
    if name in RETRIEVAL_TOOLS:
        return run_retrieval(name, args, **kw)
    if name in TEMPLATE_TOOLS:
        return run_template(run_cypher, name, args)
    raise ToolError(f"unknown tool {name!r}")


__all__ = ["RETRIEVAL_TOOLS", "MONEY_TOOLS", "MEASURES", "ToolError", "ToolClarification",
           "retrieval_catalog", "catalog_all", "validate_retrieval_args", "rows_to_facts", "for_model",
           "run_retrieval", "run_any", "activity_index", "load_retrieval"]
