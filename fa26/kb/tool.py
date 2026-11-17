"""
kb/tool.py -- the knowledge base as a tool for the team's query router
(src/tools/adapter.py, src/ask.py on retrieval-schema-integration, PR #8).

The router's convention, matched here without importing it:
  * a catalogue entry {fn, description, params}, params as
    {type, required, values?, default?, doc?};
  * results {"tool", "params", "measure", "cypher", "rows", "coverage", "raw"},
    with rows [{key, value, evidence}] and evidence as source_id values
    ("nodes_activities.csv:row:N").

Here key = iati_identifier and value = title, one row per hit in rank order.
Search is by keyword, so it answers "which activities do X" questions about
project content; counts and money stay with the Cypher templates and
retrieval tools. Bad arguments raise ValueError (the router's ToolError is
a ValueError).

Wiring it into the router is three lines in src/tools/adapter.py; see
docs/knowledge-base.md.
"""
from config import KB_PATH, PUBLISHERS

from kb.search import CONFIDENCE_ORDER, search

NAME = "kb_search"
TOOL = {
    "fn": "kb_search",
    "description": "Keyword search over activity titles, descriptions, organisations and sectors, "
                   "for questions about what projects DO (e.g. school meals, cash for food, "
                   "malnutrition treatment, seeds and tools). One fact per activity in rank order: "
                   "key=iati_identifier, value=title. Not for counts or money. English keywords "
                   "miss many French WFP records.",
    "params": {
        "query": {"type": "text", "required": True,
                  "doc": "topic words; put a fixed phrase in double quotes"},
        "country": {"type": "text", "required": False, "doc": "ISO-2 hotspot code, e.g. SO"},
        "publisher": {"type": "enum", "required": False, "values": list(PUBLISHERS)},
        "min_confidence": {"type": "enum", "required": False, "values": list(CONFIDENCE_ORDER),
                           "doc": "leave out the hunger filter's less certain activities"},
        "limit": {"type": "int", "required": False, "default": 10},
    },
}
MAX_LIMIT = 50
# the router passes publisher names as users write them
_PUBLISHER_ALIASES = {**{k: k for k in PUBLISHERS},
                      **{v["label"].lower(): k for k, v in PUBLISHERS.items()},
                      "wfp": "wfp", "oxfam america": "oxfamus", "oxfam gb": "oxfamgb",
                      "oxfam great britain": "oxfamgb"}


def catalog_line():
    """One line in the router's catalogue format."""
    ps = ", ".join(f"{p}{'' if s['required'] else '?'}: {s['type']}"
                   f"{'=' + '|'.join(s['values']) if s['type'] == 'enum' else ''}"
                   for p, s in TOOL["params"].items())
    return f"- {NAME}({ps}): {TOOL['description']}"


def _args(args):
    spec = TOOL["params"]
    args = {k: v for k, v in (args or {}).items() if v not in (None, "")}
    unknown = set(args) - set(spec)
    if unknown:
        raise ValueError(f"unknown parameters for {NAME}: {sorted(unknown)}")
    if not str(args.get("query", "")).strip():
        raise ValueError(f"{NAME}: query is required")
    out = {"query": str(args["query"])}
    if "country" in args:
        out["country"] = str(args["country"])
    if "publisher" in args:
        p = _PUBLISHER_ALIASES.get(str(args["publisher"]).strip().lower())
        if not p:
            raise ValueError(f"{NAME}: publisher={args['publisher']!r} not in {list(PUBLISHERS)}")
        out["publisher"] = p
    if "min_confidence" in args:
        if args["min_confidence"] not in CONFIDENCE_ORDER:
            raise ValueError(f"{NAME}: min_confidence={args['min_confidence']!r} "
                             f"not in {list(CONFIDENCE_ORDER)}")
        out["min_confidence"] = args["min_confidence"]
    try:
        out["limit"] = max(1, min(int(args.get("limit", spec["limit"]["default"])), MAX_LIMIT))
    except (TypeError, ValueError):
        raise ValueError(f"{NAME}: limit must be an integer, got {args.get('limit')!r}")
    return out


def run(args, kb_path=KB_PATH):
    """Run one search and return the router's result shape."""
    params = _args(args)
    hits = search(params["query"], params.get("country"), params.get("publisher"),
                  params.get("min_confidence"), params["limit"], kb_path)
    rows = [{"key": h["iati_identifier"], "value": h["title"], "evidence": [h["source_id"]]}
            for h in hits]
    coverage = ("keyword search over activity text (BM25); ranked, not exhaustive: an empty "
                "or short result does not mean no such activities exist")
    raw = {"rows": [{k: h[k] for k in ("rank", "iati_identifier", "title", "publisher",
                                       "countries", "confidence", "score", "snippet")}
                    for h in hits]}
    return {"tool": NAME, "params": params, "measure": None, "cypher": "",
            "rows": rows, "coverage": coverage, "raw": raw}
