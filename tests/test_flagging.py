import pandas as pd

from costwatch.flagging import is_candidate


def row(vh, vp):
    return pd.Series({"vs_history_pct": vh, "vs_peers_pct": vp})


def test_not_rising_is_never_flagged():
    assert not is_candidate(row(-20, 80))
    assert not is_candidate(row(0, 80))


def test_no_history_is_never_flagged():
    assert not is_candidate(row(float("nan"), 50))


def test_strong_rise_vs_own_history_flags():
    assert is_candidate(row(10.0, -5))
    assert not is_candidate(row(9.9, 0))


def test_modest_rise_needs_peer_confirmation():
    assert is_candidate(row(5.0, 20.0))
    assert not is_candidate(row(5.0, 19.9))
    assert not is_candidate(row(4.9, 50))
