"""Gridded hourly wind fields from Open-Meteo (forecast or ERA5 archive)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests

from ..config import BBOX, WIND_GRID_RES
from .epoch import to_epoch_seconds

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Transport winds inside the mixed layer. The forecast API offers 10/80/120/180 m; the ERA5
# archive offers 10/100 m. 80 m and 100 m are close enough for smoke transport.
FORECAST_VARS = ("wind_speed_80m", "wind_direction_80m")
ARCHIVE_VARS = ("wind_speed_100m", "wind_direction_100m")
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
    archive = start_date is not None
    names = ARCHIVE_VARS if archive else FORECAST_VARS
    series = []
    for i in range(0, len(pts), CHUNK):
        chunk = pts[i:i + CHUNK]
        params = {
            "latitude": ",".join(f"{p[0]:.3f}" for p in chunk),
            "longitude": ",".join(f"{p[1]:.3f}" for p in chunk),
            "hourly": ",".join(names),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
        }
        if archive:
            params.update(start_date=start_date, end_date=end_date or start_date)
        else:
            params.update(past_days=past_days, forecast_days=forecast_days)
        r = requests.get(ARCHIVE_URL if archive else FORECAST_URL, params=params, timeout=120)
        if r.status_code >= 400:  # Open-Meteo explains errors in a JSON "reason"
            raise RuntimeError(f"Open-Meteo error {r.status_code}: {r.text[:300]}")
        data = r.json()
        series.extend(data if isinstance(data, list) else [data])
    return parse_series(series, lats, lons, names)


def parse_series(series: list[dict], lats: np.ndarray, lons: np.ndarray, names=FORECAST_VARS) -> WindField:
    """Open-Meteo multi-location JSON (one dict per grid point, row-major lat then lon) -> WindField."""
    if len(series) != len(lats) * len(lons):
        raise RuntimeError(f"Open-Meteo returned {len(series)} locations, expected {len(lats) * len(lons)}")
    times = to_epoch_seconds(pd.to_datetime(series[0]["hourly"]["time"], utc=True))
    nt, ny, nx = len(times), len(lats), len(lons)
    spd = np.array([s["hourly"][names[0]] for s in series], dtype=float).T.reshape(nt, ny, nx)
    drc = np.array([s["hourly"][names[1]] for s in series], dtype=float).T.reshape(nt, ny, nx)
    spd = np.nan_to_num(spd); drc = np.nan_to_num(drc)
    u, v = speed_dir_to_uv(spd, drc)
    return WindField(lats=lats, lons=lons, times=times.astype(float), u=u, v=v)
