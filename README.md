# costwatch - a shipping-cost watchdog that refuses to guess

Flags route-weeks where freight cost per tonne-km is rising in a way that looks
out of the ordinary, then says whether a note in `context_notes.csv` genuinely
explains it. **If no note passes every check, the answer is "unexplained" - never a guess.**

```bash
pip install -r requirements.txt
python -m costwatch.run            # -> reports/output.csv (+ reports/llm_usage.json)
python -m pytest -q                # 36 tests
python eval/run_eval.py            # labeled-set score + independent fabrication audit
python eval/repro_check.py         # 3 fresh runs, byte-for-byte diff
```

## How it works

```
shipments --> weekly cost/tonne-km --> baselines --> flag rule --> candidates
                                                                       |
notes.csv + notes_structured.json --> retrieve (filter+rank) --> VERIFY (4 checks) --> verdict + templated reason --> output.csv
```

1. **Weekly metric** (`metrics.py`). Group by route and Monday-Sunday `week_of`;
   `cost_per_tonne_km = SUM(cost) / SUM(tonnes x km)` (ratio of sums, as the brief defines it).
2. **Baselines** exactly as specified: own history = trailing 8-week mean using weeks
   *strictly before* the current one (fewer if unavailable - see "history < 8 weeks");
   peers = mean of the *other* routes' value, same `route_type`, same week.
3. **Flag rule** (`flagging.py`): rising vs own history AND either
   (a) `>= +10%` vs own history, or (b) `>= +5%` vs history *and* `>= +20%` vs peers.
   Thresholds live in `config.py`.
4. **Retrieval** (`retrieval.py`): hard-filter notes to those covering the route (or
   "All Routes"), rank by TF-IDF cosine similarity (or MiniLM embeddings with `--embeddings`). Ranking only sets *order*;
   a test shows verdicts are identical even under a reversed ranking.
5. **Verification** (`verdict.py`) - the anti-hallucination gate. A note justifies a row
   only if it passes all of: **scope** (applies to this route), **effect** (says costs rose;
   not "no effect"/"normal"), **window** (its dates overlap this Mon-Sun week),
   **magnitude** (if it quotes a size like 5-7%, the observed rise isn't far beyond it).
   Plain code, no LLM, so it cannot vary between runs.
6. **Explanation** is built from a template filled with the note's own fields
   (`data/notes_structured.json`: id, dates, a short paraphrase). The note id goes in
   `matched_note_id` and also appears in the prose. Unexplained rows name the nearest
   notes considered and why each fails (e.g. "ends 2 days before this week").

### Why structured notes?
`notes_structured.json` is a hand-reviewed reading of the 10 raw notes (scope, window,
effect). `notes.py` cross-checks it against the raw CSV at load time (ids, scope, start
date) and raises on drift. Windows the notes don't state are explicit assumptions,
each recorded in the file's `basis` field.

## Results on the provided data (2,940 shipments, 7 routes, 104 weeks)

18 route-weeks flagged for review: **15 unexplained, 3 justified**.

| Finding | Verdict |
|---|---|
| Delhi-Jaipur, Nov 2024 (2 weeks, +35% / +28%) | Unexplained - only note for this route is N007 (May 2024, better roads) |
| Ahmedabad-Mumbai 2025-01-20 (+29%) | Justified - N002, festival surcharge |
| Chennai-Bangalore 2025-02-24, 03-03 | Justified - N001, flood window 24 Feb-8 Mar |
| Chennai-Bangalore 2025-03-10, 03-17 (still +22% / +14%) | **Unexplained** - flood window ended 8 Mar; N009 says conditions normal |
| Mumbai-Delhi 2025-05-12 (+11.6%) | Unexplained - N003 (diesel) only covers ~5-7% |
| Mumbai-Pune 2025-06-23 (+6.2%) | Unexplained - N003 (diesel, 5 May) gives no end date; 7 weeks on is not shown to still apply |
| Mumbai-Pune, 9 weeks Sep-Dec 2025 | Unexplained - see below |

**Notable pattern:** Mumbai-Pune climbs from ~3.4 (Apr 2025) to ~4.4 (Dec 2025), about +30%,
while its premium over Delhi-Jaipur widens from ~1.10x to ~1.38x. No note explains it. A
trailing window sees only 5-9% per week, so it is caught mainly through the peer signal.

## How I checked it (and its limits)

- **Unit tests** hand-calculate the metrics (ratio-of-sums, no look-ahead, <8-week history,
  peer exclusion) and check the output contract (column names/order, formats, Monday `week_of`).
  The numbers reproduce the sample file's rows for Delhi-Jaipur and Ahmedabad-Mumbai.
- **Adversarial verdict tests** inject a rise where a note must *not* justify it: wrong route,
  right route/wrong window, every "no effect" note, a rise far above the quoted magnitude,
  plus a sweep of all routes x 104 weeks asserting every justified verdict satisfies hard-coded rules.
- **Labeled eval** (`eval/labeled_set.csv`, 20 scored rows + 2 ambiguous reported separately):
  verdict accuracy 1.0, citation accuracy 1.0, **0 fabricated justifications** (audited against
  ground truth hard-coded in `run_eval.py`, independent of the code under test).
- **Mutation tests** disable the window and effect checks and confirm the eval fails.
- **Honest caveats.** I wrote the labels after studying this same data, and tuned thresholds on
  it, so the 1.0 is a regression check against hand-reasoned labels, *not* a held-out score. The
  real flagged weeks contain no cross-route note collisions, so route-scoping is protected by the
  adversarial tests rather than the labeled eval. Two rows are labeled ambiguous on purpose.

## Threshold sensitivity (`python eval/sensitivity.py`, full grid in `reports/sensitivity.json`)

Defaults are 10 / 20 / 2. One knob moved at a time, everything else at default:

| Setting | Rows that flip vs default (18 flagged) |
|---|---|
| `HIST_PCT_STRONG` 8 | +1 flagged: Delhi-Chennai 2024-02-05 |
| `HIST_PCT_STRONG` 12 | -1: Mumbai-Delhi 2025-05-12 (+11.6%) drops out |
| `PEER_PCT_MODEST` 15 | none |
| `PEER_PCT_MODEST` 25 | -5: Mumbai-Pune 2025-06-23, 09-15, 10-06, 10-20, 11-03 (the creep leans on the peer signal) |
| `OPEN_ENDED_WINDOW_WEEKS` 4 | none |
| `OPEN_ENDED_WINDOW_WEEKS` 8 | Mumbai-Pune 2025-06-23 becomes *justified* by N003 (the only verdict change) |

The diesel window therefore only matters for one row. Thresholds were chosen on this data, so this table shows how fragile they are, not that they are right.

## Reproducibility

Nothing is random. `eval/repro_check.py` runs three fresh processes with different
`PYTHONHASHSEED`s; outputs are byte-identical (`reports/repro_check.txt`). Sorting is explicit
and ties break on note id.

## Cost of one full run

The submitted run makes **0 LLM calls, 0 input tokens, 0 output tokens, $0** - retrieval is
local TF-IDF and the reasons are templated, which is also what makes them reproducible
(`reports/llm_usage.json`). An optional `--llm` flag lets any OpenAI-compatible endpoint
(e.g. local Ollama) re-word reasons at temperature 0 with a fixed seed and an on-disk cache. Verdict and
note id are decided first; a guard discards any rewrite whose note ids differ from the template.
At most 18 calls per full run; every call's tokens and cost are logged to the ledger.

## Assumptions and limitations

- **History < 8 weeks:** each route's first 8 weeks use all prior weeks available (week 1 has
  none, so it is never flagged). No flagged row falls in that period.
- **N002** gives a start date and "festival week": treated as 7 days from the note date.
- **N003** says "starting this week" with no end: treated as covering only that week and the next
  (`OPEN_ENDED_WINDOW_WEEKS = 2`); the note never says how long it lasted, so later rises stay unexplained. Rises above ~10% (7% + 3-pt tolerance) are only partly explained, so unexplained.
- Short and Long types have only 2 routes each, so "peers" is a single route there.
- A z-score guard was tried and removed: after a spike the trailing window is contaminated and
  the guard hid real elevated weeks (Chennai-Bangalore 03-17) and the Mumbai-Pune creep.
- A persistent creep is reported week by week; grouping consecutive flags into "episodes" would be a good next step.
- `sample_output_format_v2.csv` row 3 has an unquoted comma in `reason`, so strict CSV parsers
  misread it; our output quotes fields properly.
- The default retrieval "vector index" is an in-memory TF-IDF matrix. `--embeddings` swaps in
  MiniLM sentence embeddings (`EmbeddingRetriever`); it was only tested with a stand-in encoder,
  not the real model, because the build sandbox could not download it. Verdicts never depend on ranking.
