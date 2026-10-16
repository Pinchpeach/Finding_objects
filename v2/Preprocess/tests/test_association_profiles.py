"""Survey position errors and the R90 sky mask follow the literature (2.16.0)."""

import importlib.util
import math
import sys
from pathlib import Path

PRE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRE))
import association_model as am  # noqa: E402


def _stage4():
    s = importlib.util.spec_from_file_location("s4", PRE / "04_build_evidence.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_chandra_r0_is_95_percent_radius():
    # r0 = 2.448 sigma for a 2-D Gaussian, plus the 0.16" systematic.
    assert math.isclose(am.infer_poserr_arcsec("Chandra CSC 2.0", {"r0": 2.448}), math.hypot(1.0, 0.16))


def test_legacy_surveys_ivar_and_profile():
    sigma_deg = 0.05 / 3600.0
    row = {"ra_ivar": 1 / sigma_deg**2, "dec_ivar": 1 / sigma_deg**2, "dec": 0.0}
    assert math.isclose(am.infer_poserr_arcsec("DESI Legacy Surveys DR10", row), 0.05, rel_tol=1e-9)
    assert am.infer_psf_arcsec("DESI Legacy Surveys DR10", {}) == 1.2
    assert am.infer_psf_arcsec("Pan-STARRS1 DR2 MeanObject", {}) == 1.2


def test_erass_and_ps1_epoch():
    assert am.infer_poserr_arcsec("eROSITA eRASS1", {"POS_ERR": 3.0}) == 3.0
    assert am.infer_poserr_arcsec("eROSITA eRASS1", {}) == 4.5
    # epochMean is an MJD: 55197 = 2010.0
    assert abs(am.infer_epoch("Pan-STARRS1 DR2 MeanObject", {"epochMean": 55197.0}) - 2010.0) < 0.01


def test_r90_sky_mask():
    m = _stage4()
    assert not m._r90_sky(266.405, -28.936)  # Galactic Centre
    assert not m._r90_sky(83.63, 22.01)  # Crab, b = -5.8
    assert m._r90_sky(150.1, 2.2)  # COSMOS
    assert m._r90_sky(None, None)


def test_desi_target_position_is_not_ambiguous_next_to_a_star():
    # Field RA 250 (2.27.0): a DESI spectrum 0.01" from its LS source and
    # 0.34" from a Gaia-anchored star was "ambiguous_new" with the 0.6"
    # default error; TARGET_RA/DEC are imaging positions (2.28.0).
    dec = 30.0
    cosd = math.cos(math.radians(dec))

    def det(cat, dra_arcsec, **extra):
        return {
            "catalog": cat,
            "ra": 250.0 + dra_arcsec / 3600.0 / cosd,
            "dec": dec,
            "poserr_arcsec": am.infer_poserr_arcsec(cat, extra),
            "psf_fwhm_arcsec": am.infer_psf_arcsec(cat, extra),
            "ref_epoch": None,
            **extra,
        }

    desi = det("DESI DR1 spectroscopy", 0.0)
    ls_target = det("DESI Legacy Surveys DR10", 0.01, type="REX")
    star = det("Gaia DR3", 0.34)
    s_target = am.assess_pair(ls_target, desi)["association_score"]
    s_star = am.assess_pair(star, desi)["association_score"]
    assert s_star < 0.67 * s_target  # AMBIG_SCORE_RATIO: no longer ambiguous


def _stage1():
    s = importlib.util.spec_from_file_location("s1", PRE / "01_source_association.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_desi_spectrum_joins_its_shredded_ls_galaxy(tmp_path):
    # Field RA 250 (2.28.0): a DESI galaxy spectrum on its LS source, with PS1
    # and SDSS fragments of the same galaxy 0.3-0.4" away, became its own
    # evidence-less object.  Spectra now attach to their LS target.
    import pandas as pd

    dec = 30.0
    cosd = math.cos(math.radians(dec))

    def rows(cat, offsets, **cols):
        return pd.DataFrame(
            [
                {
                    "catalog": cat,
                    "catalog_object_id": f"{cat[:4]}{i}",
                    "ra": 250.0 + dx / 3600 / cosd,
                    "dec": dec,
                    **cols,
                }
                for i, dx in enumerate(offsets)
            ]
        )

    rows("DESI Legacy Surveys DR10", [0.0], type="REX").to_csv(tmp_path / "desi_legacy.csv", index=False)
    rows("Pan-STARRS1 DR2 MeanObject", [0.31, -0.36]).to_csv(tmp_path / "panstarrs1.csv", index=False)
    rows("SDSS DR18 PhotoObj", [0.37]).to_csv(tmp_path / "sdss.csv", index=False)
    tid = "39628481746698530"  # DR9 south target: no LS DR10 identifier match
    rows("DESI DR1 spectroscopy", [0.0]).assign(catalog_object_id=tid).to_csv(tmp_path / "desi_spec.csv", index=False)
    rows("DESI DR1 FastSpecFit", [0.0]).assign(catalog_object_id=tid).to_csv(tmp_path / "desi_fsf.csv", index=False)
    out = tmp_path / "assoc.csv"
    _stage1().run(tmp_path, out)
    a = pd.read_csv(out).set_index("catalog").object_id
    assert a["DESI DR1 spectroscopy"] == a["DESI Legacy Surveys DR10"] == a["DESI DR1 FastSpecFit"]


def test_duplicate_spectrum_does_not_move_to_a_neighbour(tmp_path):
    # Field RA 20 (2.28.0): two DESI spectra of one target; the second must
    # not attach to a GALEX detection 1.6" away.
    import pandas as pd

    def one(cat, dx, cid, **cols):
        return {"catalog": cat, "catalog_object_id": cid, "ra": 20.0 + dx / 3600, "dec": 0.0, **cols}

    pd.DataFrame([one("DESI Legacy Surveys DR10", 0.0, "L1", type="EXP")]).to_csv(tmp_path / "ls.csv", index=False)
    # A star 3.0" away makes the GALEX detection between them ambiguous, so it
    # stands alone, as in the field.
    pd.DataFrame([one("Gaia DR3", 3.0, "S1")]).to_csv(tmp_path / "gaia.csv", index=False)
    pd.DataFrame([one("GALEX AIS", 1.62, "G1")]).to_csv(tmp_path / "galex.csv", index=False)
    pd.DataFrame(
        [
            one("DESI DR1 spectroscopy", 0.02, "39627785060228797"),
            one("DESI DR1 spectroscopy", 0.01, "39627785060228111"),
        ]
    ).to_csv(tmp_path / "spec.csv", index=False)
    out = tmp_path / "assoc.csv"
    _stage1().run(tmp_path, out)
    a = pd.read_csv(out)
    ls_obj = a.loc[a.catalog.eq("DESI Legacy Surveys DR10"), "object_id"].iloc[0]
    spec_objs = set(a.loc[a.catalog.eq("DESI DR1 spectroscopy"), "object_id"])
    assert ls_obj in spec_objs  # one spectrum on its target
    for oid in spec_objs - {ls_obj}:  # the duplicate stands alone, it joins nothing else
        assert set(a.loc[a.object_id.eq(oid), "catalog"]) == {"DESI DR1 spectroscopy"}
