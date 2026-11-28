"""The position-residual tool of the order-key study (2.62.7, task "너"): the definitions are fixed before the first run (PREDICTIONS_POSITION_RESIDUAL_2026-11-28.md)."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
sys.path.insert(0, str(V2 / "benchmark" / "association_truth"))
sys.path.insert(0, str(V2 / "benchmark"))
import association_model as am  # noqa: E402

spec = importlib.util.spec_from_file_location("position_residual_tool", V2 / "benchmark" / "association_truth" / "position_residual.py")
PR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PR)

ARC = 1.0 / 3600.0


def test_the_vectorised_sigma_is_the_effective_sigma_of_the_pipeline():
    rows = pd.DataFrame([dict(catalog="AllWISE", poserr_arcsec=0.5, psf_fwhm_arcsec=6.1), dict(catalog="2MASS PSC", poserr_arcsec=0.25, psf_fwhm_arcsec=2.5),
                         dict(catalog="Pan-STARRS1 DR2 MeanObject", poserr_arcsec=0.04, psf_fwhm_arcsec=np.nan), dict(catalog="X", poserr_arcsec=0.001, psf_fwhm_arcsec=np.nan),
                         dict(catalog="DESI Legacy Surveys DR10", poserr_arcsec=0.6, psf_fwhm_arcsec=1.0)])  # fmt: skip
    got = PR.eff_sigma(rows)
    for g, r in zip(got, rows.to_dict("records")):
        det = {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}
        assert g == pytest.approx(am.effective_sigma_arcsec(det))


def test_a_clean_object_reaches_exactly_one_truth_source_and_the_residual_is_the_anchor_distance():
    truth = pd.DataFrame({"ra": [150.0, 150.01, 150.02], "dec": [2.0, 2.0, 2.0], "HSCimagAuto": [21.0, 22.0, 30.0]})  # the third is fainter than the reference limit (i < 25)
    ls, ps1 = "DESI Legacy Surveys DR10", "Pan-STARRS1 DR2 MeanObject"
    a = pd.DataFrame([
        dict(object_id="O1", catalog=ls, ra=150.0 + 0.1 * ARC, dec=2.0, object_ra=150.0 + 0.1 * ARC, object_dec=2.0, object_anchor_catalog=ls),  # 0.1'' from truth 0
        dict(object_id="O2", catalog=ls, ra=150.01, dec=2.0, object_ra=150.01, object_dec=2.0, object_anchor_catalog=ls),  # truth 1 ...
        dict(object_id="O2", catalog=ps1, ra=150.01 + 0.2 * ARC, dec=2.0, object_ra=150.01, object_dec=2.0, object_anchor_catalog=ls),
        dict(object_id="O3", catalog=ls, ra=150.0, dec=2.0, object_ra=150.0, object_dec=2.0, object_anchor_catalog=ls),  # O3 and O4 reach truth 0 too: two objects, one source
        dict(object_id="O4", catalog=ls, ra=150.5, dec=2.0, object_ra=150.5, object_dec=2.0, object_anchor_catalog=ls),  # reaches nothing
        dict(object_id="O5", catalog=ls, ra=150.0, dec=2.0, object_ra=150.0, object_dec=2.0, object_anchor_catalog=ls),
        dict(object_id="O5", catalog=ls, ra=150.01, dec=2.0, object_ra=150.0, object_dec=2.0, object_anchor_catalog=ls),  # two truth sources in one object: not clean
    ]).drop(columns=["dec_"], errors="ignore")
    c = PR.clean_objects(a, truth)
    assert set(c.object_id) == {"O1", "O2", "O3"} and "O5" not in set(c.object_id) and "O4" not in set(c.object_id)
    r = c.set_index("object_id").residual
    assert r["O1"] == pytest.approx(0.1, abs=0.01) and r["O2"] == pytest.approx(0.0, abs=0.01) and r["O3"] == pytest.approx(0.0, abs=0.01)


def test_summary_counts_the_shares_beyond_each_threshold():
    s = PR.summarise(pd.Series([0.05, 0.1, 0.4, 0.6, 0.8, 1.5]))
    assert s["objects"] == 6 and s["beyond_0.5_pct"] == pytest.approx(50.0) and s["beyond_1.0_pct"] == pytest.approx(100 / 6, abs=0.01) and s["beyond_0.3_pct"] == pytest.approx(4 / 6 * 100, abs=0.01)


def test_output_position_designs_pick_the_most_precise_member_and_the_weighted_mean():
    truth = pd.DataFrame({"ra": [150.0], "dec": [2.0], "HSCimagAuto": [21.0]})
    aw, ls = "AllWISE", "DESI Legacy Surveys DR10"
    off = 1.0 * ARC  # the AllWISE row is the anchor and lies 1'' off; the LS row is on the source
    a = pd.DataFrame([
        dict(object_id="O1", catalog=aw, ra=150.0 + off, dec=2.0, poserr_arcsec=0.5, psf_fwhm_arcsec=6.1, object_ra=150.0 + off, object_dec=2.0, object_anchor_catalog=aw),
        dict(object_id="O1", catalog=ls, ra=150.0, dec=2.0, poserr_arcsec=0.1, psf_fwhm_arcsec=1.0, object_ra=150.0 + off, object_dec=2.0, object_anchor_catalog=aw),
    ])  # fmt: skip
    # the AllWISE row must reach the truth for the object to be clean: it is not resolving, the LS row is (0 '' from the source)
    c = PR.clean_objects(a, truth)
    assert len(c) == 1 and c.residual.iloc[0] == pytest.approx(1.0, abs=0.01)
    d = PR.designs(a, c, truth)
    assert d["anchor"][0] == pytest.approx(1.0, abs=0.01)
    assert d["best_member"][0] < 0.01  # the LS row (sigma 0.167'') beats the AllWISE row (1.017'')
    assert 0.0 <= d["ivw_mean"][0] < 0.1  # resolving members only: the LS row
