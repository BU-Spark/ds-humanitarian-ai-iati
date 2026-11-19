"""Dashboard views for one answer, computed from the evidence rows it cites.

Every chart on the answer dashboard is an aggregation of the rows in the answer's evidence list, so the
dashboard never shows a number that the engine did not cite. Money is summed with Decimal from the CSV
strings; currencies are never mixed in one series.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

PUBLISHER_NAMES = {"oxfamgb": "Oxfam GB", "oxfamus": "Oxfam America", "wfp": "WFP"}
TX_TYPE_NAMES = {"1": "Incoming funds", "2": "Outgoing commitment", "3": "Disbursement", "4": "Expenditure"}
TOP = 6          # categories kept per breakdown before the rest is grouped as "Other"
GRAPH_ACTS = 12  # activities drawn in the evidence subgraph
FLOW_TOP = 4     # programmes and countries kept in the flow before the rest is grouped
ROWS_MAX = 300   # evidence rows sent to the page


def _dec(s) -> Decimal | None:
    try:
        return Decimal(str(s))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _programme(title: str) -> str:
    return re.sub(r"\s*-\s*[A-Z]{2}$", "", (title or "").strip()) or "(untitled)"


def _top(d: dict, n: int = TOP) -> list[dict]:
    items = sorted(d.items(), key=lambda kv: -float(kv[1]))
    head, tail = items[:n], items[n:]
    out = [{"key": k, "value": float(v)} for k, v in head]
    if tail:
        out.append({"key": "Other", "value": float(sum(v for _, v in tail)), "n": len(tail)})
    return out



def _sample_acts(acts, weight, cname, n=None):
    """Activities drawn in the subgraph: heaviest first, but spread across publishers and countries.

    Every publisher gets its heaviest activity first; the remaining slots go round-robin over countries
    (ordered by their total weight), so a count answer with equal weights does not show 12 rows of one country."""
    n = n or GRAPH_ACTS
    order = sorted(acts, key=lambda a: (-weight.get(a["iati_identifier"], 0), a["iati_identifier"]))
    picked, seen = [], set()
    for a in order:                                    # one per publisher
        if a["publisher"] not in {x["publisher"] for x in picked}:
            picked.append(a); seen.add(a["iati_identifier"])
    by_c, c_tot = defaultdict(list), defaultdict(float)
    for a in order:
        c = cname(a); c_tot[c] += float(weight.get(a["iati_identifier"], 0) or 1)
        if a["iati_identifier"] not in seen:
            by_c[c].append(a)
    queues = [by_c[c] for c in sorted(by_c, key=lambda c: -c_tot[c])]
    while len(picked) < n and any(queues):
        for q in queues:
            if q and len(picked) < n:
                picked.append(q.pop(0))
    return picked[:n]

def build_views(answer: dict, ev_rows: list[dict], table) -> dict:
    """answer: Engine.ask() output. ev_rows: Engine.evidence_rows(answer, limit=None). table(name) -> list of CSV dicts."""
    countries = {r["code"]: r["name"] for r in table("nodes_countries.csv")}
    acts_all = {r["iati_identifier"]: r for r in table("nodes_activities.csv")}
    by_table = defaultdict(list)
    for r in ev_rows:
        by_table[r["table"]].append(r)
    txs = by_table.get("nodes_transactions.csv", [])
    act_ids = {r["iati_identifier"] for r in by_table.get("nodes_activities.csv", [])} | {t["iati_identifier"] for t in txs}
    acts = [acts_all[a] for a in sorted(act_ids) if a in acts_all]

    def cname(a):
        c = (a or {}).get("hotspot_countries") or ""
        return countries.get(c, c) or "(no country)"

    facts = [{"key": k, "value": f["value"], "evidence_n": len(f.get("evidence", []))} for k, f in (answer.get("facts") or {}).items()]
    manifest = sorted({e[len("manifest:"):] for f in (answer.get("facts") or {}).values()
                       for e in f.get("evidence", []) if isinstance(e, str) and e.startswith("manifest:")})
    views = {"status": answer.get("status"), "facts": facts, "manifest_scope": manifest,
             "evidence_by_table": {k: len(v) for k, v in sorted(by_table.items())},
             "kpis": {"evidence": len(ev_rows), "activities": len(acts), "transactions": len(txs),
                      "countries": len({cname(a) for a in acts}), "publishers": len({a["publisher"] for a in acts})},
             "measure": None, "currency": None, "breakdowns": {}, "flow": None, "graph": None, "rows": [], "reconcile": None}

    if txs:
        cur_n = defaultdict(int)
        for t in txs:
            cur_n[t["currency"] or "(none)"] += 1
        cur = max(cur_n, key=cur_n.get)
        tx = [t for t in txs if (t["currency"] or "(none)") == cur and _dec(t["value"]) is not None]
        views.update(measure="money", currency=cur, other_currencies={k: v for k, v in cur_n.items() if k != cur})
        by_c, by_y, by_ty, by_p, val_act = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
        flow = defaultdict(Decimal)
        for t in tx:
            v = _dec(t["value"]); a = acts_all.get(t["iati_identifier"], {})
            pub = PUBLISHER_NAMES.get(a.get("publisher"), a.get("publisher") or "?")
            by_c[cname(a)] += v; by_y[(t["date"] or "")[:4] or "(no date)"] += v
            by_ty[TX_TYPE_NAMES.get(t["type"], t["type"])] += v; by_p[pub] += v; val_act[t["iati_identifier"]] += v
            flow[(pub, _programme(a.get("title")), cname(a))] += v
        total = sum(by_c.values(), Decimal(0))
        views["breakdowns"] = {"country": _top(by_c), "year": [{"key": k, "value": float(v)} for k, v in sorted(by_y.items())],
                               "type": _top(by_ty), "publisher": _top(by_p)}
        views["total"] = float(total)
        if len(facts) == 1:
            f = _dec(facts[0]["value"])
            views["reconcile"] = {"fact": facts[0]["value"], "sum_of_rows": str(total), "match": f is not None and f == total}
        weight = {a: float(v) for a, v in val_act.items()}
    else:
        views["measure"] = "count"
        by_c, by_y, by_p, by_s = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
        flow = defaultdict(int)
        for a in acts:
            pub = PUBLISHER_NAMES.get(a["publisher"], a["publisher"])
            yr = (a.get("start_actual") or a.get("start_planned") or "")[:4] or "(no date)"
            by_c[cname(a)] += 1; by_y[yr] += 1; by_p[pub] += 1; by_s[a.get("status") or "(none)"] += 1
            flow[(pub, _programme(a.get("title")), cname(a))] += 1
        views["breakdowns"] = {"country": _top(by_c), "year": [{"key": k, "value": v} for k, v in sorted(by_y.items())],
                               "publisher": _top(by_p), "status": _top(by_s)}
        weight = {a["iati_identifier"]: 1.0 for a in acts}

    if acts:
        # flow: publisher -> programme -> country, programmes and countries capped with "Other"
        prog_tot, c_tot = defaultdict(float), defaultdict(float)
        for (p, g, c), v in flow.items():
            prog_tot[g] += float(v); c_tot[c] += float(v)
        keep_g = {k for k, _ in sorted(prog_tot.items(), key=lambda kv: -kv[1])[:FLOW_TOP]}
        keep_c = {k for k, _ in sorted(c_tot.items(), key=lambda kv: -kv[1])[:TOP]}
        links = defaultdict(float)
        for (p, g, c), v in flow.items():
            g2 = g if g in keep_g else "Other programmes"; c2 = c if c in keep_c else "Other countries"
            links[("p:" + p, "g:" + g2)] += float(v); links[("g:" + g2, "c:" + c2)] += float(v)
        views["flow"] = {"links": [{"source": s, "target": t, "value": v} for (s, t), v in links.items() if v]}
        # graph: publishers -> top activities -> countries
        top_acts = _sample_acts(acts, weight, cname)
        views["graph"] = {"activities": [{"id": a["iati_identifier"], "title": a.get("title", ""), "programme": _programme(a.get("title")),
                                          "publisher": PUBLISHER_NAMES.get(a["publisher"], a["publisher"]), "country": cname(a),
                                          "weight": weight.get(a["iati_identifier"], 0)} for a in top_acts],
                          "hidden": max(len(acts) - len(top_acts), 0)}

    rows = []
    for r in ev_rows[:ROWS_MAX]:
        t = r["table"]
        if t == "nodes_transactions.csv":
            a = acts_all.get(r["iati_identifier"], {})
            rows.append({"id": r["id"], "kind": "transaction", "label": TX_TYPE_NAMES.get(r["type"], r["type"]), "country": cname(a),
                         "date": r["date"], "value": r["value"], "currency": r["currency"]})
        elif t == "nodes_activities.csv":
            rows.append({"id": r["id"], "kind": "activity", "label": r.get("title", ""), "country": cname(r),
                         "date": r.get("start_actual") or r.get("start_planned") or "", "value": None, "currency": None})
        else:
            label = r.get("name") or r.get("iati_identifier") or r.get("org_ref") or ""
            rows.append({"id": r["id"], "kind": t.replace(".csv", ""), "label": label, "country": "", "date": "", "value": None, "currency": None})
    views["rows"] = rows
    views["rows_total"] = len(ev_rows)
    # layout: a full dashboard whenever there is more than one number or any activity / transaction row to break
    # down; otherwise a single poster (one number, a zero result, a clarification or an abstention)
    full = answer.get("status") == "answer" and not answer.get("error") and (len(facts) > 1 or bool(acts) or bool(txs))
    views["layout"] = "dashboard" if full else "poster"
    return views
