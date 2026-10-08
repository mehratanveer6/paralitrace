"""End-to-end run: fetch -> cluster -> trace -> analyse -> output/latest.json.

    python -m paralitrace.pipeline --mode synthetic
    python -m paralitrace.pipeline --mode live          # real fires; FIRMS_MAP_KEY optional
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np

from .config import OUTPUT_DIR, PARAMS, env
from .data import fires as fires_mod
from .data import winds as winds_mod
from .data.fires import FireCluster
from .data.synthetic import synthetic_fires, synthetic_winds
from .model.analysis import city_forecasts, plan_interventions
from .model.tracer import TraceResult, simulate

IST = timezone(timedelta(hours=5, minutes=30))


def run(mode: str = "synthetic", budget_fires: int = 150, out_dir: str = OUTPUT_DIR) -> dict:
    started = time.time()
    t0 = float(int(datetime.now(timezone.utc).timestamp() // 3600 * 3600))

    if mode == "live":
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
    result = {
        "meta": {
            "mode": mode,
            "data_label": label,
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
        "plan": plan_interventions(trace, budget_fires=budget_fires),
        "plumes": trace.snapshots,
        "wind": wind.to_json(every=3),
    }
    result["meta"]["runtime_s"] = round(time.time() - started, 1)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "latest.json"), "w") as f:
        json.dump(result, f)
    save_trace(trace, out_dir)
    return result


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
    ap.add_argument("--mode", choices=["synthetic", "live"], default="synthetic")
    ap.add_argument("--budget", type=int, default=150, help="fire detections the state can act on")
    a = ap.parse_args()
    r = run(a.mode, a.budget)
    m = r["meta"]
    print(m["data_label"])
    print(f"[{m['mode']}] {m['fire_detections']} detections -> {m['clusters']} clusters, {m['runtime_s']}s")
    for c in sorted(r["cities"], key=lambda c: -c["day1_mean"])[:6]:
        print(f"  {c['name']:<11} day1={c['day1_mean']:>7.2f} ({c['day1_risk']:<8}) peak {c['peak_time_ist']}")
    p = r["plan"]
    print(f"  plan: {len(p['clusters'])} clusters, {p['fires_targeted']} fires -> "
          f"{p['exposure_avoided_pct_of_preventable']}% of preventable exposure "
          f"(naive biggest-fires: {p['naive_biggest_fires_pct_of_preventable']}%)")


if __name__ == "__main__":
    main()
