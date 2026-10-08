"""Replay a past burning season and check the forecasts against ground monitors.

For each day D of the season, issue a forecast the evening before (18:00 IST on D-1) using only
fires detected in the 36 hours up to then, exactly as the live system would, and average the
predicted smoke index over day D. Then compare with the daily mean PM2.5 measured near each city.

    py -m paralitrace.backtest                       # Oct 1 - Nov 30, 2025
    py -m paralitrace.backtest --start 2025-10-15 --end 2025-11-15

Needs FIRMS_MAP_KEY (historical fires) and OPENAQ_API_KEY (monitor data). Winds come from the
Open-Meteo ERA5 archive, which needs no key. Downloads are cached in output/cache, so a rerun
only recomputes. Writes output/backtest.json, the schema the Proof tab reads (Backtest in
frontend/src/types.ts).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from .config import BBOX, OUTPUT_DIR, PARAMS, RECEPTORS, env
from .data import fires as fires_mod
from .data import winds as winds_mod
from .model.tracer import simulate

IST = timezone(timedelta(hours=5, minutes=30))
OPENAQ = "https://api.openaq.org/v3"
PM25_NAMES = {"pm25", "pm2.5"}
SPIKE_QUANTILE = 0.75          # a spike is a day in the city's worst quarter for PM2.5 that season
MIN_COVERAGE_PCT = 50          # ignore monitor-days with less than half their hours reported
ISSUE_HOUR_IST = 18            # forecasts issued at 18:00 IST the evening before
LOOKBACK_H = 36                # fires used for each forecast


# ---------- small helpers ----------

def _days(start: str, end: str) -> list[date]:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]


def _cache(name: str) -> str:
    path = os.path.join(OUTPUT_DIR, "cache")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, name)


def spearman(a, b) -> float | None:
    """Rank correlation without scipy. None when fewer than 8 paired days."""
    s = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(s) < 8 or s.a.nunique() < 2 or s.b.nunique() < 2:
        return None
    return float(np.corrcoef(s.a.rank(), s.b.rank())[0, 1])


# ---------- data ----------

def fetch_season_fires(start: str, end: str, key: str) -> pd.DataFrame:
    """FIRMS standard-processing archive in 5-day requests, cached per request."""
    lat_min, lat_max, lon_min, lon_max = BBOX
    area = f"{lon_min},{lat_min},{lon_max},{lat_max}"
    first = date.fromisoformat(start) - timedelta(days=2)       # lookback before the first forecast
    last = date.fromisoformat(end)
    frames, failed = [], []
    for src in fires_mod.ARCHIVE_SOURCES:
        try:
            frames += _fetch_source(src, area, first, last, key)
        except Exception as e:                       # e.g. one satellite's archive not processed yet
            print(f"  skipping {src}: {e}")
            failed.append(src)
    if not frames:
        raise RuntimeError(f"No archived fires returned for this season and area (failed: {failed}).")
    df = fires_mod.normalise(pd.concat(frames, ignore_index=True))
    return df.drop_duplicates(subset=["latitude", "longitude", "t_epoch"]).reset_index(drop=True)


def _fetch_source(src: str, area: str, first: date, last: date, key: str) -> list[pd.DataFrame]:
    frames = []
    d = first
    while d <= last:
        path = _cache(f"firms_{src}_{d}.csv")
        if not os.path.exists(path):
            url = fires_mod.FIRMS_URL.format(key=key, source=src, area=area, days=5) + f"/{d}"
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            if r.text.lower().startswith("invalid"):
                raise RuntimeError(f"FIRMS rejected the request: {r.text[:200]}")
            with open(path, "w") as f:
                f.write(r.text)
        text = open(path).read()
        if text.strip():
            df = pd.read_csv(io.StringIO(text))
            if len(df):
                frames.append(df)
        d += timedelta(days=5)
    return frames


def fetch_season_winds(start: str, end: str) -> winds_mod.WindField:
    first = (date.fromisoformat(start) - timedelta(days=3)).isoformat()
    last = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    path = _cache(f"winds_{first}_{last}.npz")
    if os.path.exists(path):
        z = np.load(path)
        return winds_mod.WindField(z["lats"], z["lons"], z["times"], z["u"], z["v"])
    w = winds_mod.fetch_open_meteo(start_date=first, end_date=last)
    np.savez_compressed(path, lats=w.lats, lons=w.lons, times=w.times, u=w.u, v=w.v)
    return w


class OpenAQ:
    def __init__(self, key: str):
        self.s = requests.Session()
        self.s.headers["X-API-Key"] = key
        self.last = 0.0

    def get(self, path: str, **params) -> dict:
        wait = 1.1 - (time.time() - self.last)            # stay under 60 requests a minute
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            r = self.s.get(OPENAQ + path, params=params, timeout=60)
            self.last = time.time()
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1)); continue
            if r.status_code == 401:
                raise RuntimeError("OpenAQ rejected the key. Check OPENAQ_API_KEY.")
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"OpenAQ kept rate-limiting {path}")


def fetch_city_pm25(api: OpenAQ, lat: float, lon: float, start: str, end: str) -> pd.Series:
    """Daily mean PM2.5 near a city: median across monitors within 25 km, IST calendar days."""
    locs = api.get("/locations", coordinates=f"{lat:.4f},{lon:.4f}", radius=25000, limit=100)["results"]
    sensors = []
    for loc in locs:
        first = (loc.get("datetimeFirst") or {}).get("utc") or ""
        last = (loc.get("datetimeLast") or {}).get("utc") or ""
        if first[:10] > end or (last and last[:10] < start):
            continue
        sensors += [s["id"] for s in loc.get("sensors", [])
                    if (s.get("parameter") or {}).get("name", "").lower() in PM25_NAMES]
    per_sensor = []
    for sid in sensors:
        # a day of buffer either side: OpenAQ filters in UTC, the days we score are IST
        d_from = (date.fromisoformat(start) - timedelta(days=1)).isoformat() + "T00:00:00Z"
        d_to = (date.fromisoformat(end) + timedelta(days=1)).isoformat() + "T23:59:59Z"
        res = api.get(f"/sensors/{sid}/days", date_from=d_from, date_to=d_to, limit=1000)["results"]
        rows = {}
        for d in res:
            cov = (d.get("coverage") or {}).get("percentComplete")
            if d.get("value") is None or (cov is not None and cov < MIN_COVERAGE_PCT):
                continue
            day = (d["period"]["datetimeFrom"].get("local") or d["period"]["datetimeFrom"]["utc"])[:10]
            rows[day] = float(d["value"])
        if rows:
            per_sensor.append(pd.Series(rows))
    if not per_sensor:
        return pd.Series(dtype=float)
    return pd.concat(per_sensor, axis=1).median(axis=1)


def season_pm25(start: str, end: str, key: str) -> dict[str, pd.Series]:
    path = _cache(f"openaq_{start}_{end}.json")
    if os.path.exists(path):
        raw = json.load(open(path))
        return {k: pd.Series(v, dtype=float) for k, v in raw.items()}
    api = OpenAQ(key)
    out = {}
    for r in RECEPTORS:
        print(f"  monitors near {r.name}")
        out[r.id] = fetch_city_pm25(api, r.lat, r.lon, start, end)
    json.dump({k: v.to_dict() for k, v in out.items()}, open(path, "w"))
    return out


# ---------- replay ----------

def replay(fires: pd.DataFrame, wind: winds_mod.WindField, days: list[date]) -> pd.DataFrame:
    """Predicted mean smoke index per city per day, each forecast issued the evening before."""
    p = replace(PARAMS, horizon_hours=24 + (24 - ISSUE_HOUR_IST), particles_per_cluster=30)
    skip = 24 - ISSUE_HOUR_IST          # hours from issue time to the start of day D (IST)
    rows = []
    for i, d in enumerate(days):
        issue = datetime(d.year, d.month, d.day, tzinfo=IST) - timedelta(hours=skip)
        t0 = issue.timestamp()
        window = fires[(fires.t_epoch > t0 - LOOKBACK_H * 3600) & (fires.t_epoch <= t0)]
        tr = simulate(fires_mod.cluster_fires(window), wind, t0, p)
        day_mean = tr.dose[:, skip:skip + 24].mean(axis=1)
        rows += [{"date": d.isoformat(), "city": r.id, "predicted": float(v)} for r, v in zip(RECEPTORS, day_mean)]
        print(f"  {d}  {len(window):5d} fires  ({i + 1}/{len(days)})")
    return pd.DataFrame(rows)


def score(pred: pd.DataFrame, obs: dict[str, pd.Series], start: str, end: str) -> dict:
    """Build the Backtest document the Proof tab renders."""
    cities, tot = [], dict(spikes=0, caught=0, predicted=0, false=0, base_caught=0, onsets=0, onsets_caught=0)
    corrs = []
    for r in RECEPTORS:
        p = pred[pred.city == r.id].set_index("date")["predicted"]
        o = obs.get(r.id, pd.Series(dtype=float)).reindex(p.index)
        if o.notna().sum() < 10:
            continue                                   # too little monitor data to judge this city
        o_thr = o.quantile(SPIKE_QUANTILE)
        p_thr = p.quantile(SPIKE_QUANTILE)
        obs_spike = (o >= o_thr) & o.notna()
        pred_spike = (p >= p_thr) & (p > 0)            # no smoke forecast is never a spike call
        yest = obs_spike.shift(1, fill_value=False)    # baseline: repeat yesterday
        onset = obs_spike & ~yest
        valid = o.notna()
        caught = int((obs_spike & pred_spike).sum())
        false = int((pred_spike & ~obs_spike & valid).sum())
        rho = spearman(p, o)
        if rho is not None:
            corrs.append(rho)
        tot["spikes"] += int(obs_spike.sum()); tot["caught"] += caught
        tot["predicted"] += int((pred_spike & valid).sum()); tot["false"] += false
        tot["base_caught"] += int((obs_spike & yest).sum())
        tot["onsets"] += int(onset.sum()); tot["onsets_caught"] += int((onset & pred_spike).sum())
        cities.append({
            "id": r.id, "name": r.name, "spike_days": int(obs_spike.sum()), "spikes_caught": caught,
            "false_alarms": false, "correlation": None if rho is None else round(rho, 2),
            "days": [{"date": dd, "predicted_index": round(float(p[dd]), 2),
                      "observed_pm25": None if pd.isna(o[dd]) else round(float(o[dd]), 1),
                      "observed_spike": bool(obs_spike[dd]), "predicted_spike": bool(pred_spike[dd])}
                     for dd in p.index],
        })
    if not cities:
        raise RuntimeError("No city had enough monitor data to score.")
    pct = lambda a, b: round(100 * a / b) if b else 0
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return {
        "season": f"{d0:%b}-{d1:%b %Y}" if d0.month != d1.month else f"{d0:%b %Y}",
        "start": f"{d0.day} {d0:%b}",
        "end": f"{d1.day} {d1:%b}",
        "lead_hours": 24,
        "spike_definition": "A spike is a day in that city's worst quarter for PM2.5 that season.",
        "notes": ("Forecasts use archived ERA5 winds in place of the wind forecasts available at the time, "
                  "so wind error is not included. Fires come from NASA's standard-processing VIIRS archive."),
        "summary": {
            "spike_days": tot["spikes"], "spikes_caught": tot["caught"],
            "hit_rate_pct": pct(tot["caught"], tot["spikes"]),
            "false_alarm_pct": pct(tot["false"], tot["predicted"]),
            "median_correlation": round(float(np.median(corrs)), 2) if corrs else None,
            "baseline_label": "repeating yesterday's PM2.5",
            "baseline_hit_rate_pct": pct(tot["base_caught"], tot["spikes"]),
            "onset_days": tot["onsets"], "onsets_caught": tot["onsets_caught"],
        },
        "cities": sorted(cities, key=lambda c: -c["spike_days"]),
    }


def run(start: str, end: str) -> dict:
    fkey, akey = env("FIRMS_MAP_KEY"), env("OPENAQ_API_KEY")
    missing = [n for n, v in (("FIRMS_MAP_KEY", fkey), ("OPENAQ_API_KEY", akey)) if not v]
    if missing:
        raise SystemExit(f"Set {' and '.join(missing)} first (both free). See the docstring of this file.")
    print("Fires (NASA FIRMS archive)"); fires = fetch_season_fires(start, end, fkey)
    print(f"  {len(fires)} detections")
    print("Winds (Open-Meteo ERA5 archive)"); wind = fetch_season_winds(start, end)
    print("Monitors (OpenAQ)"); obs = season_pm25(start, end, akey)
    print("Replaying forecasts"); pred = replay(fires, wind, _days(start, end))
    doc = score(pred, obs, start, end)
    with open(os.path.join(OUTPUT_DIR, "backtest.json"), "w") as f:
        json.dump(doc, f)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end", default="2025-11-30")
    a = ap.parse_args()
    s = run(a.start, a.end)["summary"]
    print(f"\nCaught {s['spikes_caught']}/{s['spike_days']} spike days ({s['hit_rate_pct']}%), "
          f"baseline {s['baseline_hit_rate_pct']}%, onsets {s['onsets_caught']}/{s['onset_days']}, "
          f"false alarms {s['false_alarm_pct']}%, median rank correlation {s['median_correlation']}")


if __name__ == "__main__":
    main()
