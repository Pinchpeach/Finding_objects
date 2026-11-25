"""Likelihood-ratio diagnostics of the association stage and the measurement helpers (2.60.9)."""

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
import association_model as am  # noqa: E402
import measure_association as ma  # noqa: E402


def _det(ra, dec, err, psf=None, **kw):
    d = dict(ra=ra, dec=dec, poserr_arcsec=err, psf_fwhm_arcsec=psf, ref_epoch=None, max_radius_arcsec=5.0)
    d.update(kw)
    return d


def test_the_posterior_is_the_likelihood_ratio_over_one_plus_it():
    r = am.assess_pair(_det(10.0, 5.0, 0.3), _det(10.0 + 0.4 / 3600, 5.0, 0.4), density_arcsec2=0.004)
    lr = r["likelihood_ratio"]
    assert lr is not None and lr > 0
    assert math.isclose(r["association_posterior"], lr / (1.0 + lr), rel_tol=1e-12)
    assert am.assess_pair(_det(10.0, 5.0, 0.3), _det(10.0, 5.0, 0.4), None)["likelihood_ratio"] is None


def test_stage_1_writes_the_ratio_columns_and_changes_nothing_else(tmp_path):
    spec = importlib.util.spec_from_file_location("s1_diag", V2 / "Preprocess" / "01_source_association.py")
    s1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s1)
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = []
    rng = np.random.default_rng(1)
    for i in range(30):  # a field with enough rows for a density estimate
        rows.append(dict(catalog="DESI Legacy Surveys DR10", catalog_object_id=f"ls{i}", ra=150 + 0.003 * (i % 6),
                         dec=2 + 0.003 * (i // 6), query_radius_arcmin=1.0))  # fmt: skip
    pd.DataFrame(rows).to_csv(raw / "desi_legacy_x.csv", index=False)
    wise = [dict(catalog="AllWISE", catalog_object_id=f"w{i}", ra=150 + 0.003 * (i % 6) + 0.0001, dec=2 + 0.003 * (i // 6),
                 query_radius_arcmin=1.0) for i in range(6)]  # fmt: skip
    pd.DataFrame(wise).to_csv(raw / "allwise_x.csv", index=False)
    out = tmp_path / "assoc.csv"
    s1.run(raw, out)
    t = pd.read_csv(out)
    assert {"likelihood_ratio", "lr_sum_candidates"} <= set(t.columns)
    m = t[t.association_status == "matched"]
    assert len(m) and m.likelihood_ratio.notna().all()
    assert (m.lr_sum_candidates >= m.likelihood_ratio - 1e-9).all()  # the joined candidate is one of the summed ones
    new = t[t.association_status == "new"]
    assert new.likelihood_ratio.isna().all()


def test_wilson_and_the_sky_helper():
    lo, hi = ma.wilson(5, 100)
    assert 2.0 < lo < 5.0 < hi < 12.0
    sky = ma.Sky(np.array([10.0, 10.0]), np.array([0.0, 1.0]))
    i, s = sky.nearest(np.array([10.0]), np.array([0.0002]), 5.0)
    assert i[0] == 0 and abs(s[0] - 0.72) < 0.01
    assert sky.nearest(np.array([10.0]), np.array([0.5]), 5.0)[0][0] == -1
