"""Reproducible batch sampling and checkpoint helpers."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import random

@dataclass(frozen=True)
class SampleTarget:
    sample_id: int
    ra: float
    dec: float

def random_sky_targets(n: int = 1000, seed: int = 2609) -> list[SampleTarget]:
    """Generate reproducible positions uniform in solid angle."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        ra = rng.uniform(0.0, 360.0)
        z = rng.uniform(-1.0, 1.0)
        dec = __import__("math").degrees(__import__("math").asin(z))
        out.append(SampleTarget(i + 1, ra, dec))
    return out

def pending_targets(targets: list[SampleTarget], checkpoint: Path) -> list[SampleTarget]:
    if not checkpoint.exists():
        return targets
    done = {json.loads(line)["sample_id"] for line in checkpoint.read_text().splitlines() if line.strip()}
    return [t for t in targets if t.sample_id not in done]

def append_checkpoint(checkpoint: Path, record: dict) -> None:
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def random_footprint_targets(
    n: int = 1000,
    seed: int = 2609,
    *,
    ra_ranges: tuple[tuple[float, float], ...] = ((120.0, 240.0),),
    dec_range: tuple[float, float] = (-5.0, 65.0),
) -> list[SampleTarget]:
    """Reproducible solid-angle sampling inside a configurable survey footprint.

    The default is only an engineering test footprint; production runs should
    supply survey-derived coverage masks rather than assume every point is covered.
    """
    import math
    rng = random.Random(seed)
    widths = [hi - lo for lo, hi in ra_ranges]
    total = sum(widths)
    s0, s1 = math.sin(math.radians(dec_range[0])), math.sin(math.radians(dec_range[1]))
    out = []
    for i in range(n):
        pick = rng.uniform(0.0, total)
        acc = 0.0
        lo = hi = 0.0
        for (a, b), width in zip(ra_ranges, widths):
            acc += width
            if pick <= acc:
                lo, hi = a, b
                break
        ra = rng.uniform(lo, hi)
        dec = math.degrees(math.asin(rng.uniform(s0, s1)))
        out.append(SampleTarget(i + 1, ra, dec))
    return out
