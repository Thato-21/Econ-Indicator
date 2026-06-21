from datetime import UTC, datetime, timedelta
import unittest

from macro_engine import AssetRegistry, MacroEngine
from macro_engine.config import AssetPack
from macro_engine.domain import Direction, Evidence, Horizon


NOW = datetime(2026, 6, 21, tzinfo=UTC)


def evidence(factor: str, score: float, *, age_days: int = 0) -> Evidence:
    return Evidence(
        factor=factor,
        horizon=Horizon.INTERMEDIATE,
        score=score,
        confidence=1,
        significance=1,
        observed_at=NOW - timedelta(days=age_days),
        source="test",
        summary=f"{factor} evidence",
    )


class EngineTests(unittest.TestCase):
    def test_xauusd_pack_loads_and_is_normalized(self) -> None:
        pack = AssetRegistry().load("xauusd")
        self.assertEqual(pack.asset_id, "XAUUSD")
        self.assertAlmostEqual(sum(pack.weights[Horizon.STRUCTURAL].values()), 1)

    def test_engine_is_deterministic_and_exposes_contradictions(self) -> None:
        result = MacroEngine().assess(
            "XAUUSD",
            [evidence("fed_policy", 80), evidence("real_yields", 80), evidence("usd", -80)],
            NOW,
        )
        intermediate = next(h for h in result.horizons if h.horizon == Horizon.INTERMEDIATE)
        self.assertAlmostEqual(intermediate.score, 24)
        self.assertEqual(intermediate.direction, Direction.BULLISH)
        self.assertEqual(
            result.contradictions,
            ("intermediate: bullish fed_policy, real_yields vs bearish usd",),
        )

    def test_stale_evidence_loses_confidence_but_not_its_sign(self) -> None:
        fresh = MacroEngine().assess("XAUUSD", [evidence("real_yields", 80)], NOW)
        stale = MacroEngine().assess(
            "XAUUSD", [evidence("real_yields", 80, age_days=60)], NOW
        )
        fresh_h = next(h for h in fresh.horizons if h.horizon == Horizon.INTERMEDIATE)
        stale_h = next(h for h in stale.horizons if h.horizon == Horizon.INTERMEDIATE)
        self.assertEqual(stale_h.score, fresh_h.score)
        self.assertLess(stale_h.confidence, fresh_h.confidence)

    def test_invalid_asset_pack_fails_fast(self) -> None:
        raw = {
            "asset_id": "BAD",
            "display_name": "Bad pack",
            "version": "1",
            "factors": [
                {"id": "x", "label": "X", "category": "test", "decay_half_life_days": 1}
            ],
            "weights": {h.value: {"x": 0.5} for h in Horizon},
            "horizon_weights": {"structural": 0.4, "intermediate": 0.4, "tactical": 0.2},
        }
        with self.assertRaisesRegex(ValueError, "factor weights must sum to 1"):
            AssetPack.from_dict(raw)


if __name__ == "__main__":
    unittest.main()
