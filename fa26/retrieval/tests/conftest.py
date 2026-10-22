"""Shared fixtures: the CSVs as pandas frames (ground truth) and a skip
when no Neo4j is reachable through .env."""
import sys
from pathlib import Path

import pandas as pd
import pytest

RETRIEVAL = Path(__file__).resolve().parents[1]
ROOT = RETRIEVAL.parent
GRAPH = ROOT / "data" / "graph"
sys.path.insert(0, str(RETRIEVAL))


def _load(name):
    return pd.read_csv(GRAPH / name, dtype=str).fillna("")


@pytest.fixture(scope="session")
def csv():
    """dict of frames with the same derived columns the loader adds."""
    act = _load("nodes_activities.csv")
    act["start"] = act.start_actual.where(act.start_actual != "", act.start_planned)
    act["end"] = act.end_actual.where(act.end_actual != "", act.end_planned)
    act["start_year"] = act.start.str[:4].astype(int)
    act["end_year"] = act.end.where(act.end != "", act.start).str[:4].astype(int)
    act["countries"] = act.hotspot_countries.str.split("|")
    tx = _load("nodes_transactions.csv")
    tx["value"] = pd.to_numeric(tx.value)
    tx["year"] = tx.date.str[:4].astype(int)
    tx["publisher"] = tx.iati_identifier.map(act.set_index("iati_identifier").publisher)
    return {
        "act": act, "tx": tx,
        "org": _load("nodes_organisations.csv"),
        "part": _load("rel_participates.csv"),
        "txe": _load("rel_transaction_edges.csv"),
        "rep": _load("rel_reports.csv"),
    }


@pytest.fixture(scope="session")
def graph_db():
    """Skip the whole module when Neo4j is not reachable."""
    import db
    try:
        db.get_driver().verify_connectivity()      # no retry loop, fails in seconds
        db.read_query("RETURN 1 AS ok LIMIT 1")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Neo4j not reachable via .env: {e}")
    return db
