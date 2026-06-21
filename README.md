# Macro Intelligence Engine

An asset-agnostic foundation for auditable macro regime analysis. XAUUSD is the first
asset pack, not a hard-coded assumption in the engine.

## Design rule

The core consumes normalized evidence whose score is already expressed from the target
asset's perspective. Asset packs declare factors, decay rates, horizon weights, and factor
weights. Ingestion adapters and interpreters produce evidence; the deterministic scorer
produces the final regime. AI can classify and summarize, but cannot bypass the scorer.

```text
sources -> collectors -> normalizers/interpreters -> Evidence
                                                   |
asset pack -> validation -> decay + weighted scorer + contradiction detection
                                                   |
                         assessment -> thesis memory -> API/dashboard/backtest
```

## Run locally

```powershell
python -m pip install -e .
macro-engine XAUUSD examples/xauusd_evidence.json
python -m unittest discover -s tests -v
```

No runtime dependencies are required for the reference core. Production adapters (Postgres,
OpenAI, market/news APIs, Streamlit, and schedulers) belong outside the domain package and can
be added independently.

## Add another asset

1. Copy `src/macro_engine/assets/xauusd.json` to (for example) `eurusd.json`.
2. Define EURUSD's factors, evidence half-lives, and weights. A factor score must always mean
   bullish/bearish **for EURUSD**, regardless of the source metric's native direction.
3. Add collectors or transformation rules only for genuinely new inputs. Shared observations
   such as Fed policy, growth, DXY, and real yields should be reused.
4. Validate with `AssetRegistry().load("EURUSD")` and add historical calibration tests.

The scorer, confidence decay, contradiction logic, result schema, storage ports, API, and
backtester remain unchanged.

See [docs/architecture.md](docs/architecture.md) for production boundaries and the roadmap.
