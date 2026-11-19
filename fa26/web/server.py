"""IATI Atlas web service: the page, its library data, and the question-answering API.

    conda activate iati
    pip install -r fa26/web/requirements.txt
    python fa26/web/build_site.py                  # regenerate static/data.json from the repository
    python fa26/web/server.py                      # http://127.0.0.1:8080

Endpoints
  GET  /              the page (static/index.html)
  GET  /data.json     library data built by build_site.py
  GET  /api/meta      dataset label, open models and routes, compare view status
  POST /api/ask       {"question": str, "model": "default", "route": "auto"} -> {"answer", "views"}
  GET  /api/health    liveness

Environment (read by src/ask.py from fa26/.env, never logged or returned):
  NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD, model API keys
  IATI_ASK_MODEL   model for "default" (default anthropic/claude-sonnet-4-6)
  IATI_GRAPH_DIR   CSV folder whose rows the evidence ids refer to; must match the data loaded in Neo4j
                   (default fa26/benchmark/snapshot)
  IATI_GRAPH_LABEL label shown on the page for that data (default "benchmark snapshot")
  PORT             listen port (default 8080)
  IATI_BASIC_AUTH  optional "user:password"; when set, every route except /api/health asks for it (browser login)
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import base64
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

FA26 = Path(__file__).resolve().parents[1]
WEB = FA26 / "web"
STATIC = WEB / "static"
for p in (WEB, FA26 / "src"):
    sys.path.insert(0, str(p))

from views import build_views  # noqa: E402

GRAPH_DIR = Path(os.environ.get("IATI_GRAPH_DIR") or FA26 / "benchmark" / "snapshot")
GRAPH_LABEL = os.environ.get("IATI_GRAPH_LABEL", "benchmark snapshot")
DEFAULT_MODEL = os.environ.get("IATI_ASK_MODEL", "anthropic/claude-sonnet-4-6")
OPEN_MODELS = ("default",)   # the compare view (other models, other routes) is locked
MAX_QUESTION = 500

app = FastAPI(title="IATI Atlas", docs_url=None, redoc_url=None)
_engine = None
_lock = threading.Lock()
_AUTH = os.environ.get("IATI_BASIC_AUTH") or ""


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not _AUTH or request.url.path == "/api/health":
        return await call_next(request)
    sent = request.headers.get("authorization", "")
    ok = False
    if sent.startswith("Basic "):
        try:
            ok = secrets.compare_digest(base64.b64decode(sent[6:]).decode("utf-8"), _AUTH)
        except Exception:
            ok = False
    if not ok:
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="IATI Atlas"'})
    return await call_next(request)


def engine():
    """One shared Engine, created on first use so the page loads even when Neo4j or the model is unreachable."""
    global _engine
    with _lock:
        if _engine is None:
            from ask import Engine
            _engine = Engine(model=DEFAULT_MODEL, snapshot_dir=GRAPH_DIR)
        return _engine


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=MAX_QUESTION)
    model: str = "default"
    route: str = "auto"


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    from ask import ROUTES
    rows = sum(1 for _ in (GRAPH_DIR / "nodes_activities.csv").open(encoding="utf-8")) - 1 if (GRAPH_DIR / "nodes_activities.csv").exists() else None
    return {"dataset": {"label": GRAPH_LABEL, "activities": rows}, "models": list(OPEN_MODELS), "routes": list(ROUTES),
            "compare": {"locked": True}}


@app.post("/api/ask")
def ask(body: AskIn):
    if body.model not in OPEN_MODELS:
        raise HTTPException(423, f"model {body.model!r} is locked; open models: {list(OPEN_MODELS)}")
    try:
        eng = engine()
    except Exception as e:  # missing credentials or unreachable database: report the kind, never the values
        raise HTTPException(503, f"engine unavailable: {type(e).__name__}")
    try:
        answer = eng.ask(body.question.strip(), route=body.route)
    except ValueError as e:
        raise HTTPException(423, str(e))
    rows = eng.evidence_rows(answer, limit=None)
    views = build_views(answer, rows, eng._table)
    answer["facts"] = {k: {"value": f["value"], "evidence_n": len(f["evidence"])} for k, f in answer["facts"].items()}
    return JSONResponse({"answer": answer, "views": views})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/", StaticFiles(directory=STATIC), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8080")))
