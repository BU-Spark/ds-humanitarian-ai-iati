"""
IATI Hunger Hotspots Knowledge Graph -- interactive demo.

Self-contained Gradio app for Hugging Face Spaces. Reads the graph CSVs
produced by the iati-hunger-graph pipeline from ./data/ and offers:
  - an interactive force-directed graph explorer (pyvis)
  - canned analysis questions (pandas)

No database required.
"""
import html as html_mod
from collections import defaultdict
from pathlib import Path

import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pyvis.network import Network

def _find_data():
    """Local runs read the pipeline output directly (single source of
    truth). A bundled spaces/data/ copy takes precedence only when it
    actually contains data -- i.e. on Hugging Face Spaces, where the
    pipeline folder doesn't exist."""
    bundled = Path(__file__).parent / "data"
    pipeline_out = Path(__file__).resolve().parents[1] / "data" / "graph"
    if (bundled / "nodes_activities.csv").exists():
        return bundled
    return pipeline_out


DATA = _find_data()

HOTSPOT_NAMES = {
    "SD": "Sudan", "SS": "South Sudan", "YE": "Yemen", "PS": "Palestine",
    "NG": "Nigeria", "SO": "Somalia", "AF": "Afghanistan",
    "CD": "DR Congo", "HT": "Haiti", "LB": "Lebanon",
    "MG": "Madagascar", "MM": "Myanmar", "ML": "Mali",
}
PUB_LABELS = {"oxfamgb": "Oxfam GB", "oxfamus": "Oxfam America", "wfp": "WFP"}

COLORS = {"Activity": "#7c5cbf", "Organisation": "#2a9d8f",
          "Country": "#4a8c5c", "Sector": "#8a8a8a"}


def load(name):
    p = DATA / name
    return pd.read_csv(p, dtype=str).fillna("") if p.exists() else pd.DataFrame()


ACT = load("nodes_activities.csv")
ORG = load("nodes_organisations.csv")
SEC = load("nodes_sectors.csv")
TX = load("nodes_transactions.csv")
BUD = load("nodes_budgets.csv")
PART = load("rel_participates.csv")
TXE = load("rel_transaction_edges.csv")
CLS = load("rel_classified_as.csv")

if not ACT.empty:
    ACT["countries"] = ACT["hotspot_countries"].str.split("|")
    ACT["start"] = ACT["start_actual"].where(ACT["start_actual"] != "", ACT["start_planned"])
    ACT["year"] = ACT["start"].str[:4]
if ACT.empty:
    raise SystemExit("No data in spaces/data/ — copy the pipeline's data/graph/*.csv there first.")
PUB2ACT = ACT.set_index("iati_identifier")["publisher"].to_dict() if not ACT.empty else {}
if not TX.empty and not ACT.empty:
    _defcur = ACT.set_index("iati_identifier")["default_currency"].to_dict()
    TX.loc[TX["currency"] == "", "currency"] = \
        TX.loc[TX["currency"] == "", "iati_identifier"].map(_defcur).fillna("")
ORG_NAME = ORG.set_index("ref")["name"].to_dict() if not ORG.empty else {}


# ------------------------------------------------------------- graph tab --
def org_choices():
    if PART.empty:
        return []
    deg = PART["org_ref"].value_counts()
    out = []
    for ref, n in deg.head(150).items():
        nm = ORG_NAME.get(ref) or ref
        out.append(f"{nm} [{n}]|{ref}")
    return sorted(out, key=str.lower)


def graph_html(countries, publishers, min_links, show_sectors, focus_org=None):
    acts = ACT
    if focus_org and "|" in focus_org:
        ref = focus_org.rsplit("|", 1)[1]
        ids = set(PART[PART["org_ref"] == ref]["iati_identifier"])
        acts = acts[acts["iati_identifier"].isin(ids)]
        min_links = 1
    if countries:
        codes = {c.split(" — ")[0] for c in countries}
        acts = acts[acts["countries"].apply(lambda cc: bool(codes & set(cc)))]
    if publishers:
        pubs = {k for k, v in PUB_LABELS.items() if v in publishers}
        acts = acts[acts["publisher"].isin(pubs)]
    if acts.empty:
        return "<p style='padding:2em'>No activities match these filters.</p>"
    if len(acts) > 900:
        return (f"<p style='padding:2em'>{len(acts)} activities selected — too many "
                "to draw at once. Narrow to one or two countries.</p>")

    act_ids = set(acts["iati_identifier"])
    net = Network(height="640px", width="100%", directed=True,
                  bgcolor="#ffffff", font_color="#333", cdn_resources="in_line")
    net.barnes_hut(gravity=-9000, spring_length=130)
    seen = set()

    def add(nid, label, kind, title):
        if nid in seen:
            return
        seen.add(nid)
        net.add_node(nid, label=label, color=COLORS[kind], title=title,
                     shape="diamond" if kind == "Country" else "dot",
                     size=30 if kind == "Country" else 12)

    for _, a in acts.iterrows():
        add("A:" + a["iati_identifier"], a["title"][:34] or a["iati_identifier"],
            "Activity",
            f'{a["title"]} | {PUB_LABELS.get(a["publisher"], a["publisher"])} | {a["start"] or "?"}')
        for cc in a["countries"]:
            if cc:
                add("C:" + cc, HOTSPOT_NAMES.get(cc, cc), "Country",
                    HOTSPOT_NAMES.get(cc, cc))
                net.add_edge("A:" + a["iati_identifier"], "C:" + cc,
                             color="#4a8c5c", width=1)

    links = PART[PART["iati_identifier"].isin(act_ids)]
    counts = links["org_ref"].value_counts()
    for ref, n in counts.items():
        if n < min_links:
            continue
        add("O:" + ref, (ORG_NAME.get(ref) or ref)[:30], "Organisation",
            f"{ORG_NAME.get(ref) or ref} — {n} participations")
        for _, r in links[links["org_ref"] == ref].iterrows():
            net.add_edge("O:" + ref, "A:" + r["iati_identifier"],
                         color="#2a9d8f", width=1)

    if show_sectors:
        smeta = SEC.set_index("sector_key").to_dict("index")
        for _, r in CLS[CLS["iati_identifier"].isin(act_ids)].iterrows():
            s = smeta.get(r["sector_key"])
            if not s:
                continue
            add("S:" + r["sector_key"], (s["name"] or s["code"])[:26], "Sector",
                f'{s["name"]} ({r["sector_key"]})')
            net.add_edge("A:" + r["iati_identifier"], "S:" + r["sector_key"],
                         color="#cccccc", width=1)

    doc = net.generate_html()
    return (f'<iframe style="width:100%;height:660px;border:1px solid #ddd;'
            f'border-radius:8px" srcdoc="{html_mod.escape(doc)}"></iframe>')


# --------------------------------------------------------- questions tab --
def q_coverage():
    rows = [{"country": HOTSPOT_NAMES.get(c, c),
             "publisher": PUB_LABELS.get(a["publisher"], a["publisher"])}
            for _, a in ACT.iterrows() for c in a["countries"] if c]
    df = pd.DataFrame(rows)
    out = df.value_counts().unstack(fill_value=0).reset_index()
    return out.rename_axis(None, axis=1)


def q_shared_partners():
    m = PART.merge(ACT[["iati_identifier", "publisher"]], on="iati_identifier")
    g = m.groupby("org_ref").agg(publishers=("publisher", lambda s: sorted(set(s))),
                                 activities=("iati_identifier", "nunique")).reset_index()
    g = g[g["publishers"].apply(len) > 1].sort_values("activities", ascending=False)
    g["organisation"] = g["org_ref"].map(lambda r: ORG_NAME.get(r) or r)
    g["publishers"] = g["publishers"].apply(
        lambda ps: ", ".join(PUB_LABELS.get(p, p) for p in ps))
    return g[["organisation", "publishers", "activities"]].head(25)


def q_top_funders(country_label):
    code = country_label.split(" — ")[0]
    ids = {a["iati_identifier"] for _, a in ACT.iterrows() if code in a["countries"]}
    tx = TX[TX["iati_identifier"].isin(ids)].copy()
    prov = TXE[(TXE["edge"] == "PROVIDED_BY") & (TXE["tx_id"].isin(tx["tx_id"]))]
    m = prov.merge(tx[["tx_id", "value", "currency", "iati_identifier"]], on="tx_id")
    m["value"] = pd.to_numeric(m["value"], errors="coerce")
    g = (m.groupby(["org_ref", "currency"])
          .agg(total=("value", "sum"), transactions=("tx_id", "count"))
          .reset_index().sort_values("total", ascending=False))
    g["funder"] = g["org_ref"].map(lambda r: ORG_NAME.get(r) or r)
    g["total"] = g["total"].round(0)
    return g[["funder", "currency", "total", "transactions"]].head(25)


def q_sector_mix():
    m = CLS.merge(SEC, on="sector_key").merge(
        ACT[["iati_identifier", "publisher"]], on="iati_identifier")
    m = m[m["is_hunger"] == "true"]
    g = (m.groupby(["publisher", "name", "sector_key"]).size()
          .reset_index(name="activities")
          .sort_values(["publisher", "activities"], ascending=[True, False]))
    g["publisher"] = g["publisher"].map(lambda p: PUB_LABELS.get(p, p))
    return g.rename(columns={"name": "sector"})


def q_budgets():
    m = BUD.merge(ACT[["iati_identifier", "publisher"]], on="iati_identifier")
    m = m[m["status"] == "2"].copy()
    m["value"] = pd.to_numeric(m["value"], errors="coerce")
    m["year"] = m["period_start"].str[:4]
    g = (m.groupby(["publisher", "year", "currency"])["value"].sum()
          .round(0).reset_index(name="committed"))
    g["publisher"] = g["publisher"].map(lambda p: PUB_LABELS.get(p, p))
    return g.sort_values(["publisher", "year"])


def q_timeline():
    g = (ACT[ACT["year"].str.isdigit()]
         .groupby(["year", "publisher"]).size().unstack(fill_value=0).reset_index())
    g.columns = [PUB_LABELS.get(c, c) for c in g.columns]
    return g


QUESTIONS = {
    "Activities per hotspot per publisher": (q_coverage, False),
    "Shared partners across publishers": (q_shared_partners, False),
    "Top funders into a country": (q_top_funders, True),
    "Hunger sector mix per publisher": (q_sector_mix, False),
    "Committed budgets per year": (q_budgets, False),
    "Activities per start year": (q_timeline, False),
}

COUNTRY_CHOICES = [f"{c} — {n}" for c, n in sorted(HOTSPOT_NAMES.items(),
                                                   key=lambda kv: kv[1])]


def run_question(name, country):
    fn, needs_country = QUESTIONS[name]
    return fn(country) if needs_country else fn()


# --------------------------------------------------------- insights tab --
def insight_heatmap():
    rows = [{"country": HOTSPOT_NAMES.get(c, c),
             "publisher": PUB_LABELS.get(a["publisher"], a["publisher"])}
            for _, a in ACT.iterrows() for c in a["countries"] if c]
    piv = pd.DataFrame(rows).value_counts().unstack(fill_value=0)
    fig = px.imshow(piv, text_auto=True, aspect="auto",
                    color_continuous_scale="Greens",
                    labels=dict(x="publisher", y="", color="activities"),
                    title="Hunger-related activities per hotspot per publisher")
    fig.update_layout(height=520, coloraxis_showscale=False)
    return fig


def insight_sankey(country_label, currency):
    """Delivery chain for one hotspot: funders -> publisher -> partners.
    Funders come from incoming funds (type 1/11, provider-org); partners
    from disbursement receiver-orgs (type 3)."""
    code = country_label.split(" — ")[0]
    ids = {a["iati_identifier"] for _, a in ACT.iterrows() if code in a["countries"]}
    tx = TX[(TX["iati_identifier"].isin(ids)) & (TX["currency"] == currency)].copy()
    tx["value"] = pd.to_numeric(tx["value"], errors="coerce")
    tx = tx.dropna(subset=["value"])
    tx["publisher"] = tx["iati_identifier"].map(PUB2ACT).map(
        lambda p: PUB_LABELS.get(p, p))

    inc = tx[tx["type"].isin(["1", "11"])]
    fund = (TXE[TXE["edge"] == "PROVIDED_BY"]
            .merge(inc[["tx_id", "value", "publisher"]], on="tx_id")
            .groupby(["org_ref", "publisher"])["value"].sum()
            .reset_index().sort_values("value", ascending=False).head(14))
    out = tx[tx["type"] == "3"]
    part = (TXE[TXE["edge"] == "RECEIVED_BY"]
            .merge(out[["tx_id", "value", "publisher"]], on="tx_id")
            .groupby(["publisher", "org_ref"])["value"].sum()
            .reset_index().sort_values("value", ascending=False).head(14))
    if fund.empty and part.empty:
        return go.Figure().update_layout(
            title=f"No {currency} flows found for {country_label}")

    def nm(r):
        return (ORG_NAME.get(r) or r)[:26]
    funders = list(dict.fromkeys(fund["org_ref"]))
    pubs = list(dict.fromkeys(list(fund["publisher"]) + list(part["publisher"])))
    partners = list(dict.fromkeys(part["org_ref"]))
    labels = ([nm(r) for r in funders] + pubs + [nm(r) for r in partners])
    F, P = len(funders), len(pubs)
    src = ([funders.index(r) for r in fund["org_ref"]]
           + [F + pubs.index(p) for p in part["publisher"]])
    tgt = ([F + pubs.index(p) for p in fund["publisher"]]
           + [F + P + partners.index(r) for r in part["org_ref"]])
    val = list(fund["value"]) + list(part["value"])
    fig = go.Figure(go.Sankey(node=dict(label=labels, pad=12, thickness=14),
                              link=dict(source=src, target=tgt, value=val)))
    fig.update_layout(height=580, title=(
        f"{country_label.split(' — ')[1]}: funders → publisher → implementing "
        f"partners ({currency}; incoming funds / disbursements)"))
    return fig


def insight_timeline(currency):
    tx = TX[(TX["type"].isin(["3", "4"])) & (TX["currency"] == currency)].copy()
    tx["value"] = pd.to_numeric(tx["value"], errors="coerce")
    tx["year"] = tx["date"].str[:4]
    tx["publisher"] = tx["iati_identifier"].map(PUB2ACT)
    g = (tx.dropna(subset=["value"])
           .query("year >= '2010' and year <= '2026'")
           .groupby(["year", "publisher"])["value"].sum().reset_index())
    g["publisher"] = g["publisher"].map(lambda p: PUB_LABELS.get(p, p))
    fig = px.bar(g, x="year", y="value", color="publisher", barmode="group",
                 title=f"Disbursements + expenditure per year ({currency}), hotspot hunger activities")
    fig.update_layout(height=440)
    return fig


ABOUT = """
### About this demo
Knowledge graph of hunger-related IATI activities by **Oxfam GB, Oxfam
America and WFP** in the 13 **FAO-WFP Hunger Hotspots** (June-November 2026
outlook). Built from the [IATI Bulk Data Service](https://bulk-data.iatistandard.org/);
activities are kept when they target a hotspot country **and** carry
hunger-related sector coding (DAC / humanitarian cluster codes), with keyword
matching for publishers that use their own sector vocabularies (the
`match_basis` field on each activity records which).

**Caveats:** publisher coverage and coding practices differ (WFP: DAC-coded,
2018+; Oxfam GB: own sector vocabulary, 2006+); monetary values are not
currency-converted; sub-national hotspot areas are not yet matched.
"""

with gr.Blocks(title="IATI Hunger Hotspots Knowledge Graph") as demo:
    gr.Markdown("# IATI Hunger Hotspots Knowledge Graph\n"
                "Oxfam GB vs Oxfam America vs WFP — hunger-related activities "
                "in the 2026 Hunger Hotspots")
    with gr.Tab("Explore the graph"):
        with gr.Row():
            f_country = gr.Dropdown(COUNTRY_CHOICES, multiselect=True,
                                    label="Hotspot countries (empty = all)")
            f_pub = gr.Dropdown(list(PUB_LABELS.values()), multiselect=True,
                                label="Publishers (empty = all)")
            f_min = gr.Slider(1, 5, value=2, step=1,
                              label="Min. participations to show a partner org")
            f_sec = gr.Checkbox(label="Show sectors", value=False)
        f_focus = gr.Dropdown([""] + org_choices(), label="Focus on one organisation (ego view)", value="")
        btn = gr.Button("Draw graph", variant="primary")
        out_html = gr.HTML()
        btn.click(graph_html, [f_country, f_pub, f_min, f_sec, f_focus], out_html)
    with gr.Tab("Ask the graph"):
        q = gr.Dropdown(list(QUESTIONS), label="Question",
                        value="Activities per hotspot per publisher")
        q_country = gr.Dropdown(COUNTRY_CHOICES, label="Country (for funder question)",
                                value=COUNTRY_CHOICES[0])
        q_btn = gr.Button("Run", variant="primary")
        q_out = gr.Dataframe()
        q_btn.click(run_question, [q, q_country], q_out)
    with gr.Tab("Insights"):
        gr.Markdown("Pre-built analytical views over the full graph.")
        with gr.Row():
            i_country = gr.Dropdown(COUNTRY_CHOICES, label="Country (for funding flows)",
                                    value="YE — Yemen")
            i_cur = gr.Dropdown(["USD", "GBP"], label="Currency", value="USD")
        i_btn = gr.Button("Refresh insights", variant="primary")
        p1 = gr.Plot(label="Coverage heatmap")
        p2 = gr.Plot(label="Funding flows")
        p3 = gr.Plot(label="Funding over time")
        def _insights(c, cur):
            return insight_heatmap(), insight_sankey(c, cur), insight_timeline(cur)
        i_btn.click(_insights, [i_country, i_cur], [p1, p2, p3])
    with gr.Tab("About"):
        gr.Markdown(ABOUT)

if __name__ == "__main__":
    demo.launch(share=True)
