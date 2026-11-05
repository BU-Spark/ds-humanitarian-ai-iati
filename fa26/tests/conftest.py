import shutil
from pathlib import Path

import pytest

import parse_filter
import review

FIXTURE = Path(__file__).parent / "fixture_iati_2.03.xml"


def _rec(title, description="", sectors=()):
    """Minimal activity record in the shape parse_activity() returns,
    with only the fields hunger_match() reads."""
    return {
        "activity": {"title": title, "description": description},
        "sectors": [{"code": c, "vocabulary": v, "name": n, "percentage": ""}
                    for c, v, n in sectors],
        "transactions": [],
    }


@pytest.fixture
def make_rec():
    return _rec


@pytest.fixture
def fixture_env(tmp_path, monkeypatch):
    """Point the parser and the review files at a temp dir holding the XML
    fixture, so tests never touch data/graph/ or data/review/."""
    raw = tmp_path / "raw"
    (raw / "oxfamgb").mkdir(parents=True)
    shutil.copy(FIXTURE, raw / "oxfamgb" / FIXTURE.name)
    monkeypatch.setattr(parse_filter, "RAW_DIR", raw)
    monkeypatch.setattr(parse_filter, "GRAPH_DIR", tmp_path / "graph")
    monkeypatch.setattr(review, "QUEUE", tmp_path / "review" / "queue.csv")
    monkeypatch.setattr(review, "DECISIONS", tmp_path / "review" / "decisions.csv")
    return tmp_path
