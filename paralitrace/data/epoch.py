"""Unit-safe datetime -> UTC epoch seconds.

pandas 3 may store datetimes in microseconds instead of nanoseconds, so `astype("int64") // 10**9`
silently gives wrong answers. Subtracting the epoch and dividing by one second works in any unit.
"""
import numpy as np
import pandas as pd

_EPOCH = pd.Timestamp(0, tz="UTC")


def to_epoch_seconds(ts) -> np.ndarray:
    """Accepts a tz-aware Series or DatetimeIndex; returns int64 seconds since 1970-01-01 UTC."""
    return np.asarray((ts - _EPOCH) // pd.Timedelta(seconds=1), dtype=np.int64)
