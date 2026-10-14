"""Decide which route-weeks are 'rising and out of the ordinary'."""
from __future__ import annotations

import pandas as pd

from . import config as C


def is_candidate(row: pd.Series) -> bool:
    """Pure function of one weekly row, so it is trivial to unit-test."""
    vh, vp = row["vs_history_pct"], row["vs_peers_pct"]
    if pd.isna(vh) or vh <= 0:               # no history yet, or not rising
        return False
    strong = vh >= C.HIST_PCT_STRONG
    modest = vh >= C.HIST_PCT_MODEST and pd.notna(vp) and vp >= C.PEER_PCT_MODEST
    return bool(strong or modest)


def candidates(weekly: pd.DataFrame) -> pd.DataFrame:
    mask = weekly.apply(is_candidate, axis=1)
    return weekly[mask].reset_index(drop=True)
