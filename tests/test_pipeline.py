import re

import pandas as pd

from costwatch import config as C
from costwatch.pipeline import OUTPUT_COLUMNS, run_pipeline


def test_columns_match_the_sample_contract_exactly():
    # header only: the sample's 3rd data row has an unquoted comma in `reason`
    sample_cols = C.SAMPLE_FORMAT_CSV.read_text().splitlines()[0].strip().split(",")
    assert OUTPUT_COLUMNS == sample_cols


def test_value_formats_match_sample():
    out, _ = run_pipeline()
    assert out.flagged.isin(["Yes", "No (justified)"]).all()
    assert out.vs_own_history.str.fullmatch(r"[+-]\d+\.\d% vs this route's past average").all()
    assert out.vs_similar_routes.str.fullmatch(r"[+-]\d+\.\d% vs similar-length routes this week").all()
    assert out.week_of.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert (pd.to_datetime(out.week_of).dt.weekday == 0).all()          # every week_of is a Monday


def test_note_id_column_is_consistent_with_verdict_and_prose():
    out, _ = run_pipeline()
    out = out.fillna("")
    just = out[out.flagged == "No (justified)"]
    assert (just.matched_note_id != "").all()
    assert all(n in r for n, r in zip(just.matched_note_id, just.reason))   # id also in the prose
    assert (out[out.flagged == "Yes"].matched_note_id == "").all()


def test_sample_rows_reproduce():
    out, _ = run_pipeline()
    r = out[(out.route == "Delhi-Jaipur") & (out.week_of == "2024-11-11")].iloc[0]
    assert r.cost_per_tonne_km == 4.17 and r.vs_own_history.startswith("+35.5%")
    assert r.vs_similar_routes.startswith("+21.0%") and r.flagged == "Yes"
    r = out[(out.route == "Ahmedabad-Mumbai") & (out.week_of == "2025-01-20")].iloc[0]
    assert r.vs_own_history.startswith("+29.5%") and r.vs_similar_routes.startswith("+22.5%")
    assert r.matched_note_id == "N002"
