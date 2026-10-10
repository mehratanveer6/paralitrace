"""End-to-end run: fetch -> cluster -> trace -> analyse -> output/latest.json.

    python -m paralitrace.pipeline --mode synthetic
    python -m paralitrace.pipeline --mode live          # real fires; FIRMS_MAP_KEY optional
    python -m paralitrace.pipeline --mode replay        # a real past day, by default the smokiest day
                                                        # of the last backtest (needs FIRMS_MAP_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np

from .config import OUTPUT_DIR, PARAMS, RECEPTORS, env
from .data import fires as fires_mod
from .data import winds as winds_mod
from .data.fires import FireCluster
from .data.synthetic import synthetic_fires, synthetic_winds
from .model.analysis import auto_budget, city_forecasts, plan_interventions, risk_band
from .model.tracer import TraceResult, simulate

IST = timezone(timedelta(hours=5, minutes=30))


def run(mode: str = "synthetic", budget_fires: int | None = None, out_dir: str = OUTPUT_DIR,
        date: str | None = None) -> dict:
    """budget_fires=None sizes the plan to the day (see auto_budget)."""
    started = time.time()
    t0 = float(int(datetime.now(timezone.utc).timestamp() // 3600 * 3600))
    replay_date = None

    if mode == "replay":
        replay_date = date or smokiest_backtest_day(out_dir)
        df, wind, t0 = replay_inputs(replay_date)
        label = f"Replay of {_long_date(replay_date)}: NASA FIRMS archive fires + ERA5 winds"
    elif mode == "live":
        df = live_fires()
        wind = winds_mod.fetch_open_meteo(past_days=2, forecast_days=3)
        newest = datetime.fromtimestamp(df["t_epoch"].max(), IST).strftime("%d %b, %H:%M IST") if len(df) else "none"
        label = f"NASA FIRMS VIIRS fires (newest {newest}) + Open-Meteo winds"
    else:
        df = synthetic_fires(t0)
        wind = synthetic_winds(t0 - 36 * 3600, hours=36 + PARAMS.horizon_hours + 6)
        label = "SYNTHETIC demo data"

    clusters = fires_mod.cluster_fires(df)
    trace = simulate(clusters, wind, t0)
    budget = budget_fires or auto_budget(trace)
    plan = plan_interventions(trace, budget_fires=budget)
    result = {
        "meta": {
            "mode": mode,
            "data_label": label,
            "replay_date": replay_date,
            "newest_fire_epoch": int(df["t_epoch"].max()) if len(df) else None,
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "forecast_start_epoch": int(t0),
            "horizon_hours": PARAMS.horizon_hours,
            "fire_detections": int(len(df)),
            "clusters": len(clusters),
            "runtime_s": None,
            "calibrated": False,
        },
        "clusters": [c.to_dict() for c in clusters],
        "cities": city_forecasts(trace),
        "plan": plan,
        "counterfactual": counterfactual(clusters, wind, t0, trace, plan),
        "plumes": trace.snapshots,
        "wind": wind.to_json(every=3),
    }
    result["meta"]["runtime_s"] = round(time.time() - started, 1)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "latest.json"), "w") as f:
        json.dump(result, f)
    save_trace(trace, out_dir)
    return result


def counterfactual(clusters, wind, t0, trace: TraceResult, plan: dict) -> dict:
    """The same forecast with the plan's fires stopped: what the map and cities would look like."""
    index = {c.id: i for i, c in enumerate(clusters)}
    stopped = {index[c["cluster_id"]] for c in plan["clusters"] if c["cluster_id"] in index}
    after = simulate(clusters, wind, t0, stopped=stopped)
    cities = []
    for i, r in enumerate(RECEPTORS):
        b, a = trace.dose[i], after.dose[i]
        if b.sum() <= 0:
            continue
        cities.append({
            "id": r.id, "name": r.name, "hourly_index": a.round(3).tolist(),
            "before_peak_risk": risk_band(float(b.max())), "after_peak_risk": risk_band(float(a.max())),
            "reduction_pct": round(100 * (1 - a.sum() / b.sum()), 1),
        })
    cities.sort(key=lambda c: -c["reduction_pct"])
    return {"budget_fires": plan["budget_fires"], "plumes": after.snapshots, "cities": cities}


def _long_date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d:%b %Y}"


def smokiest_backtest_day(out_dir: str = OUTPUT_DIR) -> str:
    """The day of the last backtest with the most forecast smoke across cities: the most telling replay."""
    path = os.path.join(out_dir, "backtest.json")
    if not os.path.exists(path):
        raise SystemExit("Replay needs a date (--date YYYY-MM-DD) or a finished backtest to pick one from.")
    with open(path) as f:
        cities = json.load(f)["cities"]
    totals: dict[str, float] = {}
    for c in cities:
        for d in c["days"]:
            totals[d["date"]] = totals.get(d["date"], 0.0) + d["predicted_index"]
    return max(totals, key=totals.get)


def replay_inputs(day: str):
    """Fires and winds exactly as a forecast issued at 18:00 IST the evening before `day` would have seen."""
    from . import backtest
    key = env("FIRMS_MAP_KEY")
    if not key:
        raise SystemExit("Replay needs FIRMS_MAP_KEY for archived fires.")
    fires = backtest.fetch_season_fires(day, day, key)
    wind = backtest.fetch_season_winds(day, day)
    d = datetime.fromisoformat(day)
    t0 = datetime(d.year, d.month, d.day, tzinfo=IST).timestamp() - (24 - backtest.ISSUE_HOUR_IST) * 3600
    window = fires[(fires.t_epoch > t0 - backtest.LOOKBACK_H * 3600) & (fires.t_epoch <= t0)].reset_index(drop=True)
    return window, wind, t0


def live_fires():
    """Keyed FIRMS API when FIRMS_MAP_KEY is set (falls back on failure), else NASA's public no-key files."""
    key = env("FIRMS_MAP_KEY")
    if key:
        try:
            return fires_mod.keep_fresh(fires_mod.fetch_firms(key, days=2))
        except Exception as e:
            print(f"FIRMS API failed ({e}); using the public files instead")
    return fires_mod.fetch_firms_public("48h")


def save_trace(trace, out_dir: str = OUTPUT_DIR) -> None:
    """Source-receptor matrices, so plans can be re-run for any budget without re-tracing."""
    np.savez_compressed(os.path.join(out_dir, "trace.npz"), t0=trace.t0, hours=trace.hours,
                        dose=trace.dose, dose_by_src=trace.dose_by_src,
                        dose_by_src_projected=trace.dose_by_src_projected)


def load_trace(out_dir: str = OUTPUT_DIR) -> TraceResult:
    with open(os.path.join(out_dir, "latest.json")) as f:
        clusters = [FireCluster(**c) for c in json.load(f)["clusters"]]
    z = np.load(os.path.join(out_dir, "trace.npz"))
    return TraceResult(float(z["t0"]), z["hours"], z["dose"], z["dose_by_src"],
                       z["dose_by_src_projected"], [], clusters)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["synthetic", "live", "replay"], default="synthetic")
    ap.add_argument("--budget", type=int, default=None, help="fire locations teams can cover (default: sized to the day)")
    ap.add_argument("--date", help="replay date, YYYY-MM-DD")
    a = ap.parse_args()
    r = run(a.mode, a.budget, date=a.date)
    m = r["meta"]
    print(m["data_label"])
    print(f"[{m['mode']}] {m['fire_detections']} detections -> {m['clusters']} clusters, {m['runtime_s']}s")
    for c in sorted(r["cities"], key=lambda c: -c["day1_mean"])[:6]:
        print(f"  {c['name']:<11} day1={c['day1_mean']:>7.2f} ({c['day1_risk']:<8}) peak {c['peak_time_ist']}")
    p = r["plan"]
    cf = r["counterfactual"]["cities"][:3]
    print("  if stopped: " + ", ".join(f"{c['name']} -{c['reduction_pct']}%" for c in cf))
    print(f"  plan: {len(p['clusters'])} clusters, {p['fires_targeted']} fires -> "
          f"{p['exposure_avoided_pct_of_preventable']}% of preventable exposure "
          f"(naive biggest-fires: {p['naive_biggest_fires_pct_of_preventable']}%)")


if __name__ == "__main__":
    main()
