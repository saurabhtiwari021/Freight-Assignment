"""Retrieve candidate notes for a flagged route-week.

Two stages, both deterministic:
  1. HARD FILTER on metadata: only notes whose scope covers the route.
  2. RANK by TF-IDF cosine similarity between a query and the note text.

With only ten notes the 'vector index' is an in-memory matrix; the interface
is the same one a Chroma/FAISS or sentence-transformer backend would plug into.
Retrieval only decides ORDER. It never decides a verdict: see verdict.py.
"""
from __future__ import annotations

from datetime import date

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .notes import Note

QUERY_TEMPLATE = ("{route} freight cost per tonne km increase surcharge fuel diesel toll "
                  "flood weather festival disruption detour week of {week}")


class TfidfRetriever:
    def __init__(self, notes: list[Note]):
        self.notes = notes
        docs = [f"{' '.join(n.applies_to)} {n.text}" for n in notes]
        self._vec = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))
        self._matrix = self._vec.fit_transform(docs)

    def search(self, route: str, week_of: date) -> list[tuple[Note, float]]:
        """Notes covering `route`, best match first. Ties break on note_id."""
        q = self._vec.transform([QUERY_TEMPLATE.format(route=route, week=week_of.isoformat())])
        sims = cosine_similarity(q, self._matrix)[0]
        scored = [(n, float(s)) for n, s in zip(self.notes, sims) if n.covers_route(route)]
        # route-specific notes outrank 'All Routes' notes on equal footing
        scored.sort(key=lambda t: (-round(t[1], 6), "ALL" in t[0].applies_to, t[0].note_id))
        return scored


class EmbeddingRetriever(TfidfRetriever):
    """Same hard route filter, but ranks by dense sentence embeddings.

    `encoder` is any callable list[str] -> 2-D array of vectors (e.g. a
    sentence-transformers model's .encode). It is injected so tests can use a
    fake one and so the default run needs no model download. Ordering only:
    verdict.py still decides every verdict, so swapping the retriever cannot
    change a justified/unexplained outcome.
    """

    def __init__(self, notes: list[Note], encoder):
        self.notes = notes
        self._encode = encoder
        self._matrix = self._unit(encoder([f"{' '.join(n.applies_to)} {n.text}" for n in notes]))

    @staticmethod
    def _unit(a):
        import numpy as np
        a = np.asarray(a, dtype=float)
        return a / np.clip(np.linalg.norm(a, axis=1, keepdims=True), 1e-12, None)

    def search(self, route: str, week_of: date) -> list[tuple[Note, float]]:
        q = self._unit(self._encode([QUERY_TEMPLATE.format(route=route, week=week_of.isoformat())]))
        sims = (self._matrix @ q[0]).tolist()
        scored = [(n, float(s)) for n, s in zip(self.notes, sims) if n.covers_route(route)]
        scored.sort(key=lambda t: (-round(t[1], 6), "ALL" in t[0].applies_to, t[0].note_id))
        return scored


def minilm_encoder(name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """Load a local sentence-transformers model (needs `pip install sentence-transformers`)."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(name)
    return lambda texts: model.encode(texts, normalize_embeddings=True)
