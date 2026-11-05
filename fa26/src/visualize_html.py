"""
04_visualize.py -- Build a standalone interactive HTML graph from data/graph/.

Reads the pipeline's CSVs directly (no Neo4j needed) and renders an
interactive force-directed graph with pyvis. The output is a single HTML
file you can email or host -- viewers just open it in a browser.

Transactions are aggregated rather than drawn: 22k transaction nodes would
swamp the layout, so funding is shown as weighted FUNDS edges
(provider organisation -> activity, sized by transaction count, totals in
the tooltip).

Setup:
    pip install pyvis

Usage:
    python 04_visualize.py                       # full graph
    python 04_visualize.py --country YE          # one hotspot's neighborhood
    python 04_visualize.py --country YE --country SS
    python 04_visualize.py --min-links 2         # hide one-off partner orgs
    python 04_visualize.py --out demo.html
"""
import argparse
import csv
from collections import defaultdict

from config import GRAPH_DIR, HOTSPOTS

COLORS = {
    "Activity":     "#7c5cbf",
    "Organisation": "#2a9d8f",
    "Country":      "#4a8c5c",
    "Sector":       "#8a8a8a",
    "Emergency":    "#e07856",
    "SDG":          "#4a8c5c",
}


def rows(name):
    path = GRAPH_DIR / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build(countries_filter, min_links, out):
    from pyvis.network import Network

    acts = rows("nodes_activities.csv")
    if countries_filter:
        wanted = set(countries_filter)
        acts = [a for a in acts
                if wanted & set(a["hotspot_countries"].split("|"))]
    act_ids = {a["iati_identifier"] for a in acts}
    print(f"{len(acts)} activities selected")

    net = Network(height="97vh", width="100%", directed=True,
                  bgcolor="#ffffff", font_color="#333333",
                  cdn_resources="in_line", select_menu=True, filter_menu=True)
    net.barnes_hut(gravity=-8000, spring_length=120)

    def add(node_id, label, kind, title):
        net.add_node(node_id, label=label, color=COLORS[kind],
                     title=title, group=kind,
                     shape="dot" if kind != "Country" else "diamond",
                     size=28 if kind == "Country" else 12)

    # Countries (only hotspots the selection touches)
    touched = set()
    for a in acts:
        touched |= set(a["hotspot_countries"].split("|"))
    for c in rows("nodes_countries.csv"):
        if c["code"] in touched:
            add(f'C:{c["code"]}', c["name"], "Country",
                f'{c["name"]} — hotspot tier {c["hotspot_tier"]}')

    # Activities
    for a in acts:
        title = (f'{a["title"]}<br>{a["publisher"]} | {a["start_planned"] or a["start_actual"] or "?"}'
                 f'<br>match: {a["match_basis"]}')
        add(f'A:{a["iati_identifier"]}', a["title"][:34] or a["iati_identifier"],
            "Activity", title)
        for cc in a["hotspot_countries"].split("|"):
            if cc:
                net.add_edge(f'A:{a["iati_identifier"]}', f"C:{cc}",
                             color="#4a8c5c", width=1)

    # Organisations via participation (trim one-off partners with --min-links)
    org_names = {o["ref"]: o["name"] or o["ref"] for o in rows("nodes_organisations.csv")}
    org_links = defaultdict(list)
    for r in rows("rel_participates.csv"):
        if r["iati_identifier"] in act_ids:
            org_links[r["org_ref"]].append(r)
    for ref, links in org_links.items():
        if len(links) < min_links:
            continue
        add(f"O:{ref}", org_names.get(ref, ref)[:30], "Organisation",
            f"{org_names.get(ref, ref)}<br>{len(links)} participations")
        for r in links:
            net.add_edge(f"O:{ref}", f'A:{r["iati_identifier"]}',
                         color="#2a9d8f", width=1,
                         title=f'participates ({r["role"]})')

    # Aggregated funding edges: provider org -> activity
    tx_act = {t["tx_id"]: (t["iati_identifier"], t["value"], t["currency"])
              for t in rows("nodes_transactions.csv")
              if t["iati_identifier"] in act_ids}
    funds = defaultdict(lambda: {"n": 0, "totals": defaultdict(float)})
    for e in rows("rel_transaction_edges.csv"):
        if e["edge"] != "PROVIDED_BY" or e["tx_id"] not in tx_act:
            continue
        iid, value, currency = tx_act[e["tx_id"]]
        f = funds[(e["org_ref"], iid)]
        f["n"] += 1
        try:
            f["totals"][currency or "?"] += float(value)
        except ValueError:
            pass
    for (ref, iid), f in funds.items():
        if len(org_links.get(ref, [])) < min_links and f"O:{ref}" not in [n["id"] for n in net.nodes]:
            add(f"O:{ref}", org_names.get(ref, ref)[:30], "Organisation",
                org_names.get(ref, ref))
        totals = ", ".join(f"{v:,.0f} {c}" for c, v in f["totals"].items())
        net.add_edge(f"O:{ref}", f"A:{iid}", color="#e07856",
                     width=min(1 + f["n"] / 5, 6),
                     title=f'funds: {f["n"]} transactions ({totals})')

    # Sectors, emergencies, SDGs
    sec = {s["sector_key"]: s for s in rows("nodes_sectors.csv")}
    for r in rows("rel_classified_as.csv"):
        if r["iati_identifier"] not in act_ids:
            continue
        s = sec.get(r["sector_key"])
        if not s:
            continue
        sid = f'S:{s["sector_key"]}'
        if sid not in [n["id"] for n in net.nodes]:
            add(sid, (s["name"] or s["code"])[:28], "Sector",
                f'{s["name"]} ({s["vocabulary"]}:{s["code"]}) hunger={s["is_hunger"]}')
        net.add_edge(f'A:{r["iati_identifier"]}', sid, color="#bbbbbb", width=1)

    for name, node_csv, rel_csv, key, kind in (
            ("emergency", "nodes_emergencies.csv", "rel_responds_to.csv", "emergency_key", "Emergency"),
            ("sdg", "nodes_sdgs.csv", "rel_contributes_to.csv", "sdg_key", "SDG")):
        meta = {m[key]: m for m in rows(node_csv)}
        for r in rows(rel_csv):
            if r["iati_identifier"] not in act_ids or r[key] not in meta:
                continue
            m = meta[r[key]]
            nid = f'{kind[0]}#{r[key]}'
            if nid not in [n["id"] for n in net.nodes]:
                add(nid, (m.get("name") or m.get("code", ""))[:28], kind,
                    str(dict(m)))
            net.add_edge(f'A:{r["iati_identifier"]}', nid,
                         color=COLORS[kind], width=1)

    print(f"{len(net.nodes)} nodes, {len(net.edges)} edges -> {out}")
    net.save_graph(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", action="append", default=[],
                    help="hotspot ISO2 code; repeatable (default: all)")
    ap.add_argument("--min-links", type=int, default=1,
                    help="hide partner orgs with fewer participations")
    ap.add_argument("--out", default="iati_graph.html")
    args = ap.parse_args()
    bad = [c for c in args.country if c.upper() not in HOTSPOTS]
    if bad:
        raise SystemExit(f"not hotspot codes: {bad}; valid: {sorted(HOTSPOTS)}")
    build([c.upper() for c in args.country], args.min_links, args.out)
