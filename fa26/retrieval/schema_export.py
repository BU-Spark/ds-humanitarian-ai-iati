"""
schema_export.py -- the graph schema as XML, for a language model to read
before it routes a question or writes Cypher.

Everything structural is read from the loaded graph (labels, property types,
relationship directions, counts, the values of small string properties), so
the text cannot drift from what load_neo4j.py produced. Code names, key
properties and the funding rule come from schema_prototype.py and tools.py.

    python schema_export.py                     # print to stdout
    python schema_export.py --out schema.xml    # write a file
    python schema_export.py --env PATH          # another .env

    from schema_export import graph_schema_xml
    prompt = "Graph schema:\\n" + graph_schema_xml()
"""
import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db                                        # noqa: E402
import schema_prototype as S                     # noqa: E402
from tools import FUNDING_TRANSACTION_TYPE       # noqa: E402

MAX_VALUES = 20          # list a string property's values when it has at most this many ...
MAX_VALUES_CHARS = 300   # ... and together they are at most this long (keeps long free text out)
INTERNAL_LABELS = ("LoadMeta",)

# (label or relationship type, property) -> {code: name}, shown as "code=name"
CODE_NAMES = {
    ("Transaction", "type"): S.TRANSACTION_TYPES,
    ("Activity", "status"): S.ACTIVITY_STATUS,
    ("Budget", "type"): S.BUDGET_TYPES,
    ("Budget", "status"): S.BUDGET_STATUS,
    ("PARTICIPATES_IN", "role"): S.ORG_ROLES,
}

RULES = [
    f'"Funding" means Transaction.type_name = "{FUNDING_TRANSACTION_TYPE}". The funder is the Organisation '
    "on the PROVIDES relationship; leave out rows where that Organisation is the activity's own reporting "
    "organisation. Never add different transaction types together: WFP repeats every Outgoing Commitment "
    "as an identical Expenditure.",
    "Money: for exact totals use sum(value_cents) / 100.0 (dividing by the integer 100 truncates). Report positive and negative transactions "
    "separately (amount, adjustments, net = amount + adjustments). Group by currency; never add or convert "
    "currencies.",
    "Dates are DATE values: use t.date.year, not string comparison. Activity.start_date and end_date hold "
    "the actual date when there is one, otherwise the planned date.",
    'Citations: every node has source_id and every relationship has source_ids (a list), each naming a '
    'source CSV row, for example "nodes_transactions.csv:row:12".',
    'An Organisation.ref starting with "name:" has no IATI identifier. One organisation can appear under '
    "several refs, so resolve names with resolve_entity or the retrieval tools, not by matching "
    "Organisation.name in Cypher.",
    "The graph holds only hunger-related activities in the hotspot countries, so totals are not totals for "
    "a publisher as a whole.",
    'A value list written as "code=name" (for example "1=Incoming Funds") means the property holds the code '
    '("1"); the property with the same name plus "_name" holds the name ("Incoming Funds").',
]

NODE_PROPS = ("CALL db.schema.nodeTypeProperties() YIELD nodeLabels, propertyName, propertyTypes, mandatory "
              "RETURN nodeLabels[0] AS owner, propertyName AS name, propertyTypes AS types, mandatory LIMIT 5000")
REL_PROPS = ("CALL db.schema.relTypeProperties() YIELD relType, propertyName, propertyTypes, mandatory "
             "RETURN relType AS owner, propertyName AS name, propertyTypes AS types, mandatory LIMIT 5000")
NODE_COUNTS = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n LIMIT 1000"
REL_SHAPES = ("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS src, type(r) AS rel, labels(b)[0] AS dst, count(*) AS n "
              "LIMIT 1000")
NODE_VALUES = ("MATCH (n) UNWIND keys(n) AS k WITH labels(n)[0] AS owner, k, n[k] AS v "
               "WHERE valueType(v) STARTS WITH 'STRING' "
               "WITH owner, k, collect(DISTINCT v) AS vals WHERE size(vals) <= $max "
               "RETURN owner, k AS name, vals LIMIT 5000")
REL_VALUES = ("MATCH ()-[r]->() UNWIND keys(r) AS k WITH type(r) AS owner, k, r[k] AS v "
              "WHERE valueType(v) STARTS WITH 'STRING' "
              "WITH owner, k, collect(DISTINCT v) AS vals WHERE size(vals) <= $max "
              "RETURN owner, k AS name, vals LIMIT 5000")


def _type(types):
    """['STRING NOT NULL'] -> 'STRING'; ['LIST<STRING NOT NULL> NOT NULL'] -> 'LIST OF STRING'."""
    return " | ".join(sorted({re.sub(r"LIST<(.+)>", r"LIST OF \1", t.replace(" NOT NULL", "")) for t in types}))


def _keys():
    """label -> unique key property, from the constraints the loader creates."""
    pat = re.compile(r"FOR \(n:(\w+)\) REQUIRE n\.(\w+) IS UNIQUE")
    return dict(m.groups() for m in map(pat.search, S.CONSTRAINTS) if m)


def _props(rows, strip=False):
    out = {}
    for r in rows:
        if r["name"] is None:        # a label or relationship type with no properties
            continue
        owner = r["owner"].strip(":`") if strip else r["owner"]
        out.setdefault(owner, {})[r["name"]] = (_type(r["types"]), r["mandatory"])
    return out


def _values(rows):
    return {(r["owner"], r["name"]): sorted(r["vals"]) for r in rows
            if r["name"] != "source_id" and sum(map(len, r["vals"])) <= MAX_VALUES_CHARS}


def _add_props(parent, owner, props, values, key=None):
    for name in sorted(props, key=lambda p: (p != key, p)):
        typ, mandatory = props[name]
        attrs = {"name": name, "type": typ}
        if not mandatory:
            attrs["optional"] = "true"
        vals = values.get((owner, name))
        if vals:
            names = CODE_NAMES.get((owner, name), {})
            attrs["values"] = " | ".join(f"{v}={names[v]}" if v in names else v for v in vals)
        ET.SubElement(parent, "property", attrs)


def graph_schema_xml():
    """The schema of the graph the current .env points at, as an XML string."""
    node_props = _props(db.read_query(NODE_PROPS))
    rel_props = _props(db.read_query(REL_PROPS), strip=True)
    counts = {r["label"]: r["n"] for r in db.read_query(NODE_COUNTS) if r["label"] not in INTERNAL_LABELS}
    shapes = sorted(db.read_query(REL_SHAPES), key=lambda r: (r["rel"], r["src"], r["dst"]))
    values = _values(db.read_query(NODE_VALUES, {"max": MAX_VALUES}) + db.read_query(REL_VALUES, {"max": MAX_VALUES}))
    keys = _keys()

    root = ET.Element("graph_schema", {"schema": S.NAME, "nodes": str(sum(counts.values())),
                                       "relationships": str(sum(r["n"] for r in shapes))})
    for label in sorted(counts):
        attrs = {"label": label, "count": str(counts[label])}
        if label in keys:
            attrs["key"] = keys[label]
        _add_props(ET.SubElement(root, "node", attrs), label, node_props.get(label, {}), values, keys.get(label))
    for r in shapes:
        el = ET.SubElement(root, "relationship", {"type": r["rel"], "from": r["src"], "to": r["dst"],
                                                  "count": str(r["n"])})
        _add_props(el, r["rel"], rel_props.get(r["rel"], {}), values)
    rules = ET.SubElement(root, "rules")
    for text in RULES:
        ET.SubElement(rules, "rule").text = text
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", help="path to .env")
    ap.add_argument("--out", help="write here instead of stdout")
    args = ap.parse_args()
    if args.env:
        os.environ["RETRIEVAL_ENV"] = args.env
    xml = graph_schema_xml()
    if args.out:
        Path(args.out).write_text(xml, encoding="utf-8")
    else:
        sys.stdout.write(xml)
    db.close()


if __name__ == "__main__":
    main()
