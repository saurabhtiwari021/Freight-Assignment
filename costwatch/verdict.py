"""Deterministic verdicts. This module is the anti-hallucination gate.

A route-week is 'justified' ONLY IF a note passes ALL four checks:
  1. SCOPE      the note applies to this route (or to 'All Routes')
  2. EFFECT     the note says costs were pushed UP (not 'no effect' / 'normal')
  3. WINDOW     the note's date window overlaps this Monday-Sunday week
  4. MAGNITUDE  if the note quotes a size (e.g. 5-7%), the observed rise is not
                far above it (the excess would be unexplained)
Otherwise the row is 'unexplained' and matched_note_id stays blank.
No LLM is involved, so verdicts cannot vary between runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import config as C
from .notes import Note
from .retrieval import TfidfRetriever

# reason codes
OK = "OK"
WRONG_ROUTE = "WRONG_ROUTE"
NO_COST_EFFECT = "NO_COST_EFFECT"
OUTSIDE_WINDOW = "OUTSIDE_WINDOW"
RISE_EXCEEDS_NOTE = "RISE_EXCEEDS_NOTE"


@dataclass(frozen=True)
class Verdict:
    justified: bool
    note_id: str | None
    reason: str          # template-built, grounded in note fields


def week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def window_gap_days(note: Note, week_start: date) -> tuple[int, str]:
    """0 if the note window overlaps the week; else days apart and direction."""
    ws, we = note.window_start, note.effective_end()
    if we < week_start:
        return (week_start - we).days, "before"
    if ws > week_end(week_start):
        return (ws - week_end(week_start)).days, "after"
    return 0, "overlaps"


def check_note(note: Note, route: str, week_start: date, vs_history_pct: float) -> str:
    """Return OK or the first failing reason code."""
    if not note.covers_route(route):
        return WRONG_ROUTE
    if note.effect != "raises_cost":
        return NO_COST_EFFECT
    gap, _ = window_gap_days(note, week_start)
    if gap > 0:
        return OUTSIDE_WINDOW
    if note.magnitude_pct_max is not None and vs_history_pct > note.magnitude_pct_max + C.MAGNITUDE_TOLERANCE_PCT:
        return RISE_EXCEEDS_NOTE
    return OK


def _window_text(note: Note) -> str:
    if note.window_end is None:
        return (f"from {note.window_start}, no end date in the note, so treated as "
                f"{C.OPEN_ENDED_WINDOW_WEEKS} weeks")
    return f"{note.window_start} to {note.window_end}"


def _justified_reason(note: Note, week_start: date, vs_history_pct: float) -> str:
    text = (f"Matches note {note.note_id} dated {note.date}: {note.summary}. "
            f"Its window ({_window_text(note)}) overlaps this week "
            f"({week_start} to {week_end(week_start)}).")
    if note.magnitude_pct_max is not None:
        text += (f" The note cites a rise of up to ~{note.magnitude_pct_max:g}%; the observed "
                 f"{vs_history_pct:+.1f}% vs history is within that range.")
    return text + " The cost rise has a clear explanation."


def _rejection_phrase(note: Note, code: str, week_start: date, vs_history_pct: float) -> str:
    head = f"{note.note_id} ({note.date})"
    if code == NO_COST_EFFECT:
        return f"{head}: {note.summary}, which is not a reason for a cost rise on this route"
    if code == OUTSIDE_WINDOW:
        gap, direction = window_gap_days(note, week_start)
        rel = "ends" if direction == "before" else "starts"
        when = "before" if direction == "before" else "after"
        return (f"{head}: {note.summary}, but its window ({_window_text(note)}) does not include "
                f"this week (it {rel} {gap} day(s) {when} it)")
    if code == RISE_EXCEEDS_NOTE:
        return (f"{head}: {note.summary}, but this week is {vs_history_pct:+.1f}% vs history, "
                f"more than that note can explain")
    return head


def decide(route: str, week_start: date, vs_history_pct: float,
           retriever: TfidfRetriever) -> Verdict:
    ranked = retriever.search(route, week_start)       # already route-filtered

    # 1) first ranked note that passes every check justifies the row
    for note, _sim in ranked:
        if check_note(note, route, week_start, vs_history_pct) == OK:
            return Verdict(True, note.note_id, _justified_reason(note, week_start, vs_history_pct))

    # 2) otherwise explain which nearby notes were considered and why they fail
    sims = {n.note_id: s for n, s in ranked}
    near = []
    for note, _ in ranked:
        gap, _dir = window_gap_days(note, week_start)
        if gap <= C.CLOSEST_NOTE_MAX_DAYS:
            near.append((gap, -sims[note.note_id], note.note_id, note))
    near.sort(key=lambda t: t[:3])
    if not near:
        return Verdict(False, None, "No matching note found for this route or date range. "
                                    "Cost rise looks unexplained and worth a human review.")
    phrases = [_rejection_phrase(n, check_note(n, route, week_start, vs_history_pct),
                                 week_start, vs_history_pct) for *_, n in near[:2]]
    label = "Closest note considered -- " if len(phrases) == 1 else "Closest notes considered -- "
    return Verdict(False, None, label + "; ".join(phrases) +
                   ". No genuine justification found; flagged for review.")
