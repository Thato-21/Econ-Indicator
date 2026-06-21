from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from .config import AssetPack


class AssetRegistry:
    """Loads versioned asset packs without coupling the engine to a particular market."""

    def __init__(self, pack_directory: Path | None = None) -> None:
        self._directory = pack_directory
        self._packs: dict[str, AssetPack] = {}

    def load(self, asset_id: str) -> AssetPack:
        key = asset_id.upper()
        if key not in self._packs:
            if self._directory:
                path = self._directory / f"{key.lower()}.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
            else:
                resource = files("macro_engine").joinpath("assets", f"{key.lower()}.json")
                raw = json.loads(resource.read_text(encoding="utf-8"))
            self._packs[key] = AssetPack.from_dict(raw)
        return self._packs[key]

