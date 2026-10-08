"""Turn a TraceResult into city forecasts, source attribution and an intervention plan."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import numpy as np

from ..config import PLACES, RECEPTORS, RISK_BANDS
from .tracer import TraceResult

IST = timezone(timedelta(hours=5, minutes=30))


def risk_band(index: float) -> str:
    band = RISK_BANDS[0][1]
    for threshold, name in RISK_BANDS:
        if index >= threshold:
            band = name
    return band


def _ist(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, IST).strftime("%a %d %b, %H:%M IST")


def nearest_place(lat: float, lon: float) -> tuple[str, float, str]:
    """(district HQ name, distance km, compass direction of the point from the HQ)."""
    best = min(PLACES, key=lambda p: _km(lat, lon, p[1], p[2]))
    d = _km(lat, lon, best[1], best[2])
    ang = np.degrees(np.arctan2((lon - best[2]) * np.cos(np.deg2rad(lat)), lat - best[1])) % 360
    compass = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((ang + 22.5) // 45) % 8]
    return best[0], d, compass


def describe(lat: float, lon: float) -> str:
    name, d, comp = nearest_place(lat, lon)
    return f"near {name}" if d < 5 else f"{d:.0f} km {comp} of {name}"


def _grouped_sources(tr: TraceResult, ri: int, top_n: int) -> list[dict]:
    """Aggregate a city's source clusters by nearest district HQ."""
    r = RECEPTORS[ri]
    total = tr.dose_by_src[ri].sum()
    if total <= 0:
        return []
    groups: dict[str, dict] = {}
    for c in np.flatnonzero(tr.dose_by_src[ri] > 0):
        cl = tr.clusters[c]
        name = nearest_place(cl.lat, cl.lon)[0]
        g = groups.setdefault(name, {"w": 0.0, "lat": 0.0, "lon": 0.0, "clusters": 0, "fires": 0})
        w = tr.dose_by_src[ri, c]
        g["w"] += w; g["lat"] += w * cl.lat; g["lon"] += w * cl.lon
        g["clusters"] += 1; g["fires"] += cl.n_fires
    rows = []
    for name, g in sorted(groups.items(), key=lambda kv: -kv[1]["w"])[:top_n]:
        lat, lon = g["lat"] / g["w"], g["lon"] / g["w"]
        rows.append({"area": name, "lat": round(lat, 3), "lon": round(lon, 3),
                     "share_pct": round(100 * g["w"] / total, 1), "fires": g["fires"],
                     "distance_km": round(_km(r.lat, r.lon, lat, lon), 0)})
    return rows


def city_forecasts(tr: TraceResult, top_n: int = 5) -> list[dict]:
    out = []
    for ri, r in enumerate(RECEPTORS):
        series = tr.dose[ri]
        d1, d2 = series[:24], series[24:48]
        peak_h = int(series.argmax()) if series.size else 0
        total = tr.dose_by_src[ri].sum()
        sources = _grouped_sources(tr, ri, top_n)
        out.append({
            "id": r.id, "name": r.name, "lat": r.lat, "lon": r.lon, "population": r.population,
            "hourly_index": series.round(3).tolist(),
            "day1_mean": round(float(d1.mean()), 3) if d1.size else 0.0,
            "day2_mean": round(float(d2.mean()), 3) if d2.size else 0.0,
            "peak_index": round(float(series.max()), 3) if series.size else 0.0,
            "peak_time_ist": _ist(tr.hours[peak_h]) if series.size else None,
            "day1_risk": risk_band(float(d1.mean()) if d1.size else 0),
            "day2_risk": risk_band(float(d2.mean()) if d2.size else 0),
            "peak_risk": risk_band(float(series.max()) if series.size else 0),
            "preventable_pct": round(100 * tr.dose_by_src_projected[ri].sum() / total, 1) if total > 0 else 0.0,
            "top_sources": sources,
        })
    return out


def plan_interventions(tr: TraceResult, budget_fires: int = 150) -> dict:
    """Greedy knapsack: which clusters to stop burning tomorrow to cut the most
    population-weighted smoke exposure, given a budget counted in fire detections
    (a proxy for machines or field teams). Only projected releases are preventable.

    The dose model is linear in emissions, so each cluster's benefit is independent
    and ratio-greedy is near optimal for this budget constraint.
    """
    pop = np.array([r.population for r in RECEPTORS], dtype=float)
    harm = pop @ tr.dose_by_src_projected            # (C,) person-weighted preventable dose
    total_harm = float((pop @ tr.dose_by_src).sum())  # everything in the forecast window
    preventable = float(harm.sum())
    cost = np.array([max(c.n_fires, 1) for c in tr.clusters], dtype=float)
    order = np.argsort(-(harm / cost))

    chosen, spent, gained = [], 0, 0.0
    for c in order:
        if harm[c] <= 0:
            break
        if spent + cost[c] > budget_fires:
            continue
        spent += int(cost[c]); gained += float(harm[c])
        cl = tr.clusters[c]
        top_r = np.argsort(-(pop * tr.dose_by_src_projected[:, c]))[:3]
        chosen.append({
            "cluster_id": cl.id, "lat": round(cl.lat, 3), "lon": round(cl.lon, 3),
            "location": describe(cl.lat, cl.lon),
            "fires": cl.n_fires, "frp_mw": round(cl.frp_mw, 1),
            "share_of_preventable_pct": round(100 * harm[c] / preventable, 2) if preventable else 0,
            "protects": [RECEPTORS[i].name for i in top_r if tr.dose_by_src_projected[i, c] > 0],
        })

    # Naive baseline: stop the biggest fires (by FRP) with the same budget.
    naive, spent_n = 0.0, 0
    for c in np.argsort([-cl.frp_mw for cl in tr.clusters]):
        if spent_n + cost[c] > budget_fires:
            continue
        spent_n += int(cost[c]); naive += float(harm[c])

    return {
        "budget_fires": budget_fires,
        "fires_targeted": spent,
        "clusters": chosen,
        "exposure_avoided_pct_of_preventable": round(100 * gained / preventable, 1) if preventable else 0,
        "exposure_avoided_pct_of_total": round(100 * gained / total_harm, 1) if total_harm else 0,
        "naive_biggest_fires_pct_of_preventable": round(100 * naive / preventable, 1) if preventable else 0,
        "note": "Benefit counts only tomorrow's projected burning; smoke already emitted cannot be prevented.",
    }


def _km(lat1, lon1, lat2, lon2) -> float:
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return float(12742 * np.arcsin(np.sqrt(a)))
