"""schema_export: the XML must describe the graph that is actually loaded."""
import xml.etree.ElementTree as ET

import pytest

import schema_prototype as S
from tools import FUNDING_TRANSACTION_TYPE


@pytest.fixture(scope="module")
def schema(graph_db):
    from schema_export import graph_schema_xml
    return ET.fromstring(graph_schema_xml())


def _node(schema, label):
    return schema.find(f"node[@label='{label}']")


def _prop(el, name):
    return el.find(f"property[@name='{name}']")


def _values(el, name):
    return {v.split("=")[0] for v in _prop(el, name).get("values").split(" | ")}


def test_node_counts_match_the_csvs(schema, csv):
    assert _node(schema, "Activity").get("count") == str(len(csv["act"]))
    assert _node(schema, "Transaction").get("count") == str(len(csv["tx"]))
    assert _node(schema, "LoadMeta") is None                       # loader bookkeeping stays out


def test_keys_and_types_the_tools_rely_on(schema):
    tx = _node(schema, "Transaction")
    assert tx.get("key") == "tx_id"
    assert _prop(tx, "value").get("type") == "FLOAT"
    assert _prop(tx, "value_cents").get("type") == "INTEGER"
    assert _prop(tx, "date").get("type") == "DATE"
    assert _prop(_node(schema, "Activity"), "hotspot_countries").get("type") == "LIST OF STRING"


def test_value_lists_match_the_csvs(schema, csv):
    assert _values(_node(schema, "Activity"), "publisher") == set(csv["act"].publisher)
    assert _values(_node(schema, "Transaction"), "currency") == set(csv["tx"].currency)
    codes = _prop(_node(schema, "Transaction"), "type").get("values").split(" | ")
    assert set(codes) == {f"{c}={S.TRANSACTION_TYPES[c]}" for c in set(csv["tx"].type)}
    assert _prop(_node(schema, "Activity"), "title").get("values") is None   # free text is never listed


def test_relationship_directions(schema):
    shape = {(r.get("from"), r.get("type"), r.get("to")) for r in schema.findall("relationship")}
    assert ("Organisation", "PROVIDES", "Transaction") in shape
    assert ("Transaction", "RECEIVED_BY", "Organisation") in shape
    assert ("Activity", "HAS_TRANSACTION", "Transaction") in shape


def test_every_relationship_pattern_runs_and_counts_match(schema, graph_db):
    for r in schema.findall("relationship"):
        cypher = f"MATCH (:{r.get('from')})-[x:{r.get('type')}]->(:{r.get('to')}) RETURN count(x) AS n LIMIT 1"
        assert graph_db.read_query(cypher)[0]["n"] == int(r.get("count")), r.get("type")


def test_rules_a_model_would_follow(schema):
    rules = " ".join(r.text for r in schema.findall("rules/rule"))
    assert f'"{FUNDING_TRANSACTION_TYPE}"' in rules
    assert "sum(value_cents) / 100.0" in rules          # integer division would drop the cents
    assert '"code=name"' in rules                         # legend for the value lists
