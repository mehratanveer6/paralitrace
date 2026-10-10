"""Strands agent that answers questions and drafts advisories from the model's output.

Built on the Strands Agents SDK (AWS open source). The agent never invents numbers: every
figure comes from a tool that reads the latest pipeline run.

The model behind it is picked from what is configured, in this order (PT_MODEL forces one):
  gemini     GEMINI_API_KEY, free at aistudio.google.com/apikey. GEMINI_MODEL picks the model,
             otherwise the first of GEMINI_MODELS that the key can use.
  anthropic  ANTHROPIC_API_KEY, needs `pip install 'strands-agents[anthropic]'`
  ollama     a local Ollama: OLLAMA_HOST, OLLAMA_MODEL (needs a tool-calling model)
  bedrock    Amazon Bedrock with your AWS credentials and AWS_REGION
"""
from __future__ import annotations

import json
import os

from strands import Agent, tool

from .config import OUTPUT_DIR, RECEPTORS, env
from .model.analysis import auto_budget, plan_interventions

SYSTEM_PROMPT = """You are ParaliTrace, an air-quality analyst for Punjab, Haryana and Delhi during
the crop-residue burning season. You help district officials, school principals and residents.

Rules:
- Use the tools for every number. Never invent figures, places or times.
- Call run_info first in a conversation. If the data label says SYNTHETIC, say plainly
  that the numbers come from demo data, not real observations. If it says Replay, the
  forecast is a real past day: give its date and speak about it in the past tense.
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
def intervention_plan(budget_fires: int = 0) -> dict:
    """Best fire clusters to stop burning tomorrow to protect the most people, given how many
    fire locations field teams or crop-residue machines can cover.

    Args:
        budget_fires: Number of fire locations teams can act on tomorrow. 0 sizes it to the day.
    """
    from .pipeline import load_trace
    trace = load_trace()
    budget = int(budget_fires) if budget_fires and int(budget_fires) > 0 else auto_budget(trace)
    plan = plan_interventions(trace, budget_fires=budget)
    plan["clusters"] = plan["clusters"][:12]
    return plan


TOOLS = [run_info, list_city_risks, city_forecast, smoke_sources, intervention_plan]


GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash")


class NoModelConfigured(RuntimeError):
    pass


def provider() -> str:
    forced = (env("PT_MODEL") or "").lower()
    if forced:
        return forced
    if env("GEMINI_API_KEY"):
        return "gemini"
    if env("ANTHROPIC_API_KEY"):
        return "anthropic"
    if env("OLLAMA_MODEL"):
        return "ollama"
    if env("AWS_ACCESS_KEY_ID") or env("AWS_PROFILE"):
        return "bedrock"
    raise NoModelConfigured("The assistant needs a model. Get a free Gemini key at aistudio.google.com/apikey, "
                            "put it in .env as GEMINI_API_KEY, and restart the server.")


# Amazon Nova on Bedrock needs no approval form; cross-region inference profiles first.
BEDROCK_MODELS = ("us.amazon.nova-pro-v1:0", "us.amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0")
MODEL_NAMES = {
    "us.amazon.nova-pro-v1:0": "Amazon Nova Pro", "amazon.nova-pro-v1:0": "Amazon Nova Pro",
    "us.amazon.nova-lite-v1:0": "Amazon Nova Lite",
}


def _gemini_models() -> list:
    if not env("GEMINI_API_KEY"):
        return []
    from strands.models.gemini import GeminiModel
    ids = [env("GEMINI_MODEL")] if env("GEMINI_MODEL") else list(GEMINI_MODELS)
    return [GeminiModel(client_args={"api_key": env("GEMINI_API_KEY")}, model_id=m, params={"temperature": 0.3})
            for m in ids]


def _bedrock_models() -> list:
    from strands.models.bedrock import BedrockModel
    ids = [env("BEDROCK_MODEL_ID")] if env("BEDROCK_MODEL_ID") else list(BEDROCK_MODELS)
    return [BedrockModel(model_id=m, region_name=env("AWS_REGION", "us-east-1"), temperature=0.3) for m in ids]


def candidates() -> list:
    """Model objects to try in order, each provider's alternatives after it. On AWS (PT_MODEL=bedrock)
    Bedrock comes first and Gemini, if a key is set, is the fallback when Bedrock is unavailable."""
    p = provider()
    if p == "gemini":
        return _gemini_models()
    if p == "anthropic":
        from strands.models.anthropic import AnthropicModel
        return [AnthropicModel(model_id=env("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=1500)]
    if p == "ollama":
        from strands.models.ollama import OllamaModel
        return [OllamaModel(env("OLLAMA_HOST", "http://localhost:11434"), model_id=env("OLLAMA_MODEL", "qwen2.5:7b"))]
    return _bedrock_models() + _gemini_models()


def model_label(m) -> str:
    """Human-readable 'which model answered', shown beside each answer."""
    mid = (getattr(m, "config", None) or {}).get("model_id", "") if not isinstance(m, str) else m
    cls = type(m).__name__
    if cls == "BedrockModel":
        return f"{MODEL_NAMES.get(mid, mid)} on Amazon Bedrock"
    if cls == "GeminiModel":
        return f"{mid} (Gemini API)"
    return str(mid or cls)


def working_model_label() -> str | None:
    return model_label(_working[0]) if _working else None


_working: list = []   # the model that last answered, reused for later questions


def _model_unavailable(e: Exception) -> bool:
    """Errors that mean 'try the next model', not 'the question failed': missing access, unknown model id,
    no credentials, quota."""
    msg = f"{type(e).__name__} {e}".lower()
    return any(k in msg for k in ("not found", "404", "not supported", "permission", "403", "quota", "429",
                                  "accessdenied", "access denied", "not allowed", "not authorized",
                                  "validationexception", "resourcenotfound", "credentials", "unrecognizedclient",
                                  "invalid model", "model identifier"))


def tool_trace(agent) -> list[dict]:
    """The tool calls Strands made while answering, in order: name and arguments."""
    calls = []
    for msg in getattr(agent, "messages", []) or []:
        if msg.get("role") != "assistant":
            continue
        for block in msg.get("content", []):
            use = block.get("toolUse") if isinstance(block, dict) else None
            if use:
                calls.append({"name": use.get("name"), "input": use.get("input") or {}})
    return calls


def ask(question: str) -> str:
    return ask_with_trace(question)[0]


def ask_with_trace(question: str) -> tuple[str, list[dict]]:
    """Fresh agent per question so conversations don't leak between users."""
    models = _working or candidates()
    last: Exception | None = None
    for m in models:
        try:
            agent = Agent(model=m, tools=TOOLS, system_prompt=SYSTEM_PROMPT, callback_handler=None)
            answer = str(agent(question)).strip()
            _working[:] = [m]
            return answer, tool_trace(agent)
        except Exception as e:
            last = e
            if not _model_unavailable(e):
                raise
    raise RuntimeError(f"No configured model could answer: {last}")


if __name__ == "__main__":
    import sys
    print(ask(" ".join(sys.argv[1:]) or "Which cities face the worst smoke tomorrow, and why?"))
