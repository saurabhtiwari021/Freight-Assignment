"""Adversarial tests: inject a cost rise where a note must NOT justify it."""
from datetime import date, timedelta

import pytest

from costwatch.notes import load_notes
from costwatch.retrieval import TfidfRetriever
from costwatch.verdict import decide

NOTES = load_notes()
R = TfidfRetriever(NOTES)
D = date.fromisoformat


def v(route, week, rise=20.0):
    return decide(route, D(week), rise, R)


def test_correct_citation_is_made():
    assert v("Chennai-Bangalore", "2025-02-24").note_id == "N001"
    assert v("Chennai-Bangalore", "2025-03-03").note_id == "N001"     # week overlaps window end
    assert v("Ahmedabad-Mumbai", "2025-01-20").note_id == "N002"


def test_wrong_route_never_borrows_a_route_specific_note():
    assert v("Delhi-Jaipur", "2025-02-24").note_id is None            # N001 is Chennai-Bangalore
    assert v("Mumbai-Pune", "2025-01-20").note_id is None             # N002 is Ahmedabad-Mumbai


def test_right_route_wrong_window():
    assert v("Chennai-Bangalore", "2025-03-10").note_id is None       # flood window ended 8 Mar
    assert v("Chennai-Bangalore", "2025-03-17").note_id is None
    assert v("Chennai-Bangalore", "2025-02-17").note_id is None       # before the flood
    assert v("Ahmedabad-Mumbai", "2025-01-27").note_id is None        # festival week over


@pytest.mark.parametrize("route,week", [
    ("Mumbai-Delhi", "2024-07-29"),          # N005: costs not significantly affected
    ("Delhi-Jaipur", "2024-05-20"),          # N007: improved roads
    ("Kolkata-Bhubaneswar", "2025-06-09"),   # N008: no disruption
    ("Mumbai-Pune", "2025-09-22"),           # N006: stable demand
    ("Mumbai-Pune", "2024-03-11"),           # N004: toll plaza outside dataset
    ("Delhi-Chennai", "2025-10-27"),         # N010: no rate change
    ("Chennai-Bangalore", "2025-03-17"),     # N009: back to normal
])
def test_notes_that_say_no_cost_effect_never_justify(route, week):
    out = v(route, week)
    assert not out.justified and out.note_id is None


def test_diesel_note_applies_to_all_routes_within_window_and_magnitude():
    assert v("Delhi-Chennai", "2025-05-12", rise=6.0).note_id == "N003"
    assert v("Delhi-Chennai", "2025-05-12", rise=15.0).note_id is None    # far more than 5-7%
    assert v("Delhi-Chennai", "2025-04-28", rise=6.0).note_id is None     # week BEFORE the note date
    assert v("Delhi-Chennai", "2025-07-14", rise=6.0).note_id is None     # beyond the 8-week window


def test_no_note_means_unexplained_with_plain_message():
    out = v("Delhi-Jaipur", "2024-11-11")
    assert not out.justified and out.note_id is None
    assert "No matching note found" in out.reason


def test_sweep_every_route_and_week_justified_rows_always_pass_independent_rules():
    """Property test: across 7 routes x 2 years x several rise sizes, any justified
    verdict must satisfy route + window + effect, checked with hard-coded truth."""
    truth = {"N001": ({"Chennai-Bangalore"}, D("2025-02-24"), D("2025-03-08")),
             "N002": ({"Ahmedabad-Mumbai"}, D("2025-01-20"), D("2025-01-26")),
             "N003": (None, D("2025-05-05"), D("2025-06-29"))}           # None = all routes
    routes = ["Ahmedabad-Mumbai", "Chennai-Bangalore", "Delhi-Chennai", "Delhi-Jaipur",
              "Kolkata-Bhubaneswar", "Mumbai-Delhi", "Mumbai-Pune"]
    start, justified = D("2024-01-01"), 0
    for k in range(104):
        wk = start + timedelta(weeks=k)
        for route in routes:
            for rise in (6.0, 12.0, 30.0):
                out = v(route, wk.isoformat(), rise)
                if not out.justified:
                    assert out.note_id is None
                    continue
                justified += 1
                scope, lo, hi = truth[out.note_id]
                assert scope is None or route in scope
                assert lo <= wk + timedelta(days=6) and wk <= hi        # overlaps the week
    assert justified > 0
