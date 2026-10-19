"""The 4 persona rule sets (demo assumptions — not a design standard)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from accesstwin import config


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    allow_step: bool
    max_curb_cm: float
    max_slope_pct: float
    min_width_cm: float
    bad_surfaces: tuple[str, ...] = field(default_factory=tuple)
    max_trip_m: float = 1000
    prefers_covered: bool = False
    needs_tactile: bool = False
    equity_weight: float = 1.0


def load_personas(path: Path | str | None = None) -> dict[str, Persona]:
    with open(path or config.PERSONAS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        key: Persona(
            key=key,
            label=v["label"],
            allow_step=bool(v["allow_step"]),
            max_curb_cm=float(v["max_curb_cm"]),
            max_slope_pct=float(v["max_slope_pct"]),
            min_width_cm=float(v["min_width_cm"]),
            bad_surfaces=tuple(v.get("bad_surfaces", [])),
            max_trip_m=float(v["max_trip_m"]),
            prefers_covered=bool(v.get("prefers_covered", False)),
            needs_tactile=bool(v.get("needs_tactile", False)),
            equity_weight=float(v.get("equity_weight", 1.0)),
        )
        for key, v in raw.items()
    }


def get_persona(key: str, personas: dict[str, Persona] | None = None) -> Persona:
    personas = personas or load_personas()
    return personas[key]
