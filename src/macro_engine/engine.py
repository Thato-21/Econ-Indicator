from __future__ import annotations

from datetime import datetime

from .domain import Evidence, Horizon, RegimeAssessment, utc_now
from .registry import AssetRegistry
from .scoring import TransparentScorer, direction_for


class MacroEngine:
    def __init__(self, registry: AssetRegistry | None = None) -> None:
        self.registry = registry or AssetRegistry()
        self.scorer = TransparentScorer()

    def assess(
        self, asset_id: str, evidence: list[Evidence], as_of: datetime | None = None
    ) -> RegimeAssessment:
        as_of = as_of or utc_now()
        pack = self.registry.load(asset_id)
        horizons = tuple(
            self.scorer.score_horizon(pack, horizon, evidence, as_of) for horizon in Horizon
        )
        overall = sum(item.score * pack.horizon_weights[item.horizon] for item in horizons)
        confidence = sum(
            item.confidence * pack.horizon_weights[item.horizon] for item in horizons
        )
        contradictions = self._contradictions(horizons)
        strongest = sorted(
            (factor for horizon in horizons for factor in horizon.factors),
            key=lambda factor: abs(factor.contribution),
            reverse=True,
        )[:3]
        drivers = ", ".join(f"{item.factor} ({item.score:+.0f})" for item in strongest)
        narrative = f"{direction_for(overall).value.replace('_', ' ').title()} regime; key drivers: {drivers}."
        return RegimeAssessment(
            asset_id=pack.asset_id,
            pack_version=pack.version,
            generated_at=as_of,
            overall_score=round(overall, 2),
            overall_confidence=round(confidence, 4),
            direction=direction_for(overall),
            horizons=horizons,
            contradictions=contradictions,
            narrative=narrative,
        )

    @staticmethod
    def _contradictions(horizons) -> tuple[str, ...]:
        conflicts: list[str] = []
        for horizon in horizons:
            bullish = [f.factor for f in horizon.factors if f.contribution >= 5]
            bearish = [f.factor for f in horizon.factors if f.contribution <= -5]
            if bullish and bearish:
                conflicts.append(
                    f"{horizon.horizon.value}: bullish {', '.join(bullish)} vs bearish {', '.join(bearish)}"
                )
        return tuple(conflicts)

