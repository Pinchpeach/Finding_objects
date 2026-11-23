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


def test_pools_come_from_the_region_name_and_aggregate_each_one():
    """Locked set C (2.57.0): csth / cpln / clam aggregates, no per-object output."""
    assert (
        FS.pool_of("csth_304m58") == "csth"
        and FS.pool_of("clam_113p02") == "clam"
        and FS.pool_of("deep_cosmos_5") == "deep"
    )
    rng = np.random.default_rng(5)
    rows = []
    for pool, n_reg, err in (("csth", 4, 0.02), ("cpln", 3, 0.20), ("clam", 5, 0.05)):
        for f in range(n_reg):
            for _ in range(40):
                t = rng.choice(["STAR", "GALAXY", "QSO"], p=[0.8, 0.15, 0.05])
                rows.append({"field": f"{pool}_{f}", "t_truth": t, "ours": t if rng.random() > err else "STAR"})
    m = pd.DataFrame(rows)
    out = {r["pool"]: r for r in FS.by_pool(m, nboot=100)}
    assert set(out) == {"cpln", "csth", "clam"}
    assert (out["csth"]["n_regions"], out["cpln"]["n_regions"], out["clam"]["n_regions"]) == (4, 3, 5)
    assert out["csth"]["n"] == 160 and out["clam"]["n"] == 200
    assert (
        out["cpln"]["acc"] < out["clam"]["acc"] < out["csth"]["acc"] + 1e-9 or out["cpln"]["acc"] < out["csth"]["acc"]
    )
    assert out["cpln"]["acc_lo"] <= out["cpln"]["acc"] <= out["cpln"]["acc_hi"]
    # aggregate only: nothing in a row is per object
    assert all(not isinstance(v, (list, np.ndarray, pd.Series)) for r in out.values() for v in r.values())
    assert FS.by_pool(m.iloc[0:0]) == []


def test_compare_ab_fields_writes_pool_aggregates_and_no_per_object_files(tmp_path, monkeypatch):
    import compare_ab_fields as CAB
    import score_independent_fields as S

    rng = np.random.default_rng(7)
    root = tmp_path / "ab"
    names = [f"csth_{i}" for i in range(3)] + [f"cpln_{i}" for i in range(2)] + [f"clam_{i}" for i in range(4)]
    for v in ("base", "new"):
        for f in names:
            d = root / v / f
            d.mkdir(parents=True)
            (d / "field.json").write_text("{}")
            (d / "objects_blind.csv.gz").write_text("")

    def fake_matches(fdir, mode, bench):
        rows = []
        for k in range(30):
            t = rng.choice(["STAR", "GALAXY", "QSO"], p=[0.8, 0.15, 0.05])
            rows.append(
                {
                    "t_ra": fdir.name.__hash__() % 360 + k * 1e-3,
                    "t_dec": 1.0,
                    "t_truth": t,
                    "t_survey": "x",
                    "t_n_fragments": 0,
                    "ours": t,
                }
            )
        return pd.DataFrame(rows), {"n_truth": 30, "unmatched": 0, "in_bench": 0}

    monkeypatch.setattr(S, "field_matches", fake_matches)
    monkeypatch.setattr(S, "benchmark_positions", lambda: None)
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        ["compare_ab_fields.py", str(root), "--aggregate-only", "--by-pool", "--nboot", "50", "--out", str(out)],
    )
    CAB.main()
    pool = pd.read_csv(out / "ab_summary_by_pool.csv")
    assert set(pool.pool) == {"csth", "cpln", "clam"} and set(pool.variant) == {"base", "new"}
    assert pool.set_index(["variant", "pool"]).loc[("base", "clam"), "n_regions"] == 4
    assert sorted(p.name for p in out.iterdir()) == ["ab_summary.csv", "ab_summary_by_pool.csv"]  # aggregates only
