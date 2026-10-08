"""Gridded hourly wind fields from Open-Meteo (forecast or ERA5 archive)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests

from ..config import BBOX, WIND_GRID_RES

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
LEVEL_VARS = ("wind_speed_100m", "wind_direction_100m")  # transport within the mixed layer
CHUNK = 50  # locations per request


@dataclass
class WindField:
    lats: np.ndarray    # (ny,) ascending
    lons: np.ndarray    # (nx,) ascending
    times: np.ndarray   # (nt,) UTC epoch seconds, ascending
    u: np.ndarray       # (nt, ny, nx) eastward m/s
    v: np.ndarray       # (nt, ny, nx) northward m/s

    def sample(self, t: float, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Linear in time, bilinear in space. Positions outside the grid are clamped to its edge."""
        ti = np.interp(t, self.times, np.arange(len(self.times)))
        t0 = int(np.floor(ti)); t1 = min(t0 + 1, len(self.times) - 1); ft = ti - t0
        yi = np.clip(np.interp(lat, self.lats, np.arange(len(self.lats))), 0, len(self.lats) - 1)
        xi = np.clip(np.interp(lon, self.lons, np.arange(len(self.lons))), 0, len(self.lons) - 1)
        y0 = np.floor(yi).astype(int); x0 = np.floor(xi).astype(int)
        y1 = np.minimum(y0 + 1, len(self.lats) - 1); x1 = np.minimum(x0 + 1, len(self.lons) - 1)
        fy = yi - y0; fx = xi - x0

        def bil(f):
            return ((f[y0, x0] * (1 - fx) + f[y0, x1] * fx) * (1 - fy)
                    + (f[y1, x0] * (1 - fx) + f[y1, x1] * fx) * fy)

        u = bil(self.u[t0]) * (1 - ft) + bil(self.u[t1]) * ft
        v = bil(self.v[t0]) * (1 - ft) + bil(self.v[t1]) * ft
        return u, v

    def to_json(self, every: int = 3) -> dict:
        """Downsampled field for the map's wind arrows."""
        idx = list(range(0, len(self.times), every))
        return {"lats": self.lats.round(3).tolist(), "lons": self.lons.round(3).tolist(),
                "times": [int(self.times[i]) for i in idx],
                "u": [self.u[i].round(2).tolist() for i in idx],
                "v": [self.v[i].round(2).tolist() for i in idx]}


def grid(bbox=BBOX, res=WIND_GRID_RES):
    lat_min, lat_max, lon_min, lon_max = bbox
    return np.arange(lat_min, lat_max + 1e-9, res), np.arange(lon_min, lon_max + 1e-9, res)


def speed_dir_to_uv(speed, direction_deg):
    """Meteorological direction = where wind blows FROM."""
    rad = np.deg2rad(direction_deg)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def fetch_open_meteo(start_date: str | None = None, end_date: str | None = None,
                     past_days: int = 1, forecast_days: int = 3, bbox=BBOX) -> WindField:
    """Forecast mode by default; pass start_date/end_date (YYYY-MM-DD) for the ERA5 archive."""
    lats, lons = grid(bbox)
    pts = [(la, lo) for la in lats for lo in lons]
    series = []
    for i in range(0, len(pts), CHUNK):
        chunk = pts[i:i + CHUNK]
        params = {
            "latitude": ",".join(f"{p[0]:.3f}" for p in chunk),
            "longitude": ",".join(f"{p[1]:.3f}" for p in chunk),
            "hourly": ",".join(LEVEL_VARS),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
        }
        if start_date:
            params.update(start_date=start_date, end_date=end_date or start_date)
            url = ARCHIVE_URL
        else:
            params.update(past_days=past_days, forecast_days=forecast_days)
            url = FORECAST_URL
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        series.extend(data if isinstance(data, list) else [data])

    times = pd.to_datetime(series[0]["hourly"]["time"], utc=True).astype("int64").to_numpy() // 10**9
    nt, ny, nx = len(times), len(lats), len(lons)
    spd = np.array([s["hourly"][LEVEL_VARS[0]] for s in series], dtype=float).T.reshape(nt, ny, nx)
    drc = np.array([s["hourly"][LEVEL_VARS[1]] for s in series], dtype=float).T.reshape(nt, ny, nx)
    spd = np.nan_to_num(spd); drc = np.nan_to_num(drc)
    u, v = speed_dir_to_uv(spd, drc)
    return WindField(lats=lats, lons=lons, times=times.astype(float), u=u, v=v)
