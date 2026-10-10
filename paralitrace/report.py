"""Fill the submission writeup and video script with the numbers from the latest runs.

    py -m paralitrace.report

Reads output/latest.json (live forecast) and output/backtest.json (season replay) and writes
output/SUBMISSION.md: the writeup to paste into the submission form, then the video lines with
their numbers filled in. Sections whose data is missing say so instead of inventing figures.
"""
from __future__ import annotations

import json
import os

from .config import OUTPUT_DIR


def _load(name: str) -> dict | None:
    path = os.path.join(OUTPUT_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def build(latest: dict | None, bt: dict | None) -> str:
    plan = (latest or {}).get("plan") or {}
    meta = (latest or {}).get("meta") or {}
    real = meta.get("mode") in ("live", "replay")

    if plan:
        when = "On the replayed day" if meta.get("mode") == "replay" else "On the forecast run for this submission"
        plan_line = (f"{when} it avoids {plan['exposure_avoided_pct_of_preventable']}% "
                     f"of tomorrow's preventable exposure with {plan['fires_targeted']} fire locations, against "
                     f"{plan['naive_biggest_fires_pct_of_preventable']}% for sending the same teams to the biggest fires.")
        if not real:
            plan_line += " (These numbers come from demo data; rerun with live data before submitting.)"
    else:
        plan_line = "(Run the pipeline to fill in the planner's numbers.)"

    if bt:
        s = bt["summary"]
        proof = (f"It caught {s['spikes_caught']} of {s['spike_days']} smoke-spike days a day ahead "
                 f"({s['hit_rate_pct']}%), against {s['baseline_hit_rate_pct']}% for {s['baseline_label']}")
        if s.get("onset_days"):
            proof += (f", and {s['onsets_caught']} of {s['onset_days']} episode starts, the first smoky day after "
                      f"a clear one, which repeating yesterday can never catch")
        proof += f". {s['false_alarm_pct']}% of predicted spikes did not happen."
        if s.get("median_correlation") is not None:
            proof += f" Median rank correlation with measured PM2.5 across cities: {s['median_correlation']:.2f}."
        proof_section = (f"- **Proof.** A replay of {bt['season']} across {len(bt['cities'])} cities: each day forecast "
                         f"24 hours ahead from the previous day's fires and checked against PM2.5 from ground "
                         f"monitors. {proof}")
        video_proof = (f"\"Does it work? I replayed {bt['season']} against ground monitors. It caught "
                       f"{s['spikes_caught']} of {s['spike_days']} smoke-spike days a day ahead"
                       + (f", including {s['onsets_caught']} episode starts that simply repeating yesterday can never catch"
                          if s.get("onset_days") else "") + ".\"")
    else:
        proof_section = ("- **Proof.** A backtest module replays a past season against ground-monitor PM2.5 "
                         "(`py -m paralitrace.backtest`). (Not run yet: add the FIRMS and OpenAQ keys to .env.)")
        video_proof = "(Backtest not run yet. Skip this segment or show the Proof tab's explanation.)"

    data_line = meta.get("data_label", "")
    writeup = f"""# ParaliTrace: follow the stubble smoke, stop the right fires

**Track:** Air
**Repository:** https://github.com/mehratanveer6/paralitrace

## The problem

Every October and November, paddy-stubble fires across Punjab and Haryana send smoke over cities
from Amritsar to Delhi. Satellites already see every fire. What district officials and school
principals don't get is an answer to three questions, early enough to act on:

1. Which towns will this smoke reach, and when?
2. Which fields is my city's smoke coming from?
3. With limited field teams and crop-residue machines, which fires should we stop tomorrow to protect the most people?

## What I built

ParaliTrace turns NASA satellite fire detections and wind forecasts into a 48-hour smoke forecast
for 16 cities across Punjab, Haryana and Delhi.

- **Smoke tracer.** Each ~10 km cluster of fires releases particles in proportion to its fire radiative
  power. They drift with hourly winds, spread with turbulence and settle out over about two days. When
  particles pass near a city, its smoke index rises.
- **Attribution.** Every particle remembers its source, so each city's smoke splits exactly into
  contributions from named districts.
- **Planner.** Smoke already in the air can't be recalled, but fields expected to burn tomorrow can be
  reached. The planner ranks them by how many people their smoke would reach, within the number of
  locations field teams can cover. {plan_line}
- **Assistant.** Built with the Strands Agents SDK. It answers questions and drafts school advisories in
  English, Hindi or Punjabi, and can only quote numbers the model produced, through five tools over the
  forecast.
{proof_section}

## Where AWS fits

- **Strands Agents SDK**, AWS's open-source agent framework, runs the assistant: the agent loop, tool
  calling and the five forecast tools it reasons over. The model behind it is pluggable (Gemini by
  default, Amazon Bedrock supported).
- The repository includes a one-paste **Amazon EC2** launch script that serves the app and refreshes
  live data hourly, ready for deployment on AWS.

## Data

NASA FIRMS VIIRS active fires (near-real-time and standard-processing archive), Open-Meteo wind
forecasts and ERA5 reanalysis, OpenAQ ground-monitor PM2.5, OpenStreetMap.
{"Data shown in the demo: " + data_line + "." if data_line else ""}

## Limits

The tracer is a simplified two-dimensional model, not a research model such as HYSPLIT. The smoke
index is relative and is checked against monitors rather than converted to PM2.5. Tomorrow's burning is
assumed to resemble today's. The backtest uses reanalysis winds in place of the forecasts available at
the time.

## Built with

Python, NumPy, pandas, FastAPI, Strands Agents SDK, React, TypeScript, Vite, Leaflet.
**AI coding tools used:** Claude (Anthropic), for code, tests and drafting.
"""

    pct = lambda k: plan.get(k, "[run the pipeline]")
    video = f"""# Video lines with your numbers

- Opening: "{'This is ' + meta.get('data_label','').split(':')[0].replace('Replay of ','') + ', replayed with real NASA fire detections.' if meta.get('mode') == 'replay' else 'This is today, with live NASA fire detections.'}"
- Plan segment: "With {plan.get('budget_fires', '[N]')} field-team locations, the plan avoids {pct('exposure_avoided_pct_of_preventable')}% of tomorrow's preventable exposure. Sending the same teams to the biggest fires manages {pct('naive_biggest_fires_pct_of_preventable')}%."
- Proof segment: {video_proof}
"""
    return writeup + "\n---\n\n" + video


def main():
    text = build(_load("latest.json"), _load("backtest.json"))
    path = os.path.join(OUTPUT_DIR, "SUBMISSION.md")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {os.path.abspath(path)}")


if __name__ == "__main__":
    main()
