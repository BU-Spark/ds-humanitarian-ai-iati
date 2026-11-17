"""Minimal Ask tab: one question in, layered answer out (answer, how it was produced, evidence rows).

    conda activate iati && pip install gradio
    python fa26/ask_app.py                      # model from IATI_ASK_MODEL, default anthropic/claude-sonnet-4-6
    IATI_ASK_MODEL=zai/glm-5.3 python fa26/ask_app.py

Reads fa26/.env for Neo4j and the model key. Read-only; nothing here writes to the graph.
"""
import json
import os
import sys
from pathlib import Path

import gradio as gr
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from ask import Engine, DEFAULT_MODEL  # noqa: E402

_ENGINE = None


def engine():
    """Connect on the first question, not at import, so the page still opens when Aura is paused."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine(model=os.environ.get("IATI_ASK_MODEL", DEFAULT_MODEL))
    return _ENGINE

EXAMPLES = ["How many WFP activities target Yemen?",
            "What is the total of positive WFP incoming-fund transactions in USD?",
            "Which organisations work with both Oxfam GB and Oxfam America?",
            "How much did Oxfam give?",
            "How many people were lifted out of hunger by these projects?"]


def answer(question):
    try:
        eng = engine()
        out = eng.ask(question)
    except Exception as e:  # paused Aura, missing key, network: show it instead of a dead page
        msg = f"**Backend unavailable** ({type(e).__name__}): {str(e)[:300]}\n\nIf this mentions DNS / 9391175d.databases.neo4j.io, the Aura free instance is paused — resume it in the Neo4j console and ask again."
        return msg, "{}", pd.DataFrame(columns=["id"]), "{}"
    if out["status"] == "answer":
        lines = [f"**{k}**: {v['value']}  ({len(v['evidence'])} source rows)" for k, v in out["facts"].items()] or ["(no facts)"]
        head = "\n".join(lines)
    elif out["status"] == "clarify":
        head = f"**Needs clarification** ({', '.join(out['reasons'])}): {out.get('explanation') or ''}"
    else:
        head = f"**Cannot answer from this snapshot** ({', '.join(out['reasons'])}): {out.get('explanation') or ''}"
    how = {k: out[k] for k in ("model", "tool", "args", "cypher", "retries", "error", "latency_ms") if out.get(k) not in (None, "", {})}
    rows = eng.evidence_rows(out)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["id"])
    return head, json.dumps(how, indent=1), df, json.dumps({k: out[k] for k in ("id", "status", "facts", "reasons")}, indent=1)


with gr.Blocks(title="IATI Ask") as demo:
    gr.Markdown("## Ask the IATI hunger-response graph\nAnswers come from fixed query templates or read-only Cypher on one pinned snapshot; every number cites its source rows.")
    q = gr.Textbox(label="Question", placeholder="How many Oxfam GB activities in Somalia are completed?")
    gr.Examples(EXAMPLES, inputs=q)
    btn = gr.Button("Ask", variant="primary")
    ans = gr.Markdown(label="Answer")
    with gr.Accordion("How it was produced", open=False):
        how = gr.Code(language="json", label="tool, arguments, query, latency")
    with gr.Accordion("Evidence rows (first 50)", open=False):
        ev = gr.Dataframe(label="source rows", wrap=True)
    with gr.Accordion("Raw answer (benchmark format)", open=False):
        raw = gr.Code(language="json")
    btn.click(answer, inputs=q, outputs=[ans, how, ev, raw])
    q.submit(answer, inputs=q, outputs=[ans, how, ev, raw])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=int(os.environ.get("IATI_ASK_PORT", "7861")))
