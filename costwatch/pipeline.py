"""End to end: shipments + notes -> output.csv (matching sample_output_format_v2)."""
from __future__ import annotations

import pandas as pd

from . import config as C
from .flagging import candidates
from .llm import Polisher
from .metrics import add_baselines, load_shipments, weekly_cost
from .notes import load_notes
from .retrieval import TfidfRetriever, EmbeddingRetriever
from .verdict import decide

OUTPUT_COLUMNS = ["route", "week_of", "cost_per_tonne_km", "vs_own_history",
                  "vs_similar_routes", "flagged", "matched_note_id", "reason"]


def run_pipeline(shipments_path=C.SHIPMENTS_CSV, notes_path=C.NOTES_CSV,
                 polisher: Polisher | None = None, encoder=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (output rows, full weekly table with baselines)."""
    weekly = add_baselines(weekly_cost(load_shipments(shipments_path)))
    notes = load_notes(notes_path)
    retriever = EmbeddingRetriever(notes, encoder) if encoder else TfidfRetriever(notes)

    rows = []
    for _, r in candidates(weekly).iterrows():
        v = decide(r["route"], r["week_of"].date(), r["vs_history_pct"], retriever)
        reason = polisher.polish(v.reason) if polisher else v.reason
        rows.append({
            "route": r["route"],
            "week_of": r["week_of"].strftime("%Y-%m-%d"),
            "cost_per_tonne_km": round(r["cost_per_tonne_km"], 2),
            "vs_own_history": f"{r['vs_history_pct']:+.1f}% vs this route's past average",
            "vs_similar_routes": f"{r['vs_peers_pct']:+.1f}% vs similar-length routes this week",
            "flagged": "No (justified)" if v.justified else "Yes",
            "matched_note_id": v.note_id or "",
            "reason": reason,
        })
    out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    out = out.sort_values(["week_of", "route"]).reset_index(drop=True)
    return out, weekly
