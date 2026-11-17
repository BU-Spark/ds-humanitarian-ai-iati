"""Question-answering engine for the IATI graph: the notebook 06 hybrid router as an importable module.

    from ask import Engine
    eng = Engine()                                  # .env: Neo4j + one model (default anthropic/claude-sonnet-4-6)
    out = eng.ask("How many WFP activities target Yemen?")
    out["status"], out["facts"], out["tool"], out["args"], out["latency_ms"]
    eng.evidence_rows(out)                           # the cited snapshot rows, for display

Pipeline: plan (LLM) -> template | retrieval tool (adapter) | free Cypher -> output-contract validation -> format.
A failed check sends the error back to the planner (up to 2 retries), so one question can take up to 3 LLM calls.
Clarify / abstain reasons use the benchmark's global reason vocabulary (6 v1 codes + 11 v2 codes).

Relation to notebook 06: same templates, adapter, contract checks and graph shape, but the system prompt is
built here (build_system) and differs from notebook 06 cell 13. The benchmark scores reported for notebook 06
therefore do not automatically describe this engine; it has not been scored on the benchmark itself.
Files read: fa26/benchmark/snapshot (rows shown by evidence_rows; activity ids via tools.adapter) and, via tools.contract,
fa26/benchmark/manifest.json (valid evidence ids), and fa26/.env (connection and API keys). No questions or answer keys are read.
"""
from __future__ import annotations

import csv
import json
import os
import re
import time
from decimal import Decimal
from pathlib import Path
from typing import Optional, TypedDict

from dotenv import load_dotenv

FA26 = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
for p in (FA26 / "src", FA26 / "benchmark"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from text2cypher_eval import guard_query                                               # noqa: E402
from tools.adapter import run_any, catalog_all, ToolClarification                      # noqa: E402
from tools.contract import (evidence_error, clean_evidence, normalise_facts, single_v2_reason,  # noqa: E402
                            V1_REASONS, V2_REASON_GUIDE)

REASON_CODES = V1_REASONS + ["funding_scope", "organisation_scope", "country_scope", "outcomes_unavailable",
                             "misuse_unavailable", "balances_unavailable", "identity_unavailable",
                             "forecast_unavailable", "coverage_unavailable", "exchange_rates_unavailable",
                             "personal_details_unavailable"]
DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"

SCHEMA_SHORT = '''Graph (loaded by fa26/retrieval/load_neo4j.py): (:Organisation {ref,name,publisher,source_id})-[:REPORTS]->(:Activity) and
(:Organisation)-[:PARTICIPATES_IN {role '1' funding|'2' accountable|'3' extending|'4' implementing, role_name, source_ids}]->(:Activity);
(:Activity {iati_identifier,publisher,title,status '2' implementation|'3' finalisation(completed),status_name,humanitarian '1'|'0'|null,default_currency,match_basis,
 start_actual,start_planned,end_actual,end_planned (Date or null), start_date,end_date (Date: actual else planned), last_updated (DateTime), hotspot_countries (list), source_id});
Activity-[:TARGETS {is_hotspot boolean, source_ids}]->(:Country {code,name}); Activity-[:CLASSIFIED_AS {source_ids}]->(:Sector {sector_key}); Activity-[:LOCATED_AT {source_ids}]->(:Location {location_id,name});
Activity-[:CONTRIBUTES_TO {source_ids}]->(:SDG {sdg_key}); Activity-[:HAS_TRANSACTION {source_ids}]->(:Transaction {tx_id,type '1'..'4',type_name,date (Date or null),value (float, signed),currency,source_id});
(:Organisation)-[:PROVIDES {source_ids}]->(:Transaction)-[:RECEIVED_BY {source_ids}]->(:Organisation); Activity-[:HAS_BUDGET {source_ids}]->(:Budget {type,status,value (float),currency,period_start,period_end,source_id}).
Publisher slugs: oxfamgb, oxfamus, wfp. Transaction type codes: 1 incoming funds, 2 outgoing commitment, 3 disbursement, 4 expenditure. Empty values are null (never ''); compare dates with date('YYYY-MM-DD'); t.date.year gives the year.
EVIDENCE in free_cypher: nodes have source_id, relationships have source_ids (a list); return collect(DISTINCT a.source_id) + reduce(acc=[], l IN collect(DISTINCT r.source_ids) | acc + coalesce(l, [])) AS evidence. Never cite iati_identifier, ref or location_id.
Negative transactions are their own category: 'amount' sums value > 0, 'adjustments' sums value < 0, 'net' sums both (use the measure parameter of money tools).'''


def build_system(reason_codes=REASON_CODES) -> str:
    return '''You route questions about one fixed snapshot of IATI humanitarian aid data to deterministic query tools.
Reply with ONE JSON object only:
{"status": "answer" | "abstain" | "clarify",
 "reasons": [],                       // abstain/clarify only, from ''' + json.dumps(reason_codes) + '''
 "explanation": "one sentence",
 "tool": "<tool name>" | "free_cypher" | null,
 "args": {...},                       // the tool's parameters, exactly as declared; omit optional ones you do not need
 "cypher": ""}                        // only when tool == "free_cypher": one read-only query returning key, value, evidence

Prefer a tool whenever one matches the question exactly; use free_cypher only when no tool fits.
For "how many activities ..." with any combination of conditions use count_activities (set only the filters the question states);
for counts of transactions, organisations or locations use count_transactions / count_organisations / count_locations; for earliest/latest dates use date_extreme.
Single-value answers must be keyed exactly: count (a count), total (a monetary amount), date (a date); per-currency amounts use currency codes as keys.
Abstain when the snapshot cannot support the answer (outcomes, forecasts, balances, identities, data outside the snapshot).
Clarify when the organisation or country is ambiguous or a money question does not fix the measure, currency and period. Country names must be converted to ISO-2 codes (Somalia = SO).

TOOLS:
''' + catalog_all() + "\n\n" + SCHEMA_SHORT + "\n\n" + V2_REASON_GUIDE


# ------------------------------------------------------------------------------------------ helpers --
def fmt_value(v, kind="auto"):
    if kind == "integer": return str(int(round(float(v))))
    if kind == "decimal": return str(Decimal(str(v)).quantize(Decimal("0.01")))
    if kind == "date": return str(v)[:10]
    if isinstance(v, float) and not v.is_integer(): return str(Decimal(str(v)).quantize(Decimal("0.01")))
    if isinstance(v, (int, float)): return str(int(v))
    return str(v)


def rows_to_facts(rows, kind="auto"):
    return {str(r["key"]): {"value": fmt_value(r["value"], kind),
                            "evidence": sorted({str(e) for e in (r.get("evidence") or []) if e})} for r in rows}


def parse_plan(text, reason_codes=REASON_CODES):
    m = re.search(r"\{.*\}", text, re.S); obj = json.loads(m.group(0)) if m else {}
    status = obj.get("status", "answer"); status = status if status in ("answer", "abstain", "clarify") else "answer"
    return (status, [r for r in obj.get("reasons", []) if r in reason_codes], obj.get("explanation", ""), obj.get("tool"),
            obj.get("args") or {}, (obj.get("cypher") or "").strip().strip("`").rstrip(";"))


class S(TypedDict, total=False):
    qid: str; question: str; contract: str; value_type: str
    raw: str; status: str; reasons: list; explanation: str; tool: Optional[str]; args: dict; cypher: str
    error: Optional[str]; retries: int; rows: list; facts: dict; model_calls: int


def build_router(llm, run_cypher, system=None, reason_codes=REASON_CODES, max_retries=2):
    """LangGraph: plan -> template | free -> format, with retry on a failed check (same graph shape as notebook 06)."""
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import SystemMessage, HumanMessage
    system = system or build_system(reason_codes)

    def plan(st):
        human = f"Question {st['qid']}: {st['question']}\nContract: {st.get('contract', '')}\nValue type: {st.get('value_type', 'auto')}"
        if st.get("error"):
            human += f"\n\nYour previous attempt failed: {st['error']}\nPrevious choice: tool={st.get('tool')} args={json.dumps(st.get('args'))}\nReturn a corrected JSON object."
        out = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        text = out.content if isinstance(out.content, str) else "\n".join(b.get("text", "") for b in out.content if isinstance(b, dict))
        try:
            status, reasons, expl, tool, args, cypher = parse_plan(text, reason_codes)
            if not st["qid"].startswith("Q"): reasons = single_v2_reason(reasons, status)
            err = None if status != "answer" or tool else "no tool chosen"
            return {"raw": text, "status": status, "reasons": reasons, "explanation": expl, "tool": tool, "args": args,
                    "cypher": cypher, "error": err, "rows": [], "model_calls": st.get("model_calls", 0) + 1}
        except Exception as e:
            return {"raw": text, "status": "answer", "tool": None, "error": f"unparseable JSON: {type(e).__name__}", "rows": [],
                    "model_calls": st.get("model_calls", 0) + 1}

    def run_template(st):
        try:
            res = run_any(run_cypher, st["tool"], st["args"])
            return {"rows": res["rows"], "cypher": res["cypher"], "args": res["params"],
                    "error": None if res["rows"] or st.get("value_type") == "decimal" else "tool returned no rows"}
        except ToolClarification as e:
            ids = [str(c.get("id", c)) for c in e.candidates]
            scope = "country_scope" if ids and all(len(i) == 2 and i.isupper() for i in ids) else "organisation_scope"
            return {"rows": [], "status": "clarify", "reasons": [scope], "error": None,
                    "explanation": f"{e}; candidates: " + ", ".join(ids[:5])}
        except Exception as e:
            return {"rows": [], "error": f"{type(e).__name__}: {str(e)[:300]}"}

    def run_free(st):
        try:
            guard_query(st["cypher"]); rows = run_cypher(st["cypher"])
        except Exception as e:
            return {"rows": [], "error": f"free_cypher failed {type(e).__name__}: {str(e)[:300]}"}
        for r in rows:
            if set(r) != {"key", "value", "evidence"}:
                return {"rows": [], "error": f"free_cypher must return key, value, evidence; got {sorted(r)}"}
        ev_err = evidence_error(rows)
        if ev_err: return {"rows": [], "error": ev_err}
        return {"rows": rows, "error": None if rows or st.get("value_type") == "decimal" else "free_cypher returned no rows"}

    def format_(st):
        if st["status"] != "answer" or st.get("error"): return {"facts": {}}
        rows = st.get("rows") or [{"key": "total", "value": 0, "evidence": []}]
        for r in rows: r["evidence"] = clean_evidence(r.get("evidence"))[0]
        facts = rows_to_facts(rows, st.get("value_type", "auto"))
        return {"facts": normalise_facts(facts, st["question"], legacy=st["qid"].startswith("Q"))}

    def after_plan(st):
        if st["status"] != "answer": return "format"
        if st.get("error"): return "retry" if st.get("retries", 0) < max_retries else "format"
        return "free" if st["tool"] == "free_cypher" else "template"

    def after_exec(st): return ("retry" if st.get("retries", 0) < max_retries else "format") if st.get("error") else "format"

    g = StateGraph(S)
    for n, f in [("plan", plan), ("template", run_template), ("free", run_free), ("format", format_),
                 ("retry", lambda st: {"retries": st.get("retries", 0) + 1})]:
        g.add_node(n, f)
    g.set_entry_point("plan")
    g.add_conditional_edges("plan", after_plan, {"format": "format", "retry": "retry", "free": "free", "template": "template"})
    g.add_conditional_edges("template", after_exec, {"retry": "retry", "format": "format"})
    g.add_conditional_edges("free", after_exec, {"retry": "retry", "format": "format"})
    g.add_edge("retry", "plan"); g.add_edge("format", END)
    return g.compile()


# ------------------------------------------------------------------------------------------- engine --
def make_llm(name: str):
    """'anthropic/<model>' or '<provider>/<model>' for an OpenAI-compatible provider configured in .env."""
    provider, _, model = name.partition("/")
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0, max_tokens=1200, timeout=120)
    from langchain_openai import ChatOpenAI
    key, url = os.environ.get(f"{provider.upper()}_API_KEY"), os.environ.get(f"{provider.upper()}_BASE_URL")
    if not (key and url):
        raise RuntimeError(f"{provider.upper()}_API_KEY / _BASE_URL not set in .env")
    return ChatOpenAI(model=model, api_key=key, base_url=url, temperature=0, max_tokens=1200, timeout=180)


def connect_neo4j():
    from neo4j import GraphDatabase, Query, READ_ACCESS
    driver = GraphDatabase.driver(os.environ["NEO4J_URI"], auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    driver.verify_connectivity()
    db = os.environ.get("NEO4J_DATABASE") or "neo4j"

    def run_cypher(q, params=None):
        guard_query(q)
        with driver.session(database=db, default_access_mode=READ_ACCESS) as s:
            return [dict(r) for r in s.run(Query(q, timeout=60), **(params or {}))]
    return driver, run_cypher


class Engine:
    """One model, one graph, one router. ask() returns the answer contract plus provenance."""

    def __init__(self, model: str = DEFAULT_MODEL, env_path: Path = FA26 / ".env", run_cypher=None, llm=None,
                 snapshot_dir: Path = FA26 / "benchmark" / "snapshot"):
        load_dotenv(env_path, override=False)
        self.model = model
        self.llm = llm or make_llm(model)
        self.driver = None
        if run_cypher is None:
            self.driver, run_cypher = connect_neo4j()
        self.run_cypher = run_cypher
        self.router = build_router(self.llm, run_cypher)
        self.snapshot_dir = Path(snapshot_dir)
        self._rows: dict[str, list[dict]] = {}
        self._n = 0

    def ask(self, question: str, qid: str | None = None) -> dict:
        self._n += 1
        qid = qid or f"ASK{self._n:04d}"
        t0 = time.time()
        try:
            st = self.router.invoke({"qid": qid, "question": question, "contract": "", "value_type": "auto", "retries": 0, "model_calls": 0})
        except Exception as e:
            st = {"status": "answer", "facts": {}, "reasons": [], "error": f"{type(e).__name__}: {str(e)[:200]}", "retries": 0}
        status = st.get("status", "answer")
        out = {"id": qid, "question": question, "status": status,
               "facts": st.get("facts", {}) if status == "answer" else {},
               "reasons": st.get("reasons", []) if status != "answer" else [],
               "explanation": st.get("explanation"), "tool": st.get("tool"), "args": st.get("args"),
               "cypher": st.get("cypher"), "error": st.get("error"), "retries": st.get("retries", 0),
               "model": self.model, "latency_ms": round((time.time() - t0) * 1000, 1)}
        out["evidence_count"] = sum(len(f["evidence"]) for f in out["facts"].values())
        return out

    def evidence_rows(self, answer: dict, limit: int = 50) -> list[dict]:
        """Snapshot rows behind the answer: [{id, table, row, **columns}], first `limit` ids."""
        ids = sorted({e for f in answer.get("facts", {}).values() for e in f.get("evidence", []) if not e.startswith("manifest:")})
        out = []
        for e in ids[:limit]:
            table, _, n = e.partition(":row:")
            rows = self._table(table)
            i = int(n) - 1
            if 0 <= i < len(rows):
                out.append({"id": e, "table": table, "row": int(n), **rows[i]})
        return out

    def _table(self, name):
        if name not in self._rows:
            csv.field_size_limit(10_000_000)
            with (self.snapshot_dir / name).open(encoding="utf-8", newline="") as fh:
                self._rows[name] = list(csv.DictReader(fh))
        return self._rows[name]

    def close(self):
        if self.driver: self.driver.close()


__all__ = ["Engine", "build_router", "build_system", "make_llm", "connect_neo4j", "REASON_CODES", "DEFAULT_MODEL"]
