"""Load the raw notes and the hand-reviewed structured facts; cross-check them."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from . import config as C

ALL = "ALL"


@dataclass(frozen=True)
class Note:
    note_id: str
    date: date
    applies_to: tuple          # route names, or ("ALL",)
    window_start: date
    window_end: date | None    # None = open ended
    effect: str                # "raises_cost" | "none"
    magnitude_pct_max: float | None
    summary: str
    text: str                  # raw note text (used by retrieval)

    def effective_end(self) -> date:
        """Closed end date; open-ended notes get a bounded window."""
        if self.window_end is not None:
            return self.window_end
        return self.window_start + timedelta(weeks=C.OPEN_ENDED_WINDOW_WEEKS) - timedelta(days=1)

    def covers_route(self, route: str) -> bool:
        return ALL in self.applies_to or route in self.applies_to


def _raw_scope(raw: str) -> tuple:
    return (ALL,) if raw.strip().lower() == "all routes" else (raw.strip(),)


def load_notes(raw_path=C.NOTES_CSV, structured_path=C.NOTES_STRUCTURED_JSON) -> list[Note]:
    raw = pd.read_csv(raw_path).set_index("note_id")
    structured = json.loads(structured_path.read_text())["notes"]
    if {s["note_id"] for s in structured} != set(raw.index):
        raise ValueError("structured notes and context_notes.csv have different note ids")

    notes = []
    for s in structured:
        r = raw.loc[s["note_id"]]
        note_date = pd.Timestamp(r["date"]).date()
        # drift guards: the structured file must agree with the raw CSV
        if tuple(s["applies_to"]) != _raw_scope(r["applies_to"]):
            raise ValueError(f"{s['note_id']}: scope differs from raw CSV")
        if date.fromisoformat(s["window_start"]) != note_date:
            raise ValueError(f"{s['note_id']}: window_start differs from raw note date")
        notes.append(Note(
            note_id=s["note_id"], date=note_date, applies_to=tuple(s["applies_to"]),
            window_start=date.fromisoformat(s["window_start"]),
            window_end=date.fromisoformat(s["window_end"]) if s["window_end"] else None,
            effect=s["effect"], magnitude_pct_max=s["magnitude_pct_max"],
            summary=s["summary"], text=str(r["note"]),
        ))
    return sorted(notes, key=lambda n: n.note_id)
