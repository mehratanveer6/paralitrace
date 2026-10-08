"""Live pipeline against the real wire formats, with the network mocked.

The CSV header and confidence words match NASA's public South Asia VIIRS files; the wind JSON
matches Open-Meteo's multi-location response (a list with one object per coordinate).
"""
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from paralitrace import pipeline
from paralitrace.data import fires as fires_mod

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight"


class FakeResponse:
    def __init__(self, text="", payload=None, status=200):
        self.text, self._payload, self.status_code = text, payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def firms_csv(now: datetime, stale: bool = False) -> str:
    rng = np.random.default_rng(1)
    rows = []
    for i in range(60):
        when = now - timedelta(days=30 if stale else 0, hours=int(rng.integers(2, 20)))
        conf = ["nominal", "high", "low"][i % 3]
        rows.append(f"{30.2 + rng.normal(0, .3):.5f},{75.6 + rng.normal(0, .4):.5f},330.1,0.4,0.5,"
                    f"{when:%Y-%m-%d},{when:%H%M},N,{conf},2.0NRT,290.2,{rng.uniform(2, 30):.2f},D")
    rows.append("24.12,97.72,326.17,0.53,0.67,2026-10-07,0559,N,nominal,2.0NRT,288.02,2.89,D")  # Myanmar: outside bbox
    return HEADER + "\n" + "\n".join(rows) + "\n"


def open_meteo(params) -> list[dict]:
    lats = params["latitude"].split(","); lons = params["longitude"].split(",")
    assert len(lats) == len(lons)
    speed_key = next(v for v in params["hourly"].split(",") if v.startswith("wind_speed"))
    dir_key = next(v for v in params["hourly"].split(",") if v.startswith("wind_direction"))
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=params["past_days"])
    hours = 24 * (params["past_days"] + params["forecast_days"])
    times = [(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours)]
    return [{"latitude": float(a), "longitude": float(b), "hourly_units": {},
             "hourly": {"time": times, speed_key: [3.0] * hours, dir_key: [310.0] * hours}}
            for a, b in zip(lats, lons)]


@pytest.fixture
def fake_net(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    calls = []

    def get(url, params=None, timeout=None):
        calls.append(url)
        if "open-meteo" in url:
            assert params["hourly"] == "wind_speed_80m,wind_direction_80m"  # the forecast API has no 100 m wind
            return FakeResponse(payload=open_meteo(params))
        if "J2_" in url:
            return FakeResponse(status=503)                    # one satellite down
        if "SUOMI" in url:
            return FakeResponse(text=firms_csv(now, stale=True))  # a stale file
        return FakeResponse(text=firms_csv(now))

    monkeypatch.setattr("requests.get", get)
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    return calls, tmp_path


def test_public_fire_files_parse_filter_and_freshness(fake_net):
    df = fires_mod.fetch_firms_public("48h")
    assert len(df) > 0
    assert df.latitude.between(27.8, 32.6).all()       # Myanmar row dropped
    assert df.t_epoch.min() >= df.t_epoch.max() - 36 * 3600  # stale SUOMI rows dropped
    assert len(df) == 40                                # 60 J1 rows minus 20 'low'; SUOMI stale; J2 down


def test_live_pipeline_end_to_end_without_a_key(fake_net):
    calls, out = fake_net
    r = pipeline.run("live", out_dir=str(out))
    assert r["meta"]["mode"] == "live"
    assert r["meta"]["fire_detections"] == 40
    assert "NASA FIRMS VIIRS" in r["meta"]["data_label"]
    assert len(r["plumes"]) == 16
    assert any(c["day1_mean"] > 0 for c in r["cities"])   # north-westerly carries Sangrur smoke somewhere
    assert json.load(open(out / "latest.json"))["meta"]["mode"] == "live"
    assert sum("open-meteo" in u for u in calls) == 2      # 90 grid points in chunks of 50


def test_all_fire_files_down_is_a_clear_error(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse(status=503))
    with pytest.raises(RuntimeError, match="Could not download any FIRMS fire file"):
        fires_mod.fetch_firms_public()
