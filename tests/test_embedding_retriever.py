"""Swapping the retriever may reorder notes but must never change a verdict."""
import hashlib

import numpy as np

from costwatch.pipeline import run_pipeline


def fake_encoder(texts):
    """Deterministic stand-in for a sentence model: hashed bag of words."""
    out = np.zeros((len(texts), 64))
    for i, t in enumerate(texts):
        for w in t.lower().split():
            out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
    return out


def reversed_encoder(texts):
    return -fake_encoder(texts)          # flips every similarity: worst-case ordering


def _verdicts(out):
    return out[["route", "week_of", "flagged", "matched_note_id"]].fillna("").values.tolist()


def test_verdicts_identical_under_any_ranking():
    base, _ = run_pipeline()
    for enc in (fake_encoder, reversed_encoder):
        alt, _ = run_pipeline(encoder=enc)
        assert _verdicts(alt) == _verdicts(base)
