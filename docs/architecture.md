# Modular architecture

## Bounded contexts

| Context | Owns | Must not own |
|---|---|---|
| Acquisition | API/RSS/economic-calendar connectors, raw immutable payloads | Asset direction |
| Knowledge | Normalized observations, entities, releases, revisions, provenance | Portfolio weights |
| Interpretation | Significance, horizon relevance, asset-relative evidence | Final regime score |
| Asset packs | Factor taxonomy, transformations, decay, weights, thresholds | Infrastructure code |
| Regime engine | Decay, aggregation, confidence, contradictions, deterministic direction | Vendor APIs or prompts |
| Narrative | Thesis comparison, explanation, change classification | Hidden score changes |
| Memory | Assessments, thesis versions, evidence links, audit events | Scoring policy |
| Validation | Point-in-time replay, returns, calibration, drift | Live mutations |
| Delivery | API, Streamlit dashboard, alerts | Business rules |

Dependencies point inward: infrastructure implements domain ports. The domain imports no
database, web framework, AI SDK, dashboard, or asset-specific Python module.

## Canonical pipeline

1. Collectors persist a raw payload with source, publication time, observation time, and hash.
2. Normalizers convert payloads into shared observations (for example `US_REAL_YIELD_10Y`).
3. Interpreters apply an asset pack's mapping and emit immutable `Evidence`. AI output is
   schema-validated, source-linked, and treated as one input with bounded confidence.
4. The engine applies time decay, significance, confidence, factor weights, and horizon weights.
5. The narrative service compares the result with the last accepted thesis. A policy layer
   decides whether change is noise, reinforcement, weakening, invalidation, or a new thesis.
6. The memory service stores the assessment and all contributing evidence in one transaction.
7. Delivery and backtesting read the same assessment schema.

## Stable extension points

- `AssetPack`: declarative asset behavior, semantically versioned.
- `EvidenceRepository`: latest point-in-time evidence, replaceable by Postgres or memory.
- `AssessmentRepository`: thesis history and audit persistence.
- Collector protocol (next adapter package): vendor-specific raw ingestion.
- Interpreter protocol (next application package): deterministic or AI-assisted normalization.
- Narrative renderer: template or LLM implementation; it explains but does not score.

Shared observations should be collected once. Each asset gets an independent interpretation,
because rising oil, yields, or DXY can have different direction and importance for XAUUSD,
EURUSD, equities, and Bitcoin.

## Suggested production layout

```text
src/
  macro_engine/              # pure domain and application core (current)
  adapters/
    ingestion/               # FRED, central banks, calendars, news, market data
    persistence/             # PostgreSQL implementations and migrations
    ai/                      # structured event/narrative interpretation
    delivery/                # FastAPI and Streamlit
  workers/                   # scheduled ingestion and assessment jobs
```

Recommended PostgreSQL entities: `raw_documents`, `observations`, `evidence`, `asset_packs`,
`assessments`, `factor_results`, `theses`, `thesis_changes`, and `market_prices`. Every derived
row should retain `source_id`, `model_version`, `pack_version`, `effective_at`, and `known_at`
to prevent look-ahead bias and make every score reproducible.

## Narrative stability policy

Keep hysteresis outside the basic scorer and make it configurable per asset:

- do not change direction until a boundary is exceeded by a safety margin;
- require persistence across multiple assessments or high-significance corroboration;
- allow immediate changes only for explicit invalidation conditions;
- decay stale confidence continuously without inventing neutral evidence;
- always expose opposing material factor contributions.

This separation lets research tune stability rules without changing the auditable raw score.

## Delivery phases

1. Calibrate XAUUSD transformations and point-in-time datasets.
2. Add Postgres repositories, migrations, replay-safe workers, and raw-data lineage.
3. Add deterministic economic-series interpreters, then bounded AI news interpretation.
4. Add thesis hysteresis/memory, API, dashboard, alerts, and operational telemetry.
5. Backtest walk-forward with vintage data; freeze and version approved XAUUSD packs.
6. Add assets by pack and mappings, then test cross-asset contamination and shared-data reuse.

