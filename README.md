# ParaliTrace

Where crop-residue smoke goes in the next 48 hours, and which fields to stop first.

Built for **Environmental Hacks** (Bharat Builds Tour, WeMakeDevs × AWS), Air track.

Every October and November, paddy-stubble (parali) fires across Punjab and Haryana send smoke over
cities from Amritsar to Delhi. Officials know fires are burning. What they lack is an answer to
three practical questions, early enough to act:

1. **Which towns and schools will this smoke reach, and when?**
2. **Which fields is a given city's smoke actually coming from?**
3. **With limited machines and field teams, which fires should we stop tomorrow to protect the most people?**

ParaliTrace answers all three from satellite fire detections and wind forecasts, and an AI agent
turns the answers into advisories in English, Hindi or Punjabi.

## How it works

```
NASA FIRMS (VIIRS fires) ─┐
                          ├─> cluster fires ─> Lagrangian smoke tracer ─> city forecasts
Open-Meteo wind grid ─────┘   (~10 km cells)   (particles + wind +        source attribution
                                                 diffusion + decay)        intervention plan
                                                        │
                                   Strands agent (AWS) ─┴─> answers, school advisories
```

- **Tracer.** Each fire cluster releases particles with mass proportional to its fire radiative
  power. Particles move with bilinearly interpolated hourly winds at 100 m, spread by a
  random-walk diffusion term and decay with a 48 h lifetime. Particles within 20 km of a city add
  to that city's hourly smoke index, tagged with their source cluster.
- **Attribution.** Because every particle carries its source, each city's exposure splits
  exactly into contributions per fire cluster, grouped by district.
- **Persistence forecast.** Today's fields are assumed to burn again tomorrow at 80% intensity.
  Only that projected burning can still be prevented, and the planner counts only it.
- **Planner.** A budgeted greedy knapsack ranks clusters by population-weighted preventable
  exposure per fire location. The dose model is linear in emissions, so benefits are independent
  and ratio-greedy is close to optimal. It is compared against the naive policy of targeting the
  biggest fires.
- **Agent.** A Strands Agents SDK agent with five tools over the model output. It never invents
  numbers, flags synthetic data, and writes advisories in Gurmukhi or Devanagari on request.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m paralitrace.pipeline --mode synthetic     # offline demo data
python -m paralitrace.pipeline --mode live           # real fires + forecast winds (no key needed)

export FIRMS_MAP_KEY=... OPENAQ_API_KEY=...          # both free; needed only for the backtest
python -m paralitrace.backtest                       # replays Oct-Nov 2025, writes output/backtest.json

cd frontend && npm install && npm run build && cd ..   # build the React UI once
uvicorn app:app --reload                             # http://127.0.0.1:8000
pytest -q
```

On Windows, where `python` may not be on PATH, use the launcher: `py -m pip install -r requirements.txt`,
`py -m pytest -q`, `py -m uvicorn app:app --reload`. In Command Prompt set the key with
`set FIRMS_MAP_KEY=...` in the same terminal that starts the server.

Working on the UI: keep `uvicorn` running and run `npm run dev` inside `frontend/`, then open
http://127.0.0.1:5173. Vite hot-reloads and forwards `/api` to the backend.

### The app

- **Map and timeline**: 48 hours of smoke in 3-hour frames. Space plays and pauses, arrow keys step.
- **Cities**: when each city's smoke peaks, its risk for the next two days, and where its smoke comes from.
- **Plan**: which fires to stop tomorrow for a given number of field-team locations.
- **Ask**: the assistant.
- **Proof**: backtest results against ground monitors.
- **Fetch live fires** reruns the pipeline on real data from the browser.

### Hosted demo

`py -m paralitrace.export_demo` packs the forecast on screen, the backtest and recorded assistant answers
into `frontend/public/demo/`. Without a Python server (for example on Vercel, configured by `vercel.json`)
the app detects this, reads the snapshot, re-plans in the browser (`frontend/src/planner.ts`, a tested
mirror of the Python planner) and shows the recorded answers. Live refresh and free-form questions need
the full app.

### Backtest output

The Proof tab reads `output/backtest.json` through `/api/backtest`. The schema is the `Backtest`
interface in `frontend/src/types.ts`: a season summary (spike days caught a day ahead, false alarms,
rank correlation, and a naive baseline to compare against) plus per-city daily rows of forecast
index against measured PM2.5. Until that file exists the tab explains what it will show.

Keys go in `.env` (copy `.env.example`). The assistant needs `GEMINI_API_KEY` (free at aistudio.google.com/apikey),
or any provider listed in `paralitrace/agent.py`. `py -m paralitrace.report` writes `output/SUBMISSION.md`,
the writeup with the numbers from the latest runs.

## AWS

- **AutoGluon** (AWS open source, AutoGluon-TimeSeries) learns a next-day PM2.5 forecast per city in the backtest,
  retrained daily on past data only; combined with the smoke alerts it is the best rule on held-out November.
  `pip install -r requirements-ml.txt` to include it.
- **Strands Agents SDK** (AWS open source) powers the assistant: agent loop, tool calling and the five
  forecast tools. The model is pluggable: Gemini by default (free key), Amazon Bedrock, Anthropic or Ollama.
- **Amazon EC2**: `deploy/` has a one-paste launch script that serves the app and refreshes live data hourly.

## Honest limitations

- The tracer is a simplified 2-D model, not a research-grade dispersion model such as HYSPLIT.
  It has no vertical structure, chemistry or rain-out.
- The smoke index is relative. The backtest checks it against PM2.5 from ground monitors rather than
  converting it to a concentration. It uses ERA5 reanalysis winds in place of archived forecasts.
- City populations are approximate Census 2011 figures.
- Synthetic mode exists for development. The UI labels it clearly and the agent says so.

## Built with

Python, NumPy, FastAPI, Strands Agents SDK. Frontend: React 19, TypeScript, Vite, react-leaflet.
