"""Fill the submission text and video lines with the numbers from the latest runs.

    py -m paralitrace.report

Reads output/latest.json (the forecast on screen) and output/backtest.json (season replay) and writes
output/SUBMISSION.md with three parts: the answer to the form's "How did you use AWS" question, the
project writeup, and the video lines. Missing data is called out, never invented.
"""
from __future__ import annotations

import json
import os

from .config import OUTPUT_DIR

REPO = "https://github.com/mehratanveer6/paralitrace"


def _load(name: str) -> dict | None:
    path = os.path.join(OUTPUT_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _methods(bt: dict | None) -> dict:
    h = (bt or {}).get("heldout") or {}
    return {m["key"]: m for m in h.get("methods", [])}


def proof_text(bt: dict | None) -> tuple[str, str]:
    """(writeup paragraph, video line) for the backtest."""
    if not bt:
        return ("A backtest module replays a past season against ground-monitor PM2.5 "
                "(`py -m paralitrace.backtest`). (Not run yet.)",
                "(Backtest not run yet. Skip this segment.)")
    s, h, m = bt["summary"], bt.get("heldout"), _methods(bt)
    parts = [f"I replayed {bt['season']} across {len(bt['cities'])} cities: every day forecast 24 hours ahead from "
             f"the previous day's fires, then checked against PM2.5 from ground monitors."]
    if s.get("onset_days"):
        parts.append(f"From fires and wind alone it saw {s['onsets_caught']} of {s['onset_days']} smoky spells coming "
                     f"a day before they started, which simply repeating yesterday's reading can never do. Across all "
                     f"{s['spike_days']} spike days it caught {s['hit_rate_pct']}%, against {s['baseline_hit_rate_pct']}% "
                     f"for repeating yesterday.")
    video = ""
    if h and m:
        cal, base, nos = m["calibrated"], m["persistence"], m["calibrated_no_smoke"]
        parts.append(f"Calibrated with a two-term regression trained on {h['train']} and scored only on {h['test']}, "
                     f"which it never saw, the forecast caught {cal['caught']} of {h['spike_days']} spike days "
                     f"({cal['onsets_caught']} of {h['onset_days']} spell starts) against {base['caught']} "
                     f"({base['onsets_caught']} spell starts) for repeating yesterday, with {cal['false_alarm_pct']}% false "
                     f"alarms against {base['false_alarm_pct']}%. Its average daily PM2.5 error was {cal['mae']} µg/m³, "
                     f"against {base['mae']} for repeating yesterday and {nos['mae']} for the same regression without the "
                     f"smoke model.")
        video = (f"\"Does it work? I replayed {bt['season']} against ground monitors, trained on {h['train']} and "
                 f"tested on {h['test']}. It caught {cal['caught']} of {h['spike_days']} smoke-spike days, against "
                 f"{base['caught']} for just repeating yesterday's reading, and it saw {cal['onsets_caught']} smoky "
                 f"spells coming before they started.\"")
    elif s.get("onset_days"):
        video = (f"\"Does it work? I replayed {bt['season']} against ground monitors. It saw {s['onsets_caught']} of "
                 f"{s['onset_days']} smoky spells coming a day ahead, which repeating yesterday's reading never can.\"")
    return " ".join(parts), video


def aws_answer() -> str:
    return f"""ParaliTrace forecasts where crop-residue (stubble) smoke from Punjab and Haryana will drift over the next
48 hours, which fields each city's smoke comes from, and which fires field teams should stop tomorrow to
protect the most people. It traces NASA satellite fire detections through wind forecasts with a particle model,
and an AI assistant explains the forecast and writes school advisories in English, Hindi or Punjabi.

AWS open source: Strands Agents SDK. The assistant is a Strands Agent with five @tool functions over the
forecast (run_info, list_city_risks, city_forecast, smoke_sources, intervention_plan). Strands runs the
model-driven agent loop, generates the tool schemas from the Python type hints and docstrings, executes the
tool calls and feeds the results back, so every number the assistant quotes comes from the model output and
none is invented. The app shows each tool call Strands makes beside the answer. Strands' model-provider layer
keeps the assistant portable: it runs on Gemini today and switches to Amazon Bedrock with one setting
(PT_MODEL=bedrock), with fallback across models built on top.

AWS services: Not used in production for this submission. My AWS account's student credits weren't approved
before the deadline, so I built entirely on the AWS open-source path the rules allow. The repository includes
a ready Amazon EC2 deployment (deploy/ec2-user-data.sh: installs the app, runs it as a service and refreshes
live NASA fires every hour) and Amazon Bedrock support through Strands, so moving onto AWS services is a
deployment step, not a rewrite.

Code: {REPO}"""


def build(latest: dict | None, bt: dict | None) -> str:
    plan = (latest or {}).get("plan") or {}
    meta = (latest or {}).get("meta") or {}
    cf = (latest or {}).get("counterfactual") or {}
    real = meta.get("mode") in ("live", "replay")
    replay_day = meta.get("data_label", "").split(":")[0].replace("Replay of ", "") if meta.get("mode") == "replay" else ""
    top = [c for c in cf.get("cities", []) if c["reduction_pct"] >= 1]

    if plan:
        when = f"On the replayed day ({replay_day})" if replay_day else "On the forecast in the demo"
        plan_line = (f"{when}, with {plan['budget_fires']} fire locations it avoids "
                     f"{plan['exposure_avoided_pct_of_preventable']}% of tomorrow's preventable smoke exposure, against "
                     f"{plan['naive_biggest_fires_pct_of_preventable']}% for sending the same teams to the biggest fires.")
        if top:
            plan_line += (" A before-and-after map reruns the same forecast with those fires stopped: "
                          + ", ".join(f"{c['name']} {round(c['reduction_pct'])}% less smoke" for c in top[:3]) + ".")
        if not real:
            plan_line += " (These numbers come from demo data; rerun with real data before submitting.)"
    else:
        plan_line = "(Run the pipeline to fill in the planner's numbers.)"

    proof, video_proof = proof_text(bt)

    writeup = f"""# ParaliTrace: follow the stubble smoke, stop the right fires

**Track:** Air
**Repository:** {REPO}

## The problem

Every October and November, paddy-stubble fires across Punjab and Haryana send smoke over cities from
Amritsar to Delhi. Satellites already see every fire. What district officials and school principals don't get
is an answer to three questions, early enough to act on: which towns will this smoke reach, and when? Which
fields is my city's smoke coming from? With limited field teams and crop-residue machines, which fires should
we stop tomorrow to protect the most people?

## What I built

- **Smoke tracer.** Each ~10 km cluster of NASA VIIRS fire detections releases particles in proportion to its
  fire radiative power. They drift with hourly winds, spread with turbulence and settle out over about two days,
  giving a 48-hour smoke forecast for 16 cities across Punjab, Haryana and Delhi.
- **Attribution.** Every particle remembers its source, so each city's smoke splits exactly into contributions
  from named districts.
- **Planner.** Smoke already in the air can't be recalled, but fields expected to burn tomorrow can be reached.
  The planner ranks them by how many people their smoke would reach, within the number of locations teams can
  cover. {plan_line}
- **Assistant.** A Strands Agents SDK agent with five tools over the forecast answers questions and drafts school
  advisories in English, Hindi or Punjabi. The app shows every tool call it makes, and it can only quote numbers
  the model produced.
- **Proof.** {proof}
- **Live and replay.** One click pulls today's NASA fires and wind forecasts; any past day can be replayed with
  archived fires and reanalysis winds.

## Data

NASA FIRMS VIIRS active fires (near-real-time and archive), Open-Meteo wind forecasts and ERA5 reanalysis,
OpenAQ ground-monitor PM2.5, OpenStreetMap and Esri basemaps.

## Limits

The tracer is a simplified two-dimensional model, not a research model such as HYSPLIT. The smoke index is
relative; the calibration step turns it into a PM2.5 forecast. Tomorrow's burning is assumed to resemble
today's. The backtest uses reanalysis winds in place of the forecasts available at the time.

## Built with

Python, NumPy, pandas, FastAPI, Strands Agents SDK, React, TypeScript, Vite, Leaflet, with automated tests.
**AI coding tools used:** Claude (Anthropic), for code, tests and drafting.
"""

    opening = (f"This is {replay_day}, replayed with real NASA fire detections." if replay_day
               else "This is today, with live NASA fire detections." if meta.get("mode") == "live"
               else "(Load real data first: the app is on demo data.)")
    after = ""
    if top:
        after = (" Watch what happens if those fires are stopped: "
                 + " and ".join(f"{c['name']} gets {round(c['reduction_pct'])}% less smoke" for c in top[:2]) + ".")
    video = f"""# 3. Video lines with your numbers

- Opening: "{opening}"
- Plan: "With {plan.get('budget_fires', '[N]')} field-team locations, the plan avoids {plan.get('exposure_avoided_pct_of_preventable', '[X]')}% of tomorrow's preventable exposure. Sending the same teams to the biggest fires manages {plan.get('naive_biggest_fires_pct_of_preventable', '[Y]')}%.{after}"
- Proof: {video_proof}
"""
    return ("# 1. Form: How did you use AWS in your project?\n\n" + aws_answer()
            + "\n\n---\n\n# 2. Writeup\n\n" + writeup + "\n---\n\n" + video)


def main():
    text = build(_load("latest.json"), _load("backtest.json"))
    path = os.path.join(OUTPUT_DIR, "SUBMISSION.md")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {os.path.abspath(path)}")


if __name__ == "__main__":
    main()
