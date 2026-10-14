"""Mutation tests: deliberately break the verdict rules and prove the eval notices."""
import importlib.util
from pathlib import Path

import pytest

from costwatch import verdict

EVAL = Path(__file__).resolve().parent.parent / "eval" / "run_eval.py"


def run_eval_main():
    spec = importlib.util.spec_from_file_location("run_eval", EVAL)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.main()


def test_baseline_passes():
    assert run_eval_main() == 0


@pytest.mark.parametrize("broken", ["ignore_window", "ignore_effect"])
def test_eval_fails_when_a_guardrail_is_removed(monkeypatch, broken):
    real = verdict.check_note

    def mutant(note, route, week_start, vs):
        if broken == "ignore_window":
            gap = verdict.window_gap_days
            monkeypatch.setattr(verdict, "window_gap_days", lambda n, w: (0, "overlaps"), raising=True)
            try:
                return real(note, route, week_start, vs)
            finally:
                monkeypatch.setattr(verdict, "window_gap_days", gap)
        if broken == "ignore_effect":
            from dataclasses import replace
            return real(replace(note, effect="raises_cost"), route, week_start, vs)
    monkeypatch.setattr(verdict, "check_note", mutant)
    assert run_eval_main() == 1, f"eval failed to detect mutation: {broken}"


def test_route_guard_is_defended_twice_and_caught_by_adversarial_tests(monkeypatch):
    """The real flagged weeks have no cross-route note collisions, so the labeled eval
    cannot detect a route bug; the injected adversarial tests in test_verdict.py do.
    Prove that by removing BOTH route layers (retriever filter + check_note)."""
    from datetime import date
    from costwatch.notes import Note, load_notes
    from costwatch.retrieval import TfidfRetriever
    r = TfidfRetriever(load_notes())
    assert not verdict.decide("Delhi-Jaipur", date(2025, 2, 24), 20.0, r).justified   # healthy
    monkeypatch.setattr(Note, "covers_route", lambda self, route: True)
    r2 = TfidfRetriever(load_notes())
    assert verdict.decide("Delhi-Jaipur", date(2025, 2, 24), 20.0, r2).justified      # mutant leaks
