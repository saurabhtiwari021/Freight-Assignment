"""Threshold sensitivity analysis.

Reruns the pipeline with different threshold combos and records which rows flip.

Run:  python eval/sensitivity.py
"""
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from costwatch import config as C
from costwatch.pipeline import run_pipeline


HIST_PCT_STRONG_VALS = [8, 10, 12]
PEER_PCT_MODEST_VALS = [15, 20, 25]
OPEN_ENDED_WINDOW_WEEKS_VALS = [2, 4, 8]


def run_with_params(hist_pct, peer_pct, window_weeks):
    """Run pipeline with overridden config values, return output DataFrame."""
    # Save originals
    orig_hist = C.HIST_PCT_STRONG
    orig_peer = C.PEER_PCT_MODEST
    orig_window = C.OPEN_ENDED_WINDOW_WEEKS

    try:
        C.HIST_PCT_STRONG = hist_pct
        C.PEER_PCT_MODEST = peer_pct
        C.OPEN_ENDED_WINDOW_WEEKS = window_weeks
        out, _ = run_pipeline()
        return out
    finally:
        C.HIST_PCT_STRONG = orig_hist
        C.PEER_PCT_MODEST = orig_peer
        C.OPEN_ENDED_WINDOW_WEEKS = orig_window


def main():
    # Baseline: the current defaults
    baseline = run_with_params(10, 20, 2)
    baseline_key = set(zip(baseline["route"], baseline["week_of"], baseline["flagged"]))

    results = []
    for hist_pct, peer_pct, window_wk in itertools.product(
        HIST_PCT_STRONG_VALS, PEER_PCT_MODEST_VALS, OPEN_ENDED_WINDOW_WEEKS_VALS
    ):
        out = run_with_params(hist_pct, peer_pct, window_wk)
        combo_key = set(zip(out["route"], out["week_of"], out["flagged"]))

        # Rows that changed
        appeared = combo_key - baseline_key
        disappeared = baseline_key - combo_key

        n_total = len(out)
        n_yes = (out["flagged"] == "Yes").sum()
        n_justified = (out["flagged"] != "Yes").sum()

        results.append({
            "HIST_PCT_STRONG": hist_pct,
            "PEER_PCT_MODEST": peer_pct,
            "OPEN_ENDED_WINDOW_WEEKS": window_wk,
            "total_rows": n_total,
            "flagged_yes": int(n_yes),
            "justified": int(n_justified),
            "rows_changed_vs_baseline": len(appeared | disappeared),
        })

        if appeared or disappeared:
            for route, week, flag in sorted(appeared):
                results[-1].setdefault("details", []).append(
                    f"+APPEARED: {route} {week} -> {flag}")
            for route, week, flag in sorted(disappeared):
                results[-1].setdefault("details", []).append(
                    f"-DISAPPEARED: {route} {week} was {flag}")

    df = pd.DataFrame(results)
    # Print summary table
    print("\n=== THRESHOLD SENSITIVITY TABLE ===\n")
    summary_cols = ["HIST_PCT_STRONG", "PEER_PCT_MODEST", "OPEN_ENDED_WINDOW_WEEKS",
                    "total_rows", "flagged_yes", "justified", "rows_changed_vs_baseline"]
    print(df[summary_cols].to_string(index=False))

    # Print details of flips
    print("\n=== ROWS THAT FLIP ===\n")
    for _, row in df.iterrows():
        if isinstance(row.get("details"), list):
            print(f"  HIST={row['HIST_PCT_STRONG']} PEER={row['PEER_PCT_MODEST']} "
                  f"WINDOW={row['OPEN_ENDED_WINDOW_WEEKS']}:")
            for d in row["details"]:
                print(f"    {d}")

    # Save JSON for README
    out_path = ROOT / "reports" / "sensitivity.json"
    save = [{k: v for k, v in r.items() if k != "details"} for r in results]
    out_path.write_text(json.dumps(save, indent=2))
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
