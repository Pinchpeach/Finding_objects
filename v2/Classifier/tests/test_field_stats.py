"""Field-level statistics used for every reported score (2.51.0)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmark"))
import field_stats as FS  # noqa: E402


def _frame():
    rng = np.random.default_rng(3)
    rows = []
    for f in range(20):
        for _ in range(50):
            t = rng.choice(["STAR", "GALAXY", "QSO"], p=[0.7, 0.2, 0.1])
            rows.append({"field": f"f{f}", "t_truth": t, "ours": t if rng.random() < 0.9 else "STAR"})
    return pd.DataFrame(rows)


def test_summary_has_ci_balanced_accuracy_and_baselines():
    s = FS.summary(_frame(), nboot=200)
    assert s["acc_lo"] <= s["acc"] <= s["acc_hi"]
    assert s["bal_lo"] <= s["bal_acc"] <= s["bal_hi"]
    # predicting STAR on errors lowers GALAXY/QSO recall, so balanced < plain accuracy
    assert s["bal_acc"] < s["acc"]
    assert s["baseline_majority"].startswith("STAR")
    assert s["precision_GALAXY"] == 100.0


def test_mcnemar_paired():
    a = np.array([True] * 90 + [False] * 10)
    assert FS.mcnemar(a, a)[0] == 1.0
    b = a.copy()
    b[:20] = False  # base wrong on 20 objects the variant gets right
    p, only_a, only_b = FS.mcnemar(a, b)
    assert (only_a, only_b) == (20, 0) and p < 1e-4


def test_sky_cells_are_equal_area_and_split_whole():
    import build_sdss_sky_truth as B
    import validate_catalog_truth as V

    rng = np.random.default_rng(1)
    ra = rng.uniform(0, 360, 50000)
    dec = np.degrees(np.arcsin(rng.uniform(-1, 1, 50000)))
    c = B.sky_cell(ra, dec)
    counts = np.bincount(c, minlength=768)
    assert c.min() == 0 and c.max() == 767
    assert counts.std() / counts.mean() < 0.25  # uniform sky -> similar counts per cell
    split = pd.Series(c).astype(str).map(lambda v: V.split_for(f"cell:{v}"))
    assert pd.DataFrame({"c": c, "s": split}).groupby("c").s.nunique().max() == 1
    d = pd.DataFrame({"ra": ra[:2000], "dec": dec[:2000], "sky_cell": c[:2000]})
    assert B.spread(d, 700, 0).sky_cell.value_counts().max() == 1  # one per cell before any repeats
