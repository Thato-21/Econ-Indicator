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

### Mini web app

Double-click `run-dashboard.cmd`, or run it from PowerShell:

```powershell
.\run-dashboard.cmd
```

The dashboard opens at `http://127.0.0.1:8765`. Keep the terminal window open while using it;
press `Ctrl+C` there to stop the server. It uses only Python's standard library.

### Command-line output

From PowerShell in the project directory, use the project launcher:

```powershell
.\run-engine.cmd XAUUSD examples\xauusd_evidence.json
```

The launcher finds Python and runs the source tree directly, so it does not depend on the
`macro-engine` command being registered in `PATH`. On this workstation it automatically uses
`C:\msys64\ucrt64\bin\python.exe`. The `.cmd` launcher also works when PowerShell's execution
policy blocks `.ps1` scripts.

Alternatively, invoke this workstation's interpreter directly:

```powershell
$env:PYTHONPATH = "$PWD\src"
& "C:\msys64\ucrt64\bin\python.exe" -m macro_engine.cli XAUUSD examples\xauusd_evidence.json
```

For an editable installation and the shorter command, first ensure Python is available in the
same terminal, then run:

```powershell
python -m pip install -e .
python -m macro_engine.cli XAUUSD examples\xauusd_evidence.json
```

The `python -m ...` form remains reliable even when the directory containing installed console
scripts is absent from `PATH`.

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
