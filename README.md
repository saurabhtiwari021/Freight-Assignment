Costwatch : Evidence-Grounded Shipping Cost Anomaly Assistant
Author: Saurabh Tiwari
Background: B.Tech Computer Science & Engineering, KIIT University (Class of 2027)
Project context: Software Engineer Intern, AI & Data case study
I approached this problem with one principle: detect unusual cost movements with transparent calculations, but explain them only when the supplied evidence supports the explanation. If no context note passes the verification checks, Costwatch reports the rise as unexplained and leaves it for human review rather than guessing.

Overview
Costwatch analyzes shipment data to identify route weeks where freight cost per tonne-kilometre is rising unusually. It compares each route against its own recent history and comparable routes in the same week, then checks whether the supplied context notes genuinely explain the observed rise.
The core verdict path is deterministic. Retrieval helps order candidate notes, but it does not decide whether an anomaly is justified. An optional LLM mode can polish explanation wording only; it cannot set the verdict.
What it does
- Calculates weekly cost per tonne-kilometre using a ratio of sums.
- Uses a trailing eight-week historical baseline with no look-ahead.
- Compares each route with other routes of the same route_type in the same week.
- Flags candidates using configurable, documented thresholds.
- Retrieves route-relevant notes and verifies scope, cost impact, date window and magnitude before accepting an explanation.
- Produces a CSV with the required eight-column output contract.
- Includes automated tests, a labelled evaluation, a threshold-sensitivity check and a three-run reproducibility check.
Quick start
Windows PowerShell
Run these commands from the project root—the directory containing requirements.txt and the costwatch, data, eval, reports and tests folders.
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python -m costwatch.run
python -m pytest -q
python eval/run_eval.py
python eval/repro_check.py
python eval/sensitivity.py
macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python -m costwatch.run
python -m pytest -q
python eval/run_eval.py
python eval/repro_check.py
python eval/sensitivity.py
The default run writes reports/output.csv and reports/llm_usage.json. The evaluation and reproducibility scripts update their corresponding files under reports/.
Optional modes
Use sentence-transformer embeddings to rank notes (requires downloading the model and installing an optional dependency):
python -m pip install sentence-transformers
python -m costwatch.run --embeddings
The real MiniLM model was not available in the build environment used for this submission. The embedding-retriever tests use a stand-in encoder; treat the real model path as optional until you have run it in your own environment. The default TF-IDF path does not need this dependency.
Polish explanation wording with an OpenAI-compatible endpoint (optional): set COSTWATCH_LLM_URL and COSTWATCH_LLM_MODEL, then run:
$env:COSTWATCH_LLM_URL = "http://localhost:11434/v1"
$env:COSTWATCH_LLM_MODEL = "your-model-name"
# Optional, if the endpoint requires authentication:
$env:COSTWATCH_LLM_KEY = "your-key"
python -m costwatch.run --llm
The URL should be the endpoint base; Costwatch appends /chat/completions. The LLM is off by default and only rewrites the already-created reason text. The verdict and selected note are determined first. A note-ID guard rejects rewrites that change the set of cited note IDs, and responses are cached on disk.
For a meaningful estimated cost with a paid endpoint, set COSTWATCH_PRICE_IN_PER_M and COSTWATCH_PRICE_OUT_PER_M to that provider's current prices per million input/output tokens. If those variables are omitted, the ledger defaults to zero prices, so estimated_cost would not be a valid estimate for a paid call. Do not commit API keys or secret .env files.
For LLM-polished runs, compare all columns except explanation wording with:
python eval/repro_check.py --llm --exclude-reason
How it works
Shipment records
      |
      v
Weekly cost / tonne-km
      |
      v
Historical baseline + same-week peer baseline
      |
      v
Candidate flagging
      |
      +---------------------------+
                                  v
Raw context notes --> route filter --> TF-IDF ranking --> 4 verification checks
                                                        |
                                                        v
                                      Justified or unexplained
                                                        |
                                                        v
                                           CSV + reason + note ID
1. Weekly metric — costwatch/metrics.py
Shipments are grouped by route and Monday-starting week. The metric is:
cost_per_tonne_km = SUM(freight_cost_inr) / SUM(quantity_tonnes × distance_km)
This is a ratio of totals, not an average of shipment-level ratios. Shipment inputs with missing or non-positive tonnes, distance or freight cost are rejected.
2. Comparison baselines — costwatch/metrics.py
- Own history: mean of the previous eight weekly route values, using only weeks strictly before the current week. If fewer than eight weeks are available, the available prior weeks are used.
- Similar routes: mean of the other routes with the same route_type in the same week. The current route is excluded from its peer mean.
3. Candidate rule — costwatch/flagging.py
A route-week must be rising versus its own history, and it becomes a candidate when either condition is met:
- Strong historical rise: at least +10% versus its own historical mean; or
- Moderate historical rise plus peer premium: at least +5% versus history and at least +20% versus similar routes.
These thresholds are configurable in costwatch/config.py. They are choices for this implementation, not thresholds supplied by the brief. Their sensitivity is examined in reports/sensitivity.json.
4. Note retrieval — costwatch/retrieval.py
The default retriever uses an in-memory TF-IDF matrix with cosine similarity. Notes are first hard-filtered to the route or All Routes, then ranked by relevance. An optional MiniLM sentence-embedding retriever implements the same interface.
Retrieval determines order, not truth. A high similarity score cannot by itself justify an anomaly. The verdict remains the same even if the note ranking changes, provided the note facts and verification rules do not change.
5. Evidence verification — costwatch/verdict.py
A note can justify a route-week only if it passes all four checks:
1. Scope: the note applies to this route or all routes.
2. Effect: the note describes a cost-raising factor; a statement that conditions were normal or costs were unaffected is not a cause.
3. Window: the note's effective date range overlaps the Monday–Sunday week being reviewed.
4. Magnitude: if the note provides a cost-rise range, the observed historical increase must not exceed that range by more than the configured tolerance.
When no note passes every check, the row remains Yes (flagged for human review) and matched_note_id stays blank. The reason text explains why nearby notes were rejected when relevant.
6. Structured context — data/notes_structured.json
The ten raw notes in data/context_notes.csv are represented by hand-reviewed fields for scope, effective window, effect, magnitude and a short summary. costwatch/notes.py checks note IDs, scope and start dates against the raw CSV at load time and raises an error if they drift. Where a raw note does not specify a complete date range, the assumed window and its rationale are recorded in the structured file.
7. Optional LLM wording — costwatch/llm.py
The optional model receives a reason that already exists and may rephrase it. It is not asked to calculate the metric, retrieve evidence, or choose a verdict. The default submission run is deterministic and makes no LLM calls. Token usage and estimated cost are written to reports/llm_usage.json when the optional mode is enabled.
Output contract
reports/output.csv contains exactly these columns, in this order:
Column	Meaning
route	Origin-destination route name
week_of	Monday date for the reviewed week, formatted YYYY-MM-DD
cost_per_tonne_km	Weekly freight cost per tonne-kilometre, rounded to two decimals
vs_own_history	Percentage difference from that route's historical baseline
vs_similar_routes	Percentage difference from the same-week peer baseline
flagged	Yes or No (justified)
matched_note_id	Supporting note ID for justified rows; blank if unexplained
reason	Evidence-based explanation or the reason no note was accepted


A candidate is not automatically justified. The pipeline keeps a candidate marked Yes when the cost rise remains unexplained, even if a somewhat related note exists.
Results on the supplied data
The provided dataset contains 2,940 shipments, seven routes and 104 weeks per route. The current output contains 18 candidate route-weeks: 15 remain unexplained and flagged for review, while three are justified by context notes.
Example	Result	Reasoning
Delhi–Jaipur, 11 and 18 Nov 2024	Unexplained	The route-specific note N007 is dated May 2024 and describes improved road conditions, not a cost-raising event for these weeks.
Ahmedabad–Mumbai, week of 20 Jan 2025	Justified by N002	The festival-week surcharge note covers this route and week.
Chennai–Bangalore, weeks of 24 Feb and 3 Mar 2025	Justified by N001	Both weeks overlap the stated flood-detour window of 24 Feb–8 Mar 2025.
Chennai–Bangalore, weeks of 10 and 17 Mar 2025	Unexplained	The flood window has ended; N009 says conditions returned to normal.
Mumbai–Delhi, week of 12 May 2025	Unexplained	N003 describes an approximate 5–7% diesel-driven rise, which does not explain the full observed increase.
Mumbai–Pune, week of 23 Jun 2025	Unexplained	N003 has no explicit end date; the implementation uses a bounded window rather than assuming it continues indefinitely.
Mumbai–Pune, multiple weeks from Sep–Dec 2025	Unexplained	A gradual increase is visible relative to the peer route, but no supplied note adequately explains it.


One pattern worth investigating is the gradual increase on Mumbai–Pune: cost per tonne-kilometre rises from roughly 3.4 in April 2025 to roughly 4.4 in December 2025. A trailing historical baseline can absorb gradual changes, so the peer comparison is important for surfacing this pattern. The available notes do not establish its cause.
Validation and evaluation
Automated checks
The test suite covers metric calculations, Monday week boundaries, ratio-of-sums aggregation, no-look-ahead historical baselines, peer-route exclusion, output format, note-window checks, wrong-route notes, notes that state costs were unaffected, magnitude mismatches, and adversarial checks against fabricated justifications.
The independent metric test re-computes weekly values and baselines with a separate, simple implementation and compares the results across all 728 route-weeks.
Latest local verification
The latest Windows run for this working copy reported:
- 36 tests passed with python -m pytest -q.
- 21 labelled examples scored, with 1.0 verdict accuracy and 1.0 citation accuracy on justified rows.
- Zero fabricated justifications in the independent audit.
- Three byte-identical output runs with python eval/repro_check.py.
- Zero LLM calls in the default pipeline run.
These are regression and consistency checks, not proof of performance on unseen data. The labelled examples were written after studying this dataset, and thresholds were tuned using the same dataset. The score should therefore be read as agreement with hand-reasoned labels, not as a held-out accuracy estimate. One ambiguous example is reported for inspection rather than scored.
Threshold sensitivity
Run python eval/sensitivity.py to generate the full comparison in reports/sensitivity.json. In brief:
- Raising HIST_PCT_STRONG from 10% to 12% removes the Mumbai–Delhi candidate for 12 May 2025.
- Raising PEER_PCT_MODEST from 20% to 25% removes five Mumbai–Pune candidates that rely on the peer signal.
- Extending OPEN_ENDED_WINDOW_WEEKS from two to eight changes the Mumbai–Pune result for 23 June 2025 to justified by N003.
These changes show that threshold and date-window assumptions matter; they do not demonstrate that one setting is universally correct.
Reproducibility
eval/repro_check.py launches three fresh processes with different PYTHONHASHSEED values and compares the output files. Explicit sorting and note-ID tie-breaking make the default output byte-for-byte identical across the three runs. When using --llm, explanation wording may vary by endpoint, so --exclude-reason checks that the non-reason fields remain consistent.
Assumptions and limitations
- Fewer than eight history weeks: all available prior route-weeks are used. A route-week without a usable prior baseline is not flagged. No output candidate falls in this initial period.
- N002 date range: the note says “festival week” but gives no end date; it is treated as the seven days from the note date.
- N003 date range: the diesel note says “starting this week” but gives no end date. The implementation limits this to two weeks using OPEN_ENDED_WINDOW_WEEKS, instead of assuming the effect persists indefinitely. Its stated magnitude is approximately 5–7%, with a configured three-percentage-point tolerance.
- Small peer groups: Short and Long route types each have only two routes, so each route has just one peer in that group.
- Gradual changes: a slow persistent increase is surfaced week by week rather than grouped into a single episode. Episode-level aggregation would be a useful next step.
- Embedding path: the default TF-IDF retriever is local and lightweight. The optional MiniLM implementation has not been validated here with the real downloaded model; its unit tests use a stand-in encoder.
- LLM path: the default pipeline does not call a model. The optional LLM changes wording only and should be tested separately against the endpoint you intend to use. Cost estimates require correct provider prices to be configured.
- Thresholds: the default values were selected while examining this dataset. Sensitivity analysis is included to make the consequences visible, but a production deployment would need thresholds validated on additional historical periods and operational feedback.
Project structure
costwatch/
├── costwatch/               # Pipeline and application modules
│   ├── metrics.py           # Weekly metric and comparison baselines
│   ├── flagging.py          # Candidate selection rules
│   ├── retrieval.py         # TF-IDF and optional embedding retrieval
│   ├── notes.py             # Raw/structured note consistency checks
│   ├── verdict.py           # Deterministic evidence verification
│   ├── llm.py               # Optional explanation wording and usage ledger
│   ├── pipeline.py          # End-to-end processing
│   ├── config.py            # Thresholds and file paths
│   └── run.py               # Command-line entry point
├── data/                    # Supplied shipments, notes and note metadata
├── tests/                   # Unit, integration and adversarial tests
├── eval/                    # Labelled evaluation, sensitivity and reproducibility
├── reports/                 # Output CSV and validation evidence
├── requirements.txt
└── README.md
About the author
I'm Saurabh Tiwari, a Computer Science and Engineering student at KIIT University (Class of 2027). I used this case study to focus on practical data engineering fundamentals—clear metric definitions, testable rules, reproducible runs, and careful handling of AI-generated explanations. My main design choice in Costwatch is to keep numerical decisions and the evidence gate inspectable, so an unexplained anomaly is surfaced honestly instead of being assigned a plausible-sounding cause.