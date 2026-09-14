# Forecast baseline and bounded local AI

## Forecast

`/forecast` serves a forecast frozen in the same validated release as exceptions
and history. It does not calculate from changing raw data at request time. Older
releases without a forecast return 503 rather than an invented result.

For each currency independently, select the winning version whose observation
interval contains the cutoff. Exclude deleted records. Report closed-won bookings
separately from open pipeline. With fewer than five known closed outcomes, use an
explicit 0.5 prior. Otherwise use `(known wins + 1)/(known closed outcomes + 2)`.
Multiply open amount by that probability using Decimal and half-up minor-unit
rounding. Never convert/sum currencies or call bookings cash or recognized revenue.

This is **undated expected open bookings**, not a monthly cash forecast, calibrated
ML model, prediction of collection or causal intervention recommendation. It has
no close-date feature, uncertainty interval, invoice/payment feed or censoring
correction. Known closed outcomes can be selection-biased. Historical corrections
obey observation time, not future source-effective dates.

`scripts/evaluate_forecast.py` compares the neutral and smoothed baselines on two
handcrafted temporal holdouts. Prediction cutoff is February 1; held-out outcomes
are first observed March 1. The toy GBP errors are 36 versus 250 minor units;
EUR errors are 0 versus 250. These intentionally small illustrative fixtures are
not evidence of real predictive accuracy or a general model improvement.

Ten tests cover time leakage, cutoff boundaries, currency separation, rounding,
deleted/lost records, overlapping intervals, invalid inputs and unchanged inputs.

## Local AI-assisted investigation

The optional `revenue_pipeline.triage` CLI reads an incident from a frozen release.
It sends only whitelisted synthetic evidence to Ollama on `127.0.0.1:11434`.
There is no external endpoint, API key, paid token call or automatic download.

The model chooses between two **human investigation steps** and must cite the
incident's exact evidence hash. Its JSON is validated with a strict schema;
extra fields, unknown actions, altered evidence, malformed/oversized responses,
HTTP errors and timeouts produce a labelled deterministic fallback. Financial
facts are copied from the release, never taken from the model. No generated
free-text explanation is represented as verified evidence.

This is a deliberately limited local LLM integration, not autonomous remediation,
free-form RAG, or a model allowed to edit cases, send messages or change forecasts.
An enum/citation-valid answer is not proof that the chosen investigation step is
optimal. Human review is mandatory. AI is outside the pipeline's publication gate.

Nine deterministic tests exercise valid/invalid output, evidence mismatch, amount
injection, disabled mode, server failure and response-size bounds. A real installed
`qwen3:4b` model returned a valid `verify_contract_record` suggestion for a synthetic
missing-contract incident on 14 September 2026. This is a runtime smoke result,
not a broad model-quality benchmark. The production-data policy remains synthetic-only.

API contract reference: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
