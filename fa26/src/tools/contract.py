"""Output contract for benchmark answers: evidence ids, scalar fact keys, reason codes.

The templates satisfy the contract by construction. Free Text2Cypher answers do not, so the agent's
validate step calls these checks and sends the failure back to the planner for a retry; the format step
applies the same rules once more so a submission can never be rejected by the scorer.

Contract (benchmark v1 and v2, fa26/benchmark/v2/README.md and the exported bundle README):
* evidence id = "<table>.csv:row:<n>" for a table in the pinned manifest (n counts data rows from 1),
  or "manifest:<table>.csv" for a zero-result answer;
* a single count is keyed "count", a single monetary amount "total", a single date "date";
  amounts requested by currency are keyed by currency code;
* clarify / abstain reasons come from the bundle's global vocabulary.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

FA26 = Path(__file__).resolve().parents[2]
_ROW = re.compile(r"^([A-Za-z0-9_]+\.csv):row:(\d+)$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
SCALAR_KEYS = ("count", "total", "date")

_FILES: set[str] | None = None


def manifest_files(manifest: Path = FA26 / "benchmark" / "manifest.json") -> set[str]:
    global _FILES
    if _FILES is None:
        _FILES = set(json.loads(manifest.read_text())["files"])
    return _FILES


# ------------------------------------------------------------------------------------------ evidence --
def valid_evidence_id(e) -> bool:
    if not isinstance(e, str):
        return False
    m = _ROW.match(e)
    if m:
        return m.group(1) in manifest_files() and int(m.group(2)) >= 1
    return e.startswith("manifest:") and e[len("manifest:"):] in manifest_files()


def clean_evidence(evidence) -> tuple[list[str], list]:
    """(kept, dropped). A bare string is one id, never a sequence of characters."""
    if evidence is None:
        return [], []
    if isinstance(evidence, str):
        evidence = [evidence]
    kept, dropped = [], []
    for e in evidence:
        (kept if valid_evidence_id(e) else dropped).append(e)
    return sorted(set(kept)), dropped


def evidence_error(rows) -> str | None:
    """None when every row's evidence is contract-conformant, else a retry message naming examples."""
    bad = []
    for r in rows or []:
        _, dropped = clean_evidence(r.get("evidence"))
        bad += dropped[:2]
        if len(bad) >= 4:
            break
    if not bad:
        return None
    return ("evidence must be source_id values like nodes_activities.csv:row:12 (use a.source_id, "
            "t.source_id, o.source_id and r.source_ids on relationships), not identifiers such as "
            + ", ".join(repr(str(b))[:40] for b in bad[:3]))


# ------------------------------------------------------------------------------------------ fact keys --
def scalar_kind(question: str) -> str | None:
    """Which scalar key a single-fact answer to this question should carry, if any."""
    q = (question or "").strip().lower()
    if q.startswith("how many") or q.startswith("what is the number of") or q.startswith("count "):
        return "count"
    if q.startswith("how much") or re.search(r"\b(total|sum|amount)\b", q):
        return "total"
    if q.startswith("when") or re.search(r"\b(earliest|latest)\b.*\bdate\b|\bdate\b", q):
        return "date"
    return None


def normalise_facts(facts: dict, question: str, legacy: bool = False) -> dict:
    """Rename the key of a single-fact answer to the contract's scalar key when the question is scalar.
    Multi-fact answers (per publisher, per currency, per year) are left alone; legacy Q01-Q20 keep
    their original contracts."""
    if legacy or not facts or len(facts) != 1:
        return facts
    key = next(iter(facts))
    if key in SCALAR_KEYS or _CURRENCY.match(key):
        return facts
    kind = scalar_kind(question)
    return {kind: facts[key]} if kind else facts


# --------------------------------------------------------------------------------------------- reasons --
V1_REASONS = ["NEEDS_DATA_MISSING", "HISTORY_UNAVAILABLE", "FUNDING_DEFINITION_REQUIRED",
              "CURRENCY_BASIS_REQUIRED", "PERIOD_REQUIRED", "RAW_XML_UNAVAILABLE"]


def invalid_reasons(reasons, vocabulary) -> list[str]:
    vocab = set(vocabulary or [])
    return [r for r in (reasons or []) if r not in vocab]


V2_REASON_GUIDE = """
REASON CODES FOR NEW (V2Q*) QUESTIONS. Use the lower-case scope codes, one per clarify, never the
upper-case legacy codes (those are only for Q01-Q20):
- organisation_scope: the organisation is named loosely ("Oxfam" = GB or America?, "the UN", "America",
  "the government", "our partners", "the ministry").
- funding_scope: a vague money question about a named funder with no measure/currency/period
  ("How much did the UK give?").
- country_scope: the country is ambiguous ("Congo" = CD or CG?).
For abstain on limitation questions use the matching *_unavailable code (outcomes, misuse, balances,
identity, personal_details, forecast, coverage, exchange_rates).
""".strip()


__all__ = ["valid_evidence_id", "clean_evidence", "evidence_error", "scalar_kind", "normalise_facts",
           "invalid_reasons", "V1_REASONS", "V2_REASON_GUIDE", "manifest_files", "SCALAR_KEYS"]
