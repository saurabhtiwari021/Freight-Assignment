import pandas as pd
import pytest

from costwatch.metrics import add_baselines, monday_of, weekly_cost


def _ship(route, rtype, date, qty, km, cost, i=[0]):
    i[0] += 1
    o, d = route.split("-")
    return dict(shipment_id=f"S{i[0]}", origin=o, destination=d, route=route, route_type=rtype,
                quantity_tonnes=qty, distance_km=km, freight_cost_inr=cost, shipment_date=pd.Timestamp(date))


def test_weeks_run_monday_to_sunday():
    s = pd.Series(pd.to_datetime(["2024-01-01", "2024-01-07", "2024-01-08"]))  # Mon, Sun, Mon
    assert monday_of(s).dt.strftime("%Y-%m-%d").tolist() == ["2024-01-01", "2024-01-01", "2024-01-08"]


def test_weekly_value_is_ratio_of_sums_not_mean_of_ratios():
    df = pd.DataFrame([_ship("A-B", "Short", "2024-01-01", 10, 100, 3000),    # 3.0 per tkm
                       _ship("A-B", "Short", "2024-01-03", 20, 100, 8000)])   # 4.0 per tkm
    w = weekly_cost(df)
    assert w.loc[0, "cost_per_tonne_km"] == pytest.approx(11000 / 3000)       # 3.667, not 3.5


def _series(route, values, rtype="Short"):
    rows = [_ship(route, rtype, pd.Timestamp("2024-01-01") + pd.Timedelta(weeks=k), 10, 100, v * 1000)
            for k, v in enumerate(values)]
    return rows


def test_history_is_strictly_prior_and_uses_available_weeks_when_fewer_than_8():
    w = add_baselines(weekly_cost(pd.DataFrame(_series("A-B", [1, 2, 3, 10]))))
    assert pd.isna(w.loc[0, "hist_mean"])                       # first week: no history
    assert w.loc[1, "hist_mean"] == pytest.approx(1.0)
    assert w.loc[3, "hist_mean"] == pytest.approx(2.0)          # mean(1,2,3); the 10 is excluded
    assert w.loc[3, "hist_weeks"] == 3
    assert w.loc[3, "vs_history_pct"] == pytest.approx((10 / 2 - 1) * 100)


def test_history_window_is_eight_weeks():
    w = add_baselines(weekly_cost(pd.DataFrame(_series("A-B", [100] * 5 + [1] * 8 + [9]))))
    assert w.loc[13, "hist_mean"] == pytest.approx(1.0)         # the 100s fell out of the window
    assert w.loc[13, "hist_weeks"] == 8


def test_no_lookahead():
    base = _series("A-B", [1, 2, 3, 4, 5])
    a = add_baselines(weekly_cost(pd.DataFrame(base)))
    b = add_baselines(weekly_cost(pd.DataFrame(base + _series("A-B", [0] * 0) )))
    changed = [dict(r) for r in base]; changed[4]["freight_cost_inr"] = 999_000   # alter only the LAST week
    c = add_baselines(weekly_cost(pd.DataFrame(changed)))
    assert a.loc[:3, "hist_mean"].fillna(-1).tolist() == c.loc[:3, "hist_mean"].fillna(-1).tolist()


def test_peer_average_excludes_self_and_matches_route_type_only():
    df = pd.DataFrame(_series("A-B", [2], "Short") + _series("C-D", [4], "Short")
                      + _series("E-F", [6], "Short") + _series("G-H", [100], "Long"))
    w = add_baselines(weekly_cost(df)).set_index("route")
    assert w.loc["A-B", "peer_mean"] == pytest.approx((4 + 6) / 2)
    assert w.loc["C-D", "peer_mean"] == pytest.approx((2 + 6) / 2)
    assert pd.isna(w.loc["G-H", "peer_mean"])                    # only Long route: no peers
