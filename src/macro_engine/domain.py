from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class Horizon(StrEnum):
    STRUCTURAL = "structural"
    INTERMEDIATE = "intermediate"
    TACTICAL = "tactical"


class Direction(StrEnum):
    STRONG_BEARISH = "strong_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    STRONG_BULLISH = "strong_bullish"


@dataclass(frozen=True)
class Evidence:
    """Normalized evidence. Direction is always from the target asset's perspective."""

    factor: str
    horizon: Horizon
    score: float
    confidence: float
    observed_at: datetime
    source: str
    summary: str
    significance: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not -100 <= self.score <= 100:
            raise ValueError("evidence score must be between -100 and 100")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not 0 <= self.significance <= 1:
            raise ValueError("significance must be between 0 and 1")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class FactorResult:
    factor: str
    score: float
    confidence: float
    contribution: float
    explanation: str


@dataclass(frozen=True)
class HorizonResult:
    horizon: Horizon
    score: float
    confidence: float
    direction: Direction
    factors: tuple[FactorResult, ...]


@dataclass(frozen=True)
class RegimeAssessment:
    asset_id: str
    pack_version: str
    generated_at: datetime
    overall_score: float
    overall_confidence: float
    direction: Direction
    horizons: tuple[HorizonResult, ...]
    contradictions: tuple[str, ...]
    narrative: str


class EvidenceRepository(Protocol):
    def latest(self, asset_id: str, as_of: datetime) -> list[Evidence]: ...


class AssessmentRepository(Protocol):
    def save(self, assessment: RegimeAssessment) -> None: ...

    def latest(self, asset_id: str) -> RegimeAssessment | None: ...


def utc_now() -> datetime:
    return datetime.now(UTC)

