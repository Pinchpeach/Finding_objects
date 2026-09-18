"""Cross-band counterpart association helpers."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class CounterpartEvidence:
    source_band: str
    counterpart_band: str
    separation_arcsec: float
    source_poserr_arcsec: float | None = None
    counterpart_poserr_arcsec: float | None = None
    source_beam_arcsec: float | None = None
    counterpart_is_unidentified: bool = False

def association_score(e: CounterpartEvidence) -> dict:
    """Return interpretable positional evidence, not a definitive identity claim."""
    s1 = e.source_poserr_arcsec or 0.0
    s2 = e.counterpart_poserr_arcsec or 0.0
    sigma = math.hypot(s1, s2)
    if sigma > 0:
        normalized_sep = e.separation_arcsec / sigma
        positional_likelihood = math.exp(-0.5 * normalized_sep**2)
    elif e.source_beam_arcsec:
        normalized_sep = e.separation_arcsec / max(e.source_beam_arcsec / 2.355, 1e-9)
        positional_likelihood = math.exp(-0.5 * normalized_sep**2)
    else:
        normalized_sep = None
        positional_likelihood = None
    return {
        "source_band": e.source_band,
        "counterpart_band": e.counterpart_band,
        "separation_arcsec": e.separation_arcsec,
        "normalized_separation": normalized_sep,
        "positional_likelihood": positional_likelihood,
        "counterpart_is_unidentified": e.counterpart_is_unidentified,
        "association_status": "candidate_counterpart",
    }
