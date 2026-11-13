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


def test_xmatch_rows_follow_the_cone_schema():
    import collect_catalog_truth as C

    truth = pd.DataFrame({"benchmark_id": ["A", "B"], "ra": [10.0, 20.0], "dec": [1.0, 2.0],
                          "truth_class": ["STAR", "QSO"], "truth_source": "SDSS"})
    xm = pd.DataFrame({"benchmark_id": ["A", "A", "B"], "truth_ra": [10, 10, 20], "truth_dec": [1, 1, 2],
                       "angDist": [0.5, 1.2, 9.0], "objid": [1, 2, 3], "RAJ2000": [10, 10, 20],
                       "DEJ2000": [1, 1, 2], "NUVmag": [20.1, 21.0, 19.0]})
    o = C.from_xmatch(xm, truth, "galex", "GALEX AIS")
    # nearest row kept; B is beyond the 5" GALEX match radius
    assert o.benchmark_id.tolist() == ["A"] and o.catalog_object_id.iloc[0] == "1"
    assert list(o.columns[:11]) == ["benchmark_id", "truth_class", "truth_source", "truth_ra", "truth_dec",
                                    "match_threshold_arcsec", "catalog", "catalog_object_id", "object_name", "ra", "dec"]
    assert o._sep_arcsec.iloc[0] == 0.5


def test_vizier_multitarget_rows_map_back_to_their_targets():
    import collect_catalog_truth as C

    chunk = pd.DataFrame({"benchmark_id": ["A", "B", "C"], "ra": [10.0, 20.0, 30.0], "dec": [0.0, 0.0, 0.0],
                          "truth_class": ["STAR", "QSO", "GALAXY"], "truth_source": "SDSS"})
    # _q is the 1-based index of the target in the request; C has no row
    d = pd.DataFrame({"_q": [1, 2, 2], "2MASS": ["a", "b1", "b2"],
                      "RAJ2000": [10.0, 20.0 + 1.0 / 3600, 20.0 + 2.2 / 3600], "DEJ2000": [0.0, 0.0, 0.0]})
    xm = C.from_vizier_batch(d, chunk)
    assert xm.benchmark_id.tolist() == ["A", "B", "B"]
    assert abs(xm.angDist.iloc[1] - 1.0) < 0.01
    o = C.from_xmatch(xm, chunk, "twomass", "2MASS PSC")
    assert o.benchmark_id.tolist() == ["A", "B"] and o.catalog_object_id.tolist() == ["a", "b1"]
