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
export FIRMS_MAP_KEY=...                             # free: firms.modaps.eosdis.nasa.gov/api/map_key
python -m paralitrace.pipeline --mode live           # real fires + forecast winds

cd frontend && npm install && npm run build && cd ..   # build the React UI once
uvicorn app:app --reload                             # http://127.0.0.1:8000
pytest -q
```

Working on the UI: keep `uvicorn` running and run `npm run dev` inside `frontend/`, then open
http://127.0.0.1:5173. Vite hot-reloads and forwards `/api` to the backend.

The assistant tab needs a model. Pick one with `PT_MODEL`:

| `PT_MODEL` | Needs |
|---|---|
| `bedrock` (default) | AWS credentials with Bedrock model access, `AWS_REGION` |
| `ollama` | a local Ollama with a tool-calling model, `OLLAMA_MODEL` |
| `anthropic` | `ANTHROPIC_API_KEY` and `pip install 'strands-agents[anthropic]'` |

## AWS

- **Strands Agents SDK** (AWS open source) powers the assistant.
- **Amazon Bedrock** is the default model provider.
- Planned deployment: Lambda + EventBridge for the hourly pipeline, S3 for outputs,
  API Gateway for the API, Amplify Hosting for the map.

## Honest limitations

- The tracer is a simplified 2-D model, not a research-grade dispersion model such as HYSPLIT.
  It has no vertical structure, chemistry or rain-out.
- The smoke index is relative. Risk bands are placeholders until the backtest against 2025 CPCB
  PM2.5 data calibrates them.
- City populations are approximate Census 2011 figures.
- Synthetic mode exists for development. The UI labels it clearly and the agent says so.

## Built with

Python, NumPy, FastAPI, Strands Agents SDK. Frontend: React 19, TypeScript, Vite, react-leaflet. AI coding assistant: Claude (Anthropic).
