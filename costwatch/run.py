"""CLI:  python -m costwatch.run [--llm]"""
from __future__ import annotations

import argparse
import json

from . import config as C
from .pipeline import run_pipeline
from .llm import Polisher


def main() -> None:
    ap = argparse.ArgumentParser(description="Flag unjustified freight cost rises.")
    ap.add_argument("--shipments", default=str(C.SHIPMENTS_CSV))
    ap.add_argument("--notes", default=str(C.NOTES_CSV))
    ap.add_argument("--out", default=str(C.OUTPUT_CSV))
    ap.add_argument("--llm", action="store_true",
                    help="polish reason wording via COSTWATCH_LLM_URL/MODEL (verdicts unaffected)")
    ap.add_argument("--embeddings", action="store_true",
                    help="rank notes with MiniLM sentence embeddings (needs sentence-transformers; "
                         "verdicts unaffected)")
    a = ap.parse_args()

    C.REPORTS_DIR.mkdir(exist_ok=True)
    polisher = Polisher.from_env(C.REPORTS_DIR / ".llm_cache.json") if a.llm else None
    if a.llm and polisher is None:
        raise SystemExit("--llm needs COSTWATCH_LLM_URL and COSTWATCH_LLM_MODEL set")

    encoder = None
    if a.embeddings:
        from .retrieval import minilm_encoder
        encoder = minilm_encoder()
    out, _ = run_pipeline(a.shipments, a.notes, polisher, encoder)
    out.to_csv(a.out, index=False)

    usage = polisher.ledger.as_dict() if polisher else {
        "model": None, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost": 0.0}
    (C.REPORTS_DIR / "llm_usage.json").write_text(json.dumps(usage, indent=2))
    print(f"{len(out)} rows -> {a.out}  "
          f"(flagged Yes: {(out.flagged == 'Yes').sum()}, justified: {(out.flagged != 'Yes').sum()})")
    print(f"LLM calls: {usage['llm_calls']}  tokens in/out: {usage['input_tokens']}/{usage['output_tokens']}")


if __name__ == "__main__":
    main()
