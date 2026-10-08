"""Lagrangian particle tracer for crop-residue smoke.

Each fire cluster emits particles whose mass is proportional to its fire
radiative power (FRP). Particles are advected by the interpolated wind field,
spread by a random-walk turbulent diffusion term and removed with an
e-folding lifetime. Every step, particles near a receptor city add to that
city's smoke dose, tagged by source cluster, which gives attribution for free.

Two kinds of release:
  observed  - fires already detected by satellite (their smoke is in the air)
  projected - persistence forecast: the same fields burning again tomorrow,
              scaled by PARAMS.persistence. Only these can still be prevented,
              so the intervention planner uses projected dose alone.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import PARAMS, RECEPTORS, ModelParams
from ..data.fires import FireCluster
from ..data.winds import WindField

M_PER_DEG = 111_320.0


@dataclass
class TraceResult:
    t0: float                       # forecast start (UTC epoch)
    hours: np.ndarray               # (H,) epoch of each forecast hour
    dose: np.ndarray                # (R, H) smoke index per receptor per hour
    dose_by_src: np.ndarray         # (R, C) total forecast-window dose by cluster, all releases
    dose_by_src_projected: np.ndarray  # (R, C) same, projected (preventable) releases only
    snapshots: list[dict]           # particle positions every 3 h for the map
    clusters: list[FireCluster]


def _releases(clusters, t0, p: ModelParams, rng):
    """Build per-particle release time, mass, source index and projected flag."""
    rt, mass, src, proj = [], [], [], []
    n = p.particles_per_cluster
    for ci, c in enumerate(clusters):
        days = [(0, 1.0, False)]
        for k in (1, 2):
            if c.t_epoch + 86400 * k < t0 + p.horizon_hours * 3600:
                days.append((k, p.persistence ** k, True))
        for k, scale, is_proj in days:
            base = c.t_epoch + 86400 * k - p.release_hours * 1800
            rt.append(base + rng.uniform(0, p.release_hours * 3600, n))
            mass.append(np.full(n, c.frp_mw * scale / n))
            src.append(np.full(n, ci))
            proj.append(np.full(n, is_proj))
    if not rt:
        return (np.empty(0),) * 4
    return np.concatenate(rt), np.concatenate(mass), np.concatenate(src), np.concatenate(proj)


def simulate(clusters: list[FireCluster], wind: WindField, t0: float,
             p: ModelParams = PARAMS, receptors=RECEPTORS) -> TraceResult:
    rng = np.random.default_rng(p.seed)
    C, R, H = len(clusters), len(receptors), p.horizon_hours
    hours = t0 + 3600.0 * np.arange(H)
    dose = np.zeros((R, H)); by_src = np.zeros((R, C)); by_src_proj = np.zeros((R, C))
    snapshots: list[dict] = []

    rel_t, mass0, src, proj = _releases(clusters, t0, p, rng)
    if rel_t.size == 0:
        return TraceResult(t0, hours, dose, by_src, by_src_proj, snapshots, clusters)

    lat = np.array([clusters[i].lat for i in src]) + rng.normal(0, 0.02, src.size)
    lon = np.array([clusters[i].lon for i in src]) + rng.normal(0, 0.02, src.size)
    mass = mass0.copy()

    rlat = np.array([r.lat for r in receptors]); rlon = np.array([r.lon for r in receptors])
    radius_m = p.receptor_radius_km * 1000
    area_scale = 1000.0 / (np.pi * p.receptor_radius_km ** 2)   # mass per 1000 km^2
    dt = float(p.dt_seconds); dt_h = dt / 3600
    sigma = np.sqrt(2 * p.eddy_diffusivity_m2s * dt)
    decay = np.exp(-dt / (p.lifetime_hours * 3600))

    t_start = max(min(rel_t.min(), t0), wind.times[0])
    t = t0 - np.ceil((t0 - t_start) / dt) * dt   # step grid aligned to t0, so hour bins line up
    if t < wind.times[0]:
        t += dt
    t_end = min(t0 + H * 3600, wind.times[-1])
    next_snap = t0
    while t < t_end:
        active = rel_t <= t
        if active.any():
            a = np.flatnonzero(active)
            u, v = wind.sample(t, lat[a], lon[a])
            cosl = np.cos(np.deg2rad(lat[a]))
            dx = u * dt + rng.normal(0, sigma, a.size)
            dy = v * dt + rng.normal(0, sigma, a.size)
            lat[a] += dy / M_PER_DEG
            lon[a] += dx / (M_PER_DEG * cosl)
            mass[a] *= decay

            if t >= t0:
                h = int((t - t0) // 3600)
                cosr = np.cos(np.deg2rad(rlat))
                for ri in range(R):
                    dyr = (lat[a] - rlat[ri]) * M_PER_DEG
                    dxr = (lon[a] - rlon[ri]) * M_PER_DEG * cosr[ri]
                    inside = (dxr * dxr + dyr * dyr) < radius_m * radius_m
                    if not inside.any():
                        continue
                    ai = a[inside]
                    # time-integrated, area-normalised dose; hourly mean index
                    dose[ri, h] += mass[ai].sum() * area_scale * dt_h
                    by_src[ri] += np.bincount(src[ai], weights=mass[ai] * area_scale * dt_h, minlength=C)
                    pm = proj[ai]
                    if pm.any():
                        by_src_proj[ri] += np.bincount(src[ai][pm], weights=mass[ai][pm] * area_scale * dt_h,
                                                       minlength=C)

                if t >= next_snap:
                    sel = a if a.size <= 1500 else rng.choice(a, 1500, replace=False)
                    snapshots.append({
                        "t": int(t),
                        "points": np.column_stack([lat[sel].round(3), lon[sel].round(3),
                                                   (mass[sel] * 100).round(2)]).tolist(),
                    })
                    next_snap += 3 * 3600
        t += dt

    return TraceResult(t0, hours, dose, by_src, by_src_proj, snapshots, clusters)
