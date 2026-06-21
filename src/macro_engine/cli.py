from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .domain import Evidence, Horizon
from .engine import MacroEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a macro regime assessment")
    parser.add_argument("asset", help="Asset pack id, for example XAUUSD")
    parser.add_argument("evidence", type=Path, help="JSON array of normalized evidence")
    args = parser.parse_args()
    raw = json.loads(args.evidence.read_text(encoding="utf-8"))
    evidence = [
        Evidence(
            **{
                **item,
                "horizon": Horizon(item["horizon"]),
                "observed_at": datetime.fromisoformat(item["observed_at"]),
            }
        )
        for item in raw
    ]
    print(json.dumps(asdict(MacroEngine().assess(args.asset, evidence)), default=str, indent=2))


if __name__ == "__main__":
    main()

