from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .domain import Horizon


@dataclass(frozen=True)
class FactorConfig:
    id: str
    label: str
    category: str
    decay_half_life_days: int


@dataclass(frozen=True)
class AssetPack:
    asset_id: str
    display_name: str
    version: str
    factors: tuple[FactorConfig, ...]
    weights: dict[Horizon, dict[str, float]]
    horizon_weights: dict[Horizon, float]
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AssetPack:
        pack = cls(
            asset_id=raw["asset_id"],
            display_name=raw["display_name"],
            version=raw["version"],
            factors=tuple(FactorConfig(**item) for item in raw["factors"]),
            weights={Horizon(k): v for k, v in raw["weights"].items()},
            horizon_weights={Horizon(k): v for k, v in raw["horizon_weights"].items()},
            metadata=raw.get("metadata", {}),
        )
        pack.validate()
        return pack

    def validate(self) -> None:
        factor_ids = {factor.id for factor in self.factors}
        if len(factor_ids) != len(self.factors):
            raise ValueError(f"{self.asset_id}: duplicate factor id")
        if set(self.weights) != set(Horizon):
            raise ValueError(f"{self.asset_id}: every horizon requires weights")
        for horizon, weights in self.weights.items():
            unknown = set(weights) - factor_ids
            if unknown:
                raise ValueError(f"{self.asset_id}/{horizon}: unknown factors {unknown}")
            if abs(sum(weights.values()) - 1.0) > 1e-6:
                raise ValueError(f"{self.asset_id}/{horizon}: factor weights must sum to 1")
            if any(weight < 0 for weight in weights.values()):
                raise ValueError(f"{self.asset_id}/{horizon}: weights cannot be negative")
        if set(self.horizon_weights) != set(Horizon):
            raise ValueError(f"{self.asset_id}: every horizon requires an overall weight")
        if abs(sum(self.horizon_weights.values()) - 1.0) > 1e-6:
            raise ValueError(f"{self.asset_id}: horizon weights must sum to 1")

    def half_life(self, factor_id: str) -> timedelta:
        factor = next((item for item in self.factors if item.id == factor_id), None)
        if factor is None:
            raise KeyError(f"factor {factor_id!r} is not in asset pack {self.asset_id!r}")
        return timedelta(days=factor.decay_half_life_days)

