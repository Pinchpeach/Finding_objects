from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

LINE_LIBRARY = {
    "Halpha": 6562.8, "Hbeta": 4861.3, "OIII_5007": 5006.8,
    "OII_3727": 3727.0, "NII_6583": 6583.4, "SII_6716": 6716.4,
    "SII_6731": 6730.8, "CaII_K": 3933.7, "CaII_H": 3968.5,
    "MgII_2796": 2796.4, "MgII_2803": 2803.5, "NaI_D": 5892.9,
    "FeII_2600": 2600.2, "CIV_1549": 1549.5, "Lyalpha": 1215.7,
}

@dataclass(frozen=True)
class SpectralLine:
    name: str
    rest_wavelength: float
    observed_wavelength: float
    equivalent_width: float | None = None
    kind: str = "unknown"  # emission / absorption / unknown

    @property
    def tag(self) -> str:
        return f"line:{self.name}:{self.kind}"

def line_tags(lines: list[SpectralLine]) -> list[str]:
    return sorted({line.tag for line in lines})

def object_tags(object_type: str | None, properties: dict | None = None) -> list[str]:
    tags = []
    if object_type:
        safe = re.sub(r"[^a-z0-9_+-]+", "_", object_type.lower()).strip("_")
        tags.append(f"object:{safe}")
    for key, value in (properties or {}).items():
        if value is not None:
            tags.append(f"property:{key}={value}")
    return sorted(set(tags))

def classify_from_lines(lines: list[SpectralLine]) -> tuple[str, list[str]]:
    """Conservative rule-based first pass; intended for triage, not final science."""
    names = {x.name for x in lines if x.kind == "emission"}
    if {"Halpha", "OIII_5007"} <= names:
        kind = "emission_line_object"
    elif any(x.kind == "absorption" for x in lines):
        kind = "absorption_line_object"
    else:
        kind = "spectral_object_unclassified"
    return kind, object_tags(kind)
