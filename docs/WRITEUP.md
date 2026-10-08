# ParaliTrace: follow the stubble smoke, stop the right fires

**Track:** Air · **Team:** Tanveer Mehra (solo)

> Draft. Fill the `[[...]]` blanks from `output/backtest.json` after the backtest runs.

## The problem

Every October and November, paddy-stubble fires across Punjab and Haryana send smoke over cities
from Amritsar to Delhi. Satellites already see every fire. What district officials and school
principals don't get is an answer to three questions, early enough to act on:

1. Which towns will this smoke reach, and when?
2. Which fields is my city's smoke coming from?
3. With limited field teams and crop-residue machines, which fires should we stop tomorrow to protect
   the most people?

## What I built

ParaliTrace turns NASA's satellite fire detections and wind forecasts into a 48-hour smoke forecast
for 16 cities across Punjab, Haryana and Delhi.

- **Smoke tracer.** Each ~10 km cluster of fires releases particles in proportion to its fire
  radiative power. They drift with hourly winds, spread with turbulence, and settle out over about two
  days. When particles pass near a city, its smoke index rises.
- **Attribution.** Every particle remembers its source, so each city's smoke splits exactly into
  contributions from named districts.
- **Planner.** Smoke already in the air can't be recalled, but fields expected to burn tomorrow can be
  reached. The planner ranks them by how many people their smoke would reach, within the number of
  locations teams can cover. On today's run it avoids [[X]]% of tomorrow's preventable exposure, against
  [[Y]]% for sending the same teams to the biggest fires.
- **Assistant.** Answers questions and drafts school advisories in English, Hindi or Punjabi, using
  only numbers the model produced.
- **Proof.** A replay of the 2025 season: each day forecast 24 hours ahead and checked against PM2.5
  from ground monitors. It caught [[spikes_caught]] of [[spike_days]] smoke-spike days
  ([[hit_rate]]%), against [[baseline]]% for repeating yesterday's readings, and [[onsets_caught]] of
  [[onset_days]] episode starts, which repeating yesterday can never catch.

## Where AWS fits

- **Strands Agents SDK** (AWS open source) runs the assistant and its five tools over the forecast.
- **Amazon Bedrock** hosts the model the assistant uses.
- **Amazon EC2** serves the app and refreshes live fires and winds every hour.
- **OpenAQ's monitor archive**, used for the backtest, is itself published through the AWS Open Data
  program.

## Data

NASA FIRMS VIIRS active fires (near-real-time and archive), Open-Meteo wind forecasts and ERA5
reanalysis, OpenAQ ground monitor PM2.5, and OpenStreetMap.

## Limits

The tracer is a simplified two-dimensional model, not a research model such as HYSPLIT. The smoke
index is relative and is checked against monitors rather than converted to PM2.5. Tomorrow's burning
is assumed to resemble today's. The backtest uses reanalysis winds in place of the forecasts available
at the time.

## Built with

Python, NumPy, pandas, FastAPI, Strands Agents SDK, Amazon Bedrock, React, TypeScript, Vite, Leaflet.
**AI coding tools:** Claude (Anthropic) for code, tests and drafting.

Repository: https://github.com/mehratanveer6/paralitrace
