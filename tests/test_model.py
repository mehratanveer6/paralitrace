import numpy as np
import pytest

from paralitrace.config import RECEPTORS, ModelParams
from paralitrace.data.fires import FireCluster, cluster_fires
from paralitrace.data.winds import WindField, speed_dir_to_uv
from paralitrace.model.analysis import city_forecasts, plan_interventions
from paralitrace.model.tracer import simulate

T0 = 1_791_000_000.0
QUIET = ModelParams(eddy_diffusivity_m2s=0.0, lifetime_hours=1e9, persistence=0.0,
                    particles_per_cluster=20, release_hours=0.5, horizon_hours=24)


def uniform_wind(u, v, hours=72):
    lats, lons = np.arange(27.0, 33.01, 0.5), np.arange(73.0, 79.01, 0.5)
    shape = (hours, len(lats), len(lons))
    return WindField(lats, lons, T0 - 24 * 3600 + 3600.0 * np.arange(hours),
                     np.full(shape, float(u)), np.full(shape, float(v)))


def test_wind_direction_convention():
    u, v = speed_dir_to_uv(np.array(5.0), np.array(270.0))  # westerly blows towards east
    assert u == pytest.approx(5.0) and v == pytest.approx(0.0, abs=1e-9)
    u, v = speed_dir_to_uv(np.array(5.0), np.array(0.0))    # northerly blows south
    assert v == pytest.approx(-5.0)


def test_downwind_city_gets_smoke_upwind_city_does_not():
    # Fire 60 km west of Delhi, wind blowing east at 3 m/s: Delhi exposed, Rohtak (upwind) not.
    fire = FireCluster("f", 28.6139, 77.2090 - 60 / (111.32 * np.cos(np.deg2rad(28.61))), 100.0, 10, T0)
    tr = simulate([fire], uniform_wind(3.0, 0.0), T0, QUIET)
    ri = {r.id: i for i, r in enumerate(RECEPTORS)}
    assert tr.dose[ri["delhi"]].sum() > 0
    assert tr.dose[ri["rohtak"]].sum() == 0
    # Travel time ~ 60 km / 3 m/s = 5.6 h; arrival should be within a couple of hours of that.
    first = np.flatnonzero(tr.dose[ri["delhi"]] > 0)[0]
    assert 3 <= first <= 8


def test_attribution_shares_sum_to_100():
    fires = [FireCluster("a", 29.0, 76.0, 50, 5, T0), FireCluster("b", 28.9, 76.2, 80, 8, T0)]
    tr = simulate(fires, uniform_wind(2.5, -0.5), T0, ModelParams(horizon_hours=36))
    for c in city_forecasts(tr):
        if c["top_sources"]:
            assert sum(s["share_pct"] for s in c["top_sources"]) == pytest.approx(100, abs=0.5)


def test_plan_respects_budget_and_beats_or_matches_naive():
    rng = np.random.default_rng(0)
    fires = [FireCluster(f"c{i}", 29.5 + rng.uniform(0, 1.5), 74.5 + rng.uniform(0, 2), rng.uniform(5, 200),
                         int(rng.integers(1, 12)), T0 - 6 * 3600) for i in range(40)]
    tr = simulate(fires, uniform_wind(2.0, -1.5, hours=96), T0, ModelParams(horizon_hours=48))
    p = plan_interventions(tr, budget_fires=60)
    assert p["fires_targeted"] <= 60
    assert p["exposure_avoided_pct_of_preventable"] >= p["naive_biggest_fires_pct_of_preventable"]


def test_clustering_conserves_frp():
    import pandas as pd
    df = pd.DataFrame({"latitude": [30.01, 30.02, 30.5], "longitude": [75.01, 75.03, 75.5],
                       "frp": [3.0, 5.0, 10.0], "t_epoch": [T0] * 3})
    cl = cluster_fires(df)
    assert len(cl) == 2
    assert sum(c.frp_mw for c in cl) == pytest.approx(18.0)


def test_timeline_has_every_frame_even_without_fires():
    p = ModelParams(horizon_hours=48)
    for fires in ([], [FireCluster("a", 30.0, 75.5, 40, 4, T0)]):
        tr = simulate(fires, uniform_wind(2.0, -1.0, hours=96), T0, p)
        assert [s["t"] for s in tr.snapshots] == [int(T0 + 3 * 3600 * k) for k in range(16)]
