"""AutoGluon (AWS open source) PM2.5 forecast on top of the smoke model, scored on the held-out month.

    pip install -r requirements-ml.txt
    py -m paralitrace.ml_forecast                 # adds AutoGluon rows to output/backtest.json

Each city's daily PM2.5 is a time series. AutoGluon-TimeSeries is trained on the first part of the
season only, with the smoke model's forecast for the next day as a known covariate (it is issued at
18:00 IST the evening before, so it is genuinely known in advance). On each held-out day it predicts
from the history up to the day before; nothing is refitted on held-out data. The same predictor trained
without the smoke covariate is the ablation. Results join the held-out table in backtest.json, scored
on exactly the same days and spike definition as the other methods.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .backtest import SPIKE_QUANTILE
from .config import OUTPUT_DIR

# Fixed in advance, not tuned on the held-out month: fast tabular and statistical models.
HYPERPARAMETERS = {"DirectTabular": {}, "RecursiveTabular": {}, "ETS": {}, "Theta": {}, "SeasonalNaive": {}}
SEED = 0


def season_frame(bt: dict) -> pd.DataFrame:
    rows = []
    for c in bt["cities"]:
        for d in c["days"]:
            rows.append({"item_id": c["id"], "timestamp": pd.Timestamp(d["date"]),
                         "pm25": d["observed_pm25"], "smoke": d["predicted_index"],
                         "smoke_spike": d["predicted_spike"], "observed_spike": d["observed_spike"]})
    df = pd.DataFrame(rows).sort_values(["item_id", "timestamp"]).reset_index(drop=True)
    df["pm25"] = df["pm25"].astype(float)
    # same spike threshold as the backtest: the city's season quantile of observed PM2.5
    df["thr"] = df.groupby("item_id")["pm25"].transform(lambda s: s.quantile(SPIKE_QUANTILE))
    return df


def _predictor(train: pd.DataFrame, with_smoke: bool, path: str):
    from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
    cols = ["item_id", "timestamp", "pm25"] + (["smoke"] if with_smoke else [])
    data = TimeSeriesDataFrame.from_data_frame(train[cols], id_column="item_id", timestamp_column="timestamp")
    pred = TimeSeriesPredictor(prediction_length=1, target="pm25", eval_metric="MAE", freq="D", path=path,
                               known_covariates_names=["smoke"] if with_smoke else None, verbosity=0)
    pred.fit(data, hyperparameters=HYPERPARAMETERS, random_seed=SEED, enable_ensemble=True)
    return pred


def rolling_forecast(df: pd.DataFrame, split: date, with_smoke: bool, path: str,
                     walk_forward: bool = True) -> pd.Series:
    """One-day-ahead PM2.5 forecast for every held-out day, from history up to the day before.
    walk_forward retrains each day on everything before it (standard expanding-window evaluation;
    the held-out day itself is never seen)."""
    from autogluon.timeseries import TimeSeriesDataFrame
    pred = _predictor(df[df.timestamp < pd.Timestamp(split)], with_smoke, path)
    out = {}
    cols = ["item_id", "timestamp", "pm25"] + (["smoke"] if with_smoke else [])
    for day in sorted(df.timestamp[df.timestamp >= pd.Timestamp(split)].unique()):
        hist = df[df.timestamp < day]
        if walk_forward and day > pd.Timestamp(split):
            pred = _predictor(hist, with_smoke, f"{path}_{pd.Timestamp(day):%m%d}")
        data = TimeSeriesDataFrame.from_data_frame(hist[cols], id_column="item_id", timestamp_column="timestamp")
        kwargs = {}
        if with_smoke:
            kc = df[df.timestamp == day][["item_id", "timestamp", "smoke"]]
            kwargs["known_covariates"] = TimeSeriesDataFrame.from_data_frame(kc, id_column="item_id",
                                                                             timestamp_column="timestamp")
        fc = pred.predict(data, **kwargs)["mean"]
        for (item, ts), v in fc.items():
            out[(item, pd.Timestamp(ts))] = float(v)
    return pd.Series(out)


def score_rows(df: pd.DataFrame, split: date, preds: dict[str, pd.Series]) -> list[dict]:
    """Score on the held-out filter used everywhere else: today's and yesterday's readings present and > 0."""
    d = df.copy()
    d["prev"] = d.groupby("item_id")["pm25"].shift(1)
    test = d[(d.timestamp >= pd.Timestamp(split)) & d.pm25.notna() & d.prev.notna() & (d.pm25 > 0) & (d.prev > 0)]
    spike = (test.pm25 >= test.thr).to_numpy()
    onset = spike & ~(test.prev >= test.thr).to_numpy()
    yest = (test.prev >= test.thr).to_numpy()
    smoke = test.smoke_spike.astype(bool).to_numpy()
    rows = []
    labels = {"autogluon_no_smoke": "AutoGluon on PM2.5 history only",
              "autogluon": "AutoGluon with the smoke model as input",
              "autogluon_combined": "AutoGluon + smoke alerts"}
    keys = list(zip(test.item_id, test.timestamp))
    for key, series in preds.items():
        yhat = np.array([series.get(k, np.nan) for k in keys])
        call = yhat >= test.thr.to_numpy()
        if key == "autogluon":
            calls = {"autogluon": call, "autogluon_combined": call | smoke}
        else:
            calls = {key: call}
        for k, c in calls.items():
            n = int(c.sum())
            rows.append({"key": k, "label": labels[k], "caught": int((c & spike).sum()),
                         "false_alarm_pct": round(100 * int((c & ~spike).sum()) / n) if n else 0,
                         "onsets_caught": int((c & onset).sum()),
                         "mae": None if k == "autogluon_combined" else round(float(np.nanmean(np.abs(test.pm25 - yhat))), 1)})
    return rows


def add_autogluon(bt: dict, workdir: str) -> dict:
    h = bt.get("heldout")
    if not h:
        raise SystemExit("The backtest has no held-out block to add to.")
    split = date.fromisoformat(h.get("test_start") or pd.Timestamp(pd.to_datetime(h["test"], format="%b %Y")).date().isoformat())
    df = season_frame(bt)
    logging.getLogger("autogluon").setLevel(logging.ERROR)
    preds = {
        "autogluon_no_smoke": rolling_forecast(df, split, False, os.path.join(workdir, "ag_no_smoke")),
        "autogluon": rolling_forecast(df, split, True, os.path.join(workdir, "ag_smoke")),
    }
    rows = score_rows(df, split, preds)
    h["methods"] = [m for m in h["methods"] if not m["key"].startswith("autogluon")] + rows
    h["autogluon"] = {"models": sorted(HYPERPARAMETERS), "first_trained_on": h["train"], "seed": SEED,
                      "walk_forward": True}
    return bt


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", default=os.path.join(OUTPUT_DIR, "backtest.json"))
    a = ap.parse_args()
    with open(a.file, encoding="utf-8") as f:
        bt = json.load(f)
    add_autogluon(bt, os.path.join(OUTPUT_DIR, "autogluon"))
    with open(a.file, "w", encoding="utf-8") as f:
        json.dump(bt, f)
    for m in bt["heldout"]["methods"]:
        print(f"  {m['label']:<42} caught {m['caught']:>3}  new spells {m['onsets_caught']:>3}  "
              f"false alarms {m['false_alarm_pct']:>3}%  error {m['mae']}")


if __name__ == "__main__":
    main()
