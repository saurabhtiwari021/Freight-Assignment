"""Weekly cost-per-tonne-km and the two comparison baselines.

Definitions follow the brief exactly:
  cost_per_tonne_km = SUM(freight_cost) / SUM(quantity_tonnes * distance_km)
  vs own history    = trailing 8-week mean of weekly values, weeks STRICTLY
                      BEFORE the current week; fewer weeks -> use what exists.
  vs similar routes = mean of the other routes' weekly value (same week, same
                      route_type); the route itself is excluded.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

REQUIRED_COLS = [
    "shipment_id", "origin", "destination", "route_type", "quantity_tonnes",
    "distance_km", "freight_cost_inr", "shipment_date",
]


def load_shipments(path=config.SHIPMENTS_CSV) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = set(REQUIRED_COLS) - set(df.columns)
    if missing:
        raise ValueError(f"shipment file missing columns: {sorted(missing)}")
    df["shipment_date"] = pd.to_datetime(df["shipment_date"])
    for col in ("quantity_tonnes", "distance_km", "freight_cost_inr"):
        if (df[col] <= 0).any() or df[col].isna().any():
            raise ValueError(f"non-positive or missing values in {col}")
    df["route"] = df["origin"].str.strip() + "-" + df["destination"].str.strip()
    return df


def monday_of(dates: pd.Series) -> pd.Series:
    """Monday (00:00) of each date's Monday-Sunday week."""
    d = pd.to_datetime(dates).dt.normalize()
    return d - pd.to_timedelta(d.dt.weekday, unit="D")


def weekly_cost(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (route, route_type, week_of) with cost per tonne-km."""
    d = df.copy()
    d["week_of"] = monday_of(d["shipment_date"])
    d["tonne_km"] = d["quantity_tonnes"] * d["distance_km"]
    w = (
        d.groupby(["route", "route_type", "week_of"], as_index=False)
        .agg(total_cost=("freight_cost_inr", "sum"),
             tonne_km=("tonne_km", "sum"),
             n_shipments=("shipment_id", "count"))
    )
    w["cost_per_tonne_km"] = w["total_cost"] / w["tonne_km"]
    return w.sort_values(["route", "week_of"]).reset_index(drop=True)


def add_baselines(w: pd.DataFrame, window: int = config.HISTORY_WINDOW_WEEKS) -> pd.DataFrame:
    """Add own-history and peer baselines (no look-ahead) to weekly rows."""
    w = w.sort_values(["route", "week_of"]).reset_index(drop=True).copy()

    # own history: shift(1) so the current week is never in its own baseline
    g = w.groupby("route")["cost_per_tonne_km"]
    w["hist_mean"] = g.transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
    w["hist_std"] = g.transform(lambda s: s.shift(1).rolling(window, min_periods=2).std())
    w["hist_weeks"] = g.transform(lambda s: s.shift(1).rolling(window, min_periods=1).count())

    # peers: (sum of type-week values - own value) / (count - 1)
    grp = w.groupby(["route_type", "week_of"])["cost_per_tonne_km"]
    tot, cnt = grp.transform("sum"), grp.transform("count")
    w["peer_mean"] = np.where(cnt > 1, (tot - w["cost_per_tonne_km"]) / (cnt - 1).clip(lower=1), np.nan)
    w["peer_routes"] = (cnt - 1)

    w["vs_history_pct"] = (w["cost_per_tonne_km"] / w["hist_mean"] - 1) * 100
    w["vs_peers_pct"] = (w["cost_per_tonne_km"] / w["peer_mean"] - 1) * 100
    w["z_score"] = (w["cost_per_tonne_km"] - w["hist_mean"]) / w["hist_std"]
    return w
