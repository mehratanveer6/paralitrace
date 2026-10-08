"""Seeded synthetic fires and winds for offline development and tests.

Shapes match the live clients. Fire hotspots follow the districts that dominate
post-monsoon burning; winds mimic the typical Oct-Nov north-westerly regime.
Never present synthetic output as observed data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import BBOX
from .winds import WindField, grid, speed_dir_to_uv

HOTSPOTS = [  # (lat, lon, relative intensity)
    (30.25, 75.84, 1.0),   # Sangrur
    (30.38, 75.55, 0.7),   # Barnala
    (30.21, 74.95, 0.8),   # Bathinda
    (29.99, 75.40, 0.6),   # Mansa
    (30.82, 75.17, 0.7),   # Moga
    (30.92, 74.61, 0.9),   # Ferozepur
    (31.45, 74.92, 0.8),   # Tarn Taran
    (30.34, 76.39, 0.6),   # Patiala
    (29.80, 76.40, 0.5),   # Kaithal
    (29.32, 76.31, 0.4),   # Jind
    (29.52, 75.45, 0.4),   # Fatehabad
]


def synthetic_fires(t_ref: float, n: int = 900, seed: int = 7) -> pd.DataFrame:
    """Detections around afternoon overpass (~08:00 UTC = 13:30 IST) the day before t_ref."""
    rng = np.random.default_rng(seed)
    w = np.array([h[2] for h in HOTSPOTS]); w = w / w.sum()
    idx = rng.choice(len(HOTSPOTS), size=n, p=w)
    lat = np.array([HOTSPOTS[i][0] for i in idx]) + rng.normal(0, 0.18, n)
    lon = np.array([HOTSPOTS[i][1] for i in idx]) + rng.normal(0, 0.22, n)
    frp = rng.lognormal(mean=1.8, sigma=0.8, size=n)  # MW, heavy tail like real VIIRS
    day0 = np.floor(t_ref / 86400) * 86400 - 86400
    t = day0 + 8 * 3600 + rng.normal(0, 1800, n)
    return pd.DataFrame({"latitude": lat, "longitude": lon, "frp": frp, "t_epoch": t})


def synthetic_winds(t_start: float, hours: int = 96, seed: int = 11, bbox=BBOX) -> WindField:
    rng = np.random.default_rng(seed)
    lats, lons = grid(bbox)
    times = t_start + 3600.0 * np.arange(hours)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    # Flow turns from westerly (north) to north-westerly (south-east, towards Delhi).
    base_dir = 300 + 12 * (bbox[1] - LA) / (bbox[1] - bbox[0]) + 6 * (LO - bbox[2]) / (bbox[3] - bbox[2])
    u = np.empty((hours, len(lats), len(lons))); v = np.empty_like(u)
    phase = rng.uniform(0, 2 * np.pi)
    for k, t in enumerate(times):
        hour_ist = ((t / 3600) + 5.5) % 24
        diurnal = 1.6 + 1.4 * max(0.0, np.sin(np.pi * (hour_ist - 8) / 12))   # stronger by day
        synoptic = 1.0 + 0.25 * np.sin(2 * np.pi * k / 60 + phase)             # slow modulation
        spd = diurnal * synoptic + rng.normal(0, 0.15, LA.shape)
        drc = base_dir + 10 * np.sin(2 * np.pi * k / 36 + phase) + rng.normal(0, 4, LA.shape)
        u[k], v[k] = speed_dir_to_uv(np.clip(spd, 0.2, None), drc)
    return WindField(lats=lats, lons=lons, times=times, u=u, v=v)
