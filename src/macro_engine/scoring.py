from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

from .config import AssetPack
from .domain import Direction, Evidence, FactorResult, Horizon, HorizonResult


def direction_for(score: float) -> Direction:
    if score <= -70:
        return Direction.STRONG_BEARISH
    if score <= -20:
        return Direction.BEARISH
    if score < 20:
        return Direction.NEUTRAL
    if score < 70:
        return Direction.BULLISH
    return Direction.STRONG_BULLISH


class TransparentScorer:
    """Deterministic scoring; AI may normalize evidence but never sets final direction."""

    def score_horizon(
        self, pack: AssetPack, horizon: Horizon, evidence: list[Evidence], as_of: datetime
    ) -> HorizonResult:
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            if item.horizon == horizon and item.factor in pack.weights[horizon]:
                grouped[item.factor].append(item)

        results: list[FactorResult] = []
        for factor_id, weight in pack.weights[horizon].items():
            observations = grouped[factor_id]
            if not observations:
                results.append(FactorResult(factor_id, 0, 0, 0, "No current evidence"))
                continue
            weighted_score = 0.0
            effective_weight = 0.0
            for item in observations:
                age = max(0.0, (as_of - item.observed_at).total_seconds())
                half_life = pack.half_life(factor_id, horizon).total_seconds()
                freshness = math.pow(0.5, age / half_life)
                strength = item.confidence * item.significance * freshness
                weighted_score += item.score * strength
                effective_weight += strength
            factor_score = weighted_score / effective_weight if effective_weight else 0.0
            confidence = min(1.0, effective_weight / max(1, len(observations)))
            # Confidence is part of impact, not merely a label. This prevents a stale,
            # low-significance observation from ranking as a top driver on raw magnitude alone.
            contribution = factor_score * weight * confidence
            summary = max(observations, key=lambda item: item.observed_at).summary
            results.append(
                FactorResult(factor_id, factor_score, confidence, contribution, summary)
            )

        score = sum(item.contribution for item in results)
        confidence = sum(
            item.confidence * pack.weights[horizon][item.factor] for item in results
        )
        return HorizonResult(
            horizon=horizon,
            score=round(score, 2),
            confidence=round(confidence, 4),
            direction=direction_for(score),
            factors=tuple(results),
        )
