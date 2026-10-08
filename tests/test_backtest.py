"""Backtest end to end with the network mocked in each service's documented response shape."""
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from paralitrace import backtest
from paralitrace.config import RECEPTORS

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight"
START, END = "2025-11-01", "2025-11-12"


class Resp:
    def __init__(self, text="", payload=None, status=200):
        self.text, self._p, self.status_code = text, payload, status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def firms_archive(url: str) -> str:
    d0 = date.fromisoformat(url.rsplit("/", 1)[1])
    rng = np.random.default_rng(d0.toordinal())
    rows = []
    for k in range(5):                          # DATE .. DATE+4
        d = d0 + timedelta(k)
        n = 40 + 30 * (d.day % 4)               # burning varies day to day
        for i in range(n):
            rows.append(f"{30.25 + rng.normal(0, .3):.4f},{75.8 + rng.normal(0, .4):.4f},330,0.4,0.5,"
                        f"{d},0820,N,{'nhl'[i % 3]},2,290,{rng.uniform(2, 25):.2f},D")
    return HEADER + "\n" + "\n".join(rows)


def era5(params) -> list[dict]:
    assert params["hourly"] == "wind_speed_100m,wind_direction_100m"
    d0, d1 = date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
    hours = 24 * ((d1 - d0).days + 1)
    times = [(datetime(d0.year, d0.month, d0.day) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours)]
    n = len(params["latitude"].split(","))
    return [{"hourly": {"time": times, "wind_speed_100m": [3.0] * hours, "wind_direction_100m": [305.0] * hours}}
            for _ in range(n)]


def openaq(path, params):
    if path.endswith("/locations"):
        lat = float(params["coordinates"].split(",")[0])
        sid = int(lat * 1000)
        return {"results": [{"id": sid, "name": "Station", "datetimeFirst": {"utc": "2019-01-01T00:00:00Z"},
                             "datetimeLast": {"utc": "2026-10-01T00:00:00Z"},
                             "sensors": [{"id": sid, "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"}},
                                         {"id": sid + 1, "parameter": {"id": 1, "name": "pm10", "units": "µg/m³"}}]}]}
    sid = int(path.split("/")[2])
    rng = np.random.default_rng(sid)
    res = []
    for k in range(12):
        d = date(2025, 11, 1) + timedelta(k)
        res.append({"value": float(80 + 25 * (d.day % 4) + rng.normal(0, 10)),
                    "period": {"datetimeFrom": {"utc": f"{d - timedelta(1)}T18:30:00Z", "local": f"{d}T00:00:00+05:30"}},
                    "coverage": {"percentComplete": 30.0 if k == 5 else 95.0}})
    return {"results": res}


@pytest.fixture
def mocked(monkeypatch, tmp_path):
    def get(url, params=None, timeout=None):
        if "/api/area/csv/" in url:
            return Resp(text=firms_archive(url))
        if "archive-api.open-meteo" in url:
            return Resp(payload=era5(params))
        raise AssertionError(url)

    def session_get(self, url, params=None, timeout=None):
        return Resp(payload=openaq(url.replace(backtest.OPENAQ, ""), params))

    monkeypatch.setattr("requests.get", get)
    monkeypatch.setattr("requests.Session.get", session_get)
    monkeypatch.setattr(backtest, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(backtest.time, "sleep", lambda s: None)
    monkeypatch.setenv("FIRMS_MAP_KEY", "k")
    monkeypatch.setenv("OPENAQ_API_KEY", "k")
    return tmp_path


def test_backtest_document_matches_the_proof_tab_contract(mocked):
    doc = backtest.run(START, END)
    assert set(doc) >= {"season", "start", "end", "lead_hours", "spike_definition", "summary", "cities"}
    s = doc["summary"]
    assert set(s) >= {"spike_days", "spikes_caught", "hit_rate_pct", "false_alarm_pct", "median_correlation",
                      "baseline_label", "baseline_hit_rate_pct"}
    assert 0 <= s["spikes_caught"] <= s["spike_days"]
    assert 0 <= s["hit_rate_pct"] <= 100 and 0 <= s["baseline_hit_rate_pct"] <= 100
    c = doc["cities"][0]
    assert set(c) == {"id", "name", "spike_days", "spikes_caught", "false_alarms", "correlation", "days"}
    assert len(c["days"]) == 12
    assert set(c["days"][0]) == {"date", "predicted_index", "observed_pm25", "observed_spike", "predicted_spike"}
    assert c["days"][5]["observed_pm25"] is None          # low-coverage day dropped
    assert (mocked / "backtest.json").exists()


def test_rerun_uses_the_cache(mocked, monkeypatch):
    backtest.run(START, END)
    monkeypatch.setattr("requests.get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    monkeypatch.setattr("requests.Session.get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    backtest.run(START, END)


def test_missing_keys_explained(monkeypatch):
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="FIRMS_MAP_KEY and OPENAQ_API_KEY"):
        backtest.run(START, END)


def test_spearman():
    assert backtest.spearman(list(range(10)), [x * x for x in range(10)]) == pytest.approx(1.0)
    assert backtest.spearman([1, 2], [3, 4]) is None
