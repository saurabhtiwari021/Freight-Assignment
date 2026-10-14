"""All tunable knobs in one place. Nothing here is random."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SHIPMENTS_CSV = DATA_DIR / "shipment_records.csv"
NOTES_CSV = DATA_DIR / "context_notes.csv"
NOTES_STRUCTURED_JSON = DATA_DIR / "notes_structured.json"
SAMPLE_FORMAT_CSV = DATA_DIR / "sample_output_format_v2.csv"
REPORTS_DIR = ROOT / "reports"
OUTPUT_CSV = REPORTS_DIR / "output.csv"

# --- baselines (fixed by the brief; do not change) --------------------------
HISTORY_WINDOW_WEEKS = 8      # trailing, strictly-before-current-week

# --- flag rule (our choice; see README "Flag rule") -------------------------
# A route-week is a candidate when cost is RISING vs its own history AND it is
# unusual by either of two signals:
#   (a) the rise vs own history is large in absolute terms, or
#   (b) it is a modest rise but also well above same-length peers.
HIST_PCT_STRONG = 10.0        # (a) vs_own_history >= 10%
HIST_PCT_MODEST = 5.0         # (b) vs_own_history >= 5% ...
PEER_PCT_MODEST = 20.0        #     ... and vs_similar_routes >= 20%
# NOTE: a z-score guard was tried and removed. After a spike the trailing
# window is contaminated, so z collapses and real elevated weeks (Chennai-
# Bangalore 2025-03-17) and a slow creep (Mumbai-Pune) were hidden.

# --- note verification ------------------------------------------------------
# Notes with no stated end date ("starting this week") are treated as covering
# only the week they start plus the next one. The note gives no duration, so we
# do not stretch it further: a rise weeks later is left "unexplained" rather
# than attributed to a note that never said it lasted that long.
OPEN_ENDED_WINDOW_WEEKS = 2
# A note quoting a magnitude (e.g. 5-7%) only justifies a rise that is not much
# larger than that magnitude; the excess would be unexplained.
MAGNITUDE_TOLERANCE_PCT = 3.0
# Retrieval: only consider notes within this many days of the week when naming
# a "closest note" for an unexplained row.
CLOSEST_NOTE_MAX_DAYS = 90
