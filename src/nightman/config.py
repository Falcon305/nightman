from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field

_CONF_RANK = {"heuristic": 0, "high": 1, "verified": 2}


@dataclass
class Config:
    exclude: list[str] = field(default_factory=list)
    min_confidence: str = "heuristic"
    allow: dict[str, list[str]] = field(default_factory=dict)

    def allowed_for(self, func: str) -> list[str]:
        return list(self.allow.get(func, [])) + list(self.allow.get("*", []))

    def confidence_rank(self, confidence: str) -> int:
        return _CONF_RANK.get(confidence, 0)

    def meets_confidence(self, confidence: str) -> bool:
        return self.confidence_rank(confidence) >= self.confidence_rank(self.min_confidence)


def _from_table(table: dict) -> Config:
    allow_raw = table.get("allow", {})
    allow = {str(k): [str(x) for x in v] for k, v in allow_raw.items()} if isinstance(allow_raw, dict) else {}
    return Config(
        exclude=[str(x) for x in table.get("exclude", [])],
        min_confidence=str(table.get("min_confidence", "heuristic")),
        allow=allow,
    )


def load_config(root: str = ".") -> Config:
    standalone = os.path.join(root, ".nightman.toml")
    if os.path.exists(standalone):
        with open(standalone, "rb") as handle:
            return _from_table(tomllib.load(handle))
    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.exists(pyproject):
        with open(pyproject, "rb") as handle:
            data = tomllib.load(handle)
        table = data.get("tool", {}).get("nightman", {})
        if table:
            return _from_table(table)
    return Config()
