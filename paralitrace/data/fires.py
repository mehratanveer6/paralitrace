"""Active-fire detections from NASA FIRMS, clustered into ~10 km burn cells."""
from __future__ import annotations

import io
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from ..config import BBOX, PARAMS

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/{days}"
NRT_SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
ARCHIVE_SOURCES = ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP")


@dataclass
class FireCluster:
    id: str
    lat: float          # FRP-weighted centroid
    lon: float
    frp_mw: float       # summed fire radiative power, proxy for emissions
    n_fires: int        # detections in the cell, proxy for machines needed
    t_epoch: float      # mean detection time (UTC epoch seconds)

    def to_dict(self) -> dict:
        return asdict(self)


def fetch_firms(map_key: str, days: int = 1, date: str | None = None,
                sources: tuple[str, ...] = NRT_SOURCES, bbox=BBOX) -> pd.DataFrame:
    """Fetch VIIRS detections inside bbox. date='YYYY-MM-DD' pulls history (use ARCHIVE_SOURCES)."""
    lat_min, lat_max, lon_min, lon_max = bbox
    area = f"{lon_min},{lat_min},{lon_max},{lat_max}"
    frames = []
    for src in sources:
        url = FIRMS_URL.format(key=map_key, source=src, area=area, days=days)
        if date:
            url += f"/{date}"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        if not r.text.strip() or r.text.lower().startswith("invalid"):
            raise RuntimeError(f"FIRMS error for {src}: {r.text[:200]}")
        df = pd.read_csv(io.StringIO(r.text))
        if len(df):
            df["source"] = src
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["latitude", "longitude", "frp", "acq_date", "acq_time", "confidence"])
    return normalise(pd.concat(frames, ignore_index=True))


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Drop low-confidence pixels, add UTC epoch time."""
    df = df.copy()
    if "confidence" in df:
        df = df[df["confidence"].astype(str).str.lower() != "l"]
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    ts = pd.to_datetime(df["acq_date"] + " " + hhmm, format="%Y-%m-%d %H%M", utc=True)
    df["t_epoch"] = ts.astype("int64") // 10**9
    return df[["latitude", "longitude", "frp", "t_epoch"]].dropna().reset_index(drop=True)


def cluster_fires(df: pd.DataFrame, res_deg: float = PARAMS.cluster_res_deg) -> list[FireCluster]:
    """Grid detections into res_deg cells. Each cell becomes one emission source."""
    if df.empty:
        return []
    d = df.copy()
    d["frp"] = d["frp"].clip(lower=0.5)
    d["gy"] = np.floor(d["latitude"] / res_deg).astype(int)
    d["gx"] = np.floor(d["longitude"] / res_deg).astype(int)
    out = []
    for (gy, gx), g in d.groupby(["gy", "gx"]):
        w = g["frp"].to_numpy()
        out.append(FireCluster(
            id=f"c{gy}_{gx}",
            lat=float(np.average(g["latitude"], weights=w)),
            lon=float(np.average(g["longitude"], weights=w)),
            frp_mw=float(w.sum()),
            n_fires=int(len(g)),
            t_epoch=float(g["t_epoch"].mean()),
        ))
    out.sort(key=lambda c: -c.frp_mw)
    return out


def now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()
