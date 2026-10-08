"""FastAPI server: serves the map and the model's output.

    uvicorn app:app --reload
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from paralitrace.config import OUTPUT_DIR
from paralitrace.model.analysis import plan_interventions
from paralitrace.pipeline import load_trace, run

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
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
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
