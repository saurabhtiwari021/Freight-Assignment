"""Score the pipeline against a hand-labeled set, plus an independent no-fabrication audit.

Run:  python eval/run_eval.py          (exit code 1 on any scored failure)

The audit uses HARD-CODED ground truth below (not data/notes_structured.json), so a
mistake in the structured notes or the verdict code cannot silently pass its own test.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from costwatch.pipeline import run_pipeline  # noqa: E402

# note -> (routes it genuinely applies to; None = all, first day, last day). Every other
# note (N004-N010) says costs were unaffected / normal and may NEVER justify a row.
JUSTIFYING = {"N001": ({"Chennai-Bangalore"}, date(2025, 2, 24), date(2025, 3, 8)),
              "N002": ({"Ahmedabad-Mumbai"}, date(2025, 1, 20), date(2025, 1, 26)),
              "N003": (None, date(2025, 5, 5), date(2025, 5, 18))}


def audit_row(r) -> list[str]:
    """Return problems with a 'No (justified)' row (empty list = passes)."""
    nid = r.matched_note_id
    if nid not in JUSTIFYING:
        return [f"{nid!r} can never justify a rise"]
    routes, lo, hi = JUSTIFYING[nid]
    wk = date.fromisoformat(r.week_of)
    problems = []
    if routes is not None and r.route not in routes:
        problems.append(f"{nid} does not apply to {r.route}")
    if not (lo <= wk + timedelta(days=6) and wk <= hi):
        problems.append(f"{nid} window {lo}..{hi} does not cover week {wk}")
    if nid not in r.reason:
        problems.append("note id missing from reason prose")
    return problems


def main() -> int:
    out, _ = run_pipeline()
    out = out.fillna("")
    lab = pd.read_csv(ROOT / "eval" / "labeled_set.csv").fillna("")
    keyed = out.set_index(["route", "week_of"])

    scored, correct, cite_ok, cite_total, details = 0, 0, 0, 0, []
    for _, L in lab.iterrows():
        k = (L.route, L.week_of)
        if k in keyed.index:
            row = keyed.loc[k]
            got = "justified" if row.flagged == "No (justified)" else "unexplained"
            got_note = row.matched_note_id
        else:
            got, got_note = "not_flagged", ""
        if L.expected == "ambiguous":
            details.append(f"  [info ] {L.route} {L.week_of}: system says {got} {got_note}")
            continue
        scored += 1
        ok = got == L.expected
        correct += ok
        if L.expected == "justified":
            cite_total += 1
            cite_ok += (got_note == L.expected_note)
        if not ok or (L.expected == "justified" and got_note != L.expected_note):
            details.append(f"  [FAIL ] {L.route} {L.week_of}: expected {L.expected} {L.expected_note}, got {got} {got_note}")

    justified = out[out.flagged == "No (justified)"]
    fabricated = {f"{r.route} {r.week_of}": audit_row(r) for r in justified.itertuples() if audit_row(r)}
    blank_ok = bool((out[out.flagged == "Yes"].matched_note_id == "").all())

    result = {"labeled_rows_scored": scored, "verdict_accuracy": round(correct / scored, 3),
              "citation_accuracy_on_justified": round(cite_ok / cite_total, 3) if cite_total else None,
              "justified_rows_in_output": len(justified), "fabricated_justifications": len(fabricated),
              "unexplained_rows_have_blank_note_id": blank_ok}
    print(json.dumps(result, indent=2)); print("\n".join(details))
    for k, p in fabricated.items():
        print(f"  [FABRICATED] {k}: {p}")
    (ROOT / "reports" / "eval_results.json").write_text(json.dumps(result, indent=2))
    return 0 if (correct == scored and not fabricated and blank_ok and cite_ok == cite_total) else 1


if __name__ == "__main__":
    sys.exit(main())
