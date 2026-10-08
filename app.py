"""FastAPI server: serves the built React app and the model's output.

    cd frontend && npm install && npm run build && cd ..
    uvicorn app:app --reload
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from paralitrace.config import OUTPUT_DIR
from paralitrace.model.analysis import plan_interventions
from paralitrace.pipeline import load_trace, run

DIST_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")  # built React app
app = FastAPI(title="ParaliTrace")


class RunRequest(BaseModel):
    mode: str = Field("synthetic", pattern="^(synthetic|live)$")
    budget: int = Field(150, ge=1, le=5000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


def _latest() -> dict:
    path = os.path.join(OUTPUT_DIR, "latest.json")
    if not os.path.exists(path):
        run("synthetic")
    with open(path) as f:
        return json.load(f)


@app.get("/api/latest")
def latest():
    return _latest()


@app.post("/api/run")
def run_pipeline(req: RunRequest):
    try:
        return run(req.mode, req.budget)["meta"]
    except SystemExit as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # upstream API failures
        raise HTTPException(502, f"Pipeline failed: {e}")


@app.get("/api/plan")
def plan(budget: int = 150):
    _latest()
    return plan_interventions(load_trace(), budget_fires=max(1, min(budget, 5000)))


@app.get("/api/backtest")
def backtest():
    """Season replay results written by the backtest (schema: Backtest in frontend/src/types.ts)."""
    path = os.path.join(OUTPUT_DIR, "backtest.json")
    if not os.path.exists(path):
        raise HTTPException(404, "No backtest has been run yet")
    with open(path) as f:
        return json.load(f)


@app.post("/api/ask")
def ask(req: AskRequest):
    _latest()
    try:
        from paralitrace.agent import ask as agent_ask
        return {"answer": agent_ask(req.question)}
    except Exception as e:
        raise HTTPException(503, f"The assistant is unavailable: {type(e).__name__}: {e}")


@app.get("/")
def index():
    page = os.path.join(DIST_DIR, "index.html")
    if not os.path.exists(page):
        return HTMLResponse("<p>Frontend not built. Run <code>npm install</code> and <code>npm run build</code> "
                            "inside <code>frontend/</code>, then reload.</p>", status_code=503)
    return FileResponse(page)


@app.get("/favicon.svg")
def favicon():
    return FileResponse(os.path.join(DIST_DIR, "favicon.svg"), media_type="image/svg+xml")


if os.path.isdir(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
