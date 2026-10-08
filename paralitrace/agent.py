"""Strands agent that answers questions and drafts advisories from the model's output.

The agent never invents numbers: every figure comes from a tool that reads the
latest pipeline run. Model provider is chosen with PT_MODEL:
  bedrock (default)  AWS Bedrock, uses your AWS credentials and AWS_REGION
  ollama             local model, set OLLAMA_HOST and OLLAMA_MODEL (needs a tool-calling model)
  anthropic          ANTHROPIC_API_KEY, needs `pip install 'strands-agents[anthropic]'`
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from strands import Agent, tool

from .config import OUTPUT_DIR, RECEPTORS, env
from .model.analysis import plan_interventions

SYSTEM_PROMPT = """You are ParaliTrace, an air-quality analyst for Punjab, Haryana and Delhi during
the crop-residue burning season. You help district officials, school principals and residents.

Rules:
- Use the tools for every number. Never invent figures, places or times.
- Call run_info first in a conversation. If the data label says SYNTHETIC, say plainly
  that the numbers come from demo data, not real observations.
- The smoke index is relative and not yet calibrated to PM2.5. Describe it with the
  risk band (low, moderate, high, severe) and the timing, not as a concentration.
- Smoke already emitted cannot be prevented. Only tomorrow's projected burning can.
- For school advisories: say when to move assemblies and sports indoors, keep it short
  and practical, and give the forecast window in IST. Recommend checking the official
  CPCB AQI before acting. Do not give medical diagnoses.
- When asked for Punjabi or Hindi, write in that language and script (Gurmukhi or
  Devanagari), keeping numbers and times in digits.
- Be concise. Lead with the answer."""


def _load() -> dict:
    with open(os.path.join(OUTPUT_DIR, "latest.json")) as f:
        return json.load(f)


def _city(data: dict, name: str) -> dict | None:
    key = name.strip().lower()
    for c in data["cities"]:
        if key in (c["id"], c["name"].lower()):
            return c
    return None


@tool
def run_info() -> dict:
    """Metadata about the latest model run: data source label, generation time, fire counts."""
    return _load()["meta"]


@tool
def list_city_risks() -> list[dict]:
    """Every covered city with its smoke risk for the next 24 h and the 24 h after, worst first."""
    cities = _load()["cities"]
    rows = [{"city": c["name"], "today_risk": c["day1_risk"], "tomorrow_risk": c["day2_risk"],
             "peak_time_ist": c["peak_time_ist"]} for c in cities]
    order = {"severe": 0, "high": 1, "moderate": 2, "low": 3}
    return sorted(rows, key=lambda r: (order[r["today_risk"]], order[r["tomorrow_risk"]]))


@tool
def city_forecast(city: str) -> dict:
    """48-hour smoke forecast for one city: risk bands, peak time, and the 6-hourly trend.

    Args:
        city: City name, for example "Mohali" or "Delhi".
    """
    c = _city(_load(), city)
    if not c:
        return {"error": f"Unknown city. Covered: {', '.join(r.name for r in RECEPTORS)}"}
    h = c["hourly_index"]
    return {
        "city": c["name"], "next_24h_risk": c["day1_risk"], "following_24h_risk": c["day2_risk"],
        "peak_risk": c["peak_risk"], "peak_time_ist": c["peak_time_ist"],
        "six_hourly_index": [round(sum(h[i:i + 6]) / 6, 1) for i in range(0, len(h), 6)],
        "preventable_share_pct": c["preventable_pct"],
    }


@tool
def smoke_sources(city: str) -> dict:
    """Which burning clusters send the most smoke to a city, with share and distance.

    Args:
        city: City name, for example "Ludhiana".
    """
    c = _city(_load(), city)
    if not c:
        return {"error": "Unknown city"}
    return {"city": c["name"], "top_sources": c["top_sources"],
            "preventable_share_pct": c["preventable_pct"]}


@tool
def intervention_plan(budget_fires: int = 150) -> dict:
    """Best fire clusters to stop burning tomorrow to protect the most people, given how many
    fire locations field teams or crop-residue machines can cover.

    Args:
        budget_fires: Number of fire detections the state can act on tomorrow.
    """
    from .pipeline import load_trace
    plan = plan_interventions(load_trace(), budget_fires=max(1, int(budget_fires)))
    plan["clusters"] = plan["clusters"][:12]
    return plan


TOOLS = [run_info, list_city_risks, city_forecast, smoke_sources, intervention_plan]


def _model():
    provider = (env("PT_MODEL", "bedrock") or "bedrock").lower()
    if provider == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(env("OLLAMA_HOST", "http://localhost:11434"),
                           model_id=env("OLLAMA_MODEL", "qwen2.5:7b"))
    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel
        return AnthropicModel(model_id=env("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=1500)
    from strands.models.bedrock import BedrockModel
    kwargs = {"region_name": env("AWS_REGION", "us-east-1")}
    if env("BEDROCK_MODEL_ID"):
        kwargs["model_id"] = env("BEDROCK_MODEL_ID")
    return BedrockModel(**kwargs)


@lru_cache(maxsize=1)
def _model_cached():
    return _model()


def ask(question: str) -> str:
    """Fresh agent per question so conversations don't leak between users."""
    agent = Agent(model=_model_cached(), tools=TOOLS, system_prompt=SYSTEM_PROMPT,
                  callback_handler=None)
    return str(agent(question)).strip()


if __name__ == "__main__":
    import sys
    print(ask(" ".join(sys.argv[1:]) or "Which cities face the worst smoke tomorrow, and why?"))
