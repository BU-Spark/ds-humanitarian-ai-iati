"""Knowledge base (Milestone 1): build from the pipeline's graph CSVs, keyword
search with filters and citations, CSV export, and the evaluation scorer.
Builds from the XML fixture in a temp dir, never from data/."""
import csv
import json
import sqlite3

import pytest

import parse_filter
from kb import build, evaluate, search


@pytest.fixture
def kb(fixture_env):
    parse_filter.run("oxfamgb")
    return build.build(fixture_env / "graph", fixture_env / "kb" / "kb.sqlite")


def test_build_has_one_entry_per_kept_activity(kb, fixture_env):
    with open(fixture_env / "graph" / "nodes_activities.csv", encoding="utf-8") as f:
        kept = {r["iati_identifier"] for r in csv.DictReader(f)}
    db = sqlite3.connect(kb)
    ids = {r[0] for r in db.execute("SELECT iati_identifier FROM activities")}
    fts = db.execute("SELECT count(*) FROM activities_fts").fetchone()[0]
    meta = dict(db.execute("SELECT key, value FROM kb_meta"))
    assert ids == kept and fts == len(kept)
    assert meta["activities"] == str(len(kept))


def test_search_cites_and_ranks(kb):
    hits = search.search("hunger and malnutrition", kb_path=kb)
    assert hits[0]["iati_identifier"] == "US-EIN-237069110-TEST004"
    assert hits[0]["rank"] == 1 and hits[0]["score"] > 0
    assert "[" in hits[0]["snippet"]  # matched words are marked


def test_stemming_and_accents(kb):
    # "transfer" finds "Cash transfers"; the stored text keeps its accents
    assert search.search("cash transfer", kb_path=kb)
    assert search.to_fts_query("sécurité") == '"sécurité"'


def test_country_and_publisher_filters(kb):
    assert {h["iati_identifier"] for h in search.search("food", country="SS", kb_path=kb)} \
        == {"GB-CHC-202918-TEST001"}
    assert search.search("food", country="South Sudan", kb_path=kb)
    assert search.search("food", publisher="oxfamus", kb_path=kb) == [] or all(
        h["publisher"] == "oxfamus" for h in search.search("food", publisher="oxfamus", kb_path=kb))
    with pytest.raises(ValueError):
        search.search("food", country="Narnia", kb_path=kb)


def test_min_confidence_filter(kb):
    hits = search.search("livelihoods resilience", min_confidence="medium", kb_path=kb)
    assert all(h["confidence"] in ("medium", "high") for h in hits)
    assert "GB-CHC-202918-TEST006" not in {h["iati_identifier"] for h in hits}  # low


@pytest.mark.parametrize("text", [
    'malnutrition AND NOT "children', "food (aid)*", "NEAR(x y)", "C'est l'aide",
])
def test_odd_questions_do_not_raise(kb, text):
    search.search(text, kb_path=kb)


def test_stopword_only_question_returns_nothing(kb):
    assert search.to_fts_query("which projects are there?") == ""
    assert search.search("which projects are there?", kb_path=kb) == []


def test_phrases_are_kept_together():
    assert search.to_fts_query('"school meals" in Yemen') == '"school meals" OR "yemen"'


def test_export_csv(kb, tmp_path):
    out = tmp_path / "hits.csv"
    search.export_csv(search.search("food", kb_path=kb), out)
    with open(out, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows and rows[0]["iati_identifier"] and rows[0]["rank"] == "1"


def test_missing_kb_says_how_to_build(tmp_path):
    with pytest.raises(FileNotFoundError, match="kb.build"):
        search.search("food", kb_path=tmp_path / "none.sqlite")


def test_evaluate_scores(kb, tmp_path):
    qfile = tmp_path / "q.json"
    qfile.write_text(json.dumps({"questions": [{
        "id": "T1", "question": "hunger malnutrition", "country": None,
        "kind": "topic", "relevant": ["US-EIN-237069110-TEST004"]}]}))
    [r] = evaluate.evaluate(qfile, kb_path=kb)
    assert r["rr"] == 1.0 and r["r20"] == 1.0 and r["p10"] == 0.1


def test_eval_questions_reference_kb_activities():
    # every judged activity id is well formed and listed once per question
    data = json.loads(evaluate.QUESTIONS.read_text(encoding="utf-8"))
    for q in data["questions"]:
        assert q["relevant"] and len(set(q["relevant"])) == len(q["relevant"]), q["id"]
        assert all(i.startswith(("GB-CHC-", "XM-DAC-", "US-EIN-")) for i in q["relevant"])
