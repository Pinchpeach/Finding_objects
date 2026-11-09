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


def test_spectrum_finds_its_target_when_another_survey_anchors_the_group(tmp_path):
    # Field RA 20 (2.28.0): the LS target was 0.02" from the spectrum but its
    # group was anchored by a PS1 detection 0.71" away, so FastSpecFit went by
    # position to a lone GALEX detection and the spectrum followed by alias.
    import pandas as pd

    def one(cat, dx, cid, dy=0.0, **cols):
        return {"catalog": cat, "catalog_object_id": cid, "ra": 20.0 + dx / 3600, "dec": dy / 3600, **cols}

    pd.DataFrame([one("Pan-STARRS1 DR2 MeanObject", 0.0, "P1", dy=0.71)]).to_csv(tmp_path / "ps1.csv", index=False)
    pd.DataFrame([one("DESI Legacy Surveys DR10", 0.0, "L1", type="EXP")]).to_csv(tmp_path / "ls.csv", index=False)
    pd.DataFrame([one("Gaia DR3", 3.4, "S1")]).to_csv(tmp_path / "gaia.csv", index=False)
    pd.DataFrame([one("GALEX AIS", 1.62, "G1")]).to_csv(tmp_path / "galex.csv", index=False)
    tid = "39627785060228797"
    pd.DataFrame([one("DESI DR1 spectroscopy", 0.02, tid)]).to_csv(tmp_path / "spec.csv", index=False)
    pd.DataFrame([one("DESI DR1 FastSpecFit", 0.02, tid)]).to_csv(tmp_path / "fsf.csv", index=False)
    out = tmp_path / "assoc.csv"
    _stage1().run(tmp_path, out)
    a = pd.read_csv(out).set_index("catalog").object_id
    assert a["DESI DR1 spectroscopy"] == a["DESI DR1 FastSpecFit"] == a["DESI Legacy Surveys DR10"]


def _annotation_field(tmp_path, ned):
    import pandas as pd

    dec = 30.0
    cosd = math.cos(math.radians(dec))
    pd.DataFrame(
        [{"catalog": "Pan-STARRS1 DR2 MeanObject", "catalog_object_id": "ps0", "ra": 250.0, "dec": dec}]
    ).to_csv(tmp_path / "panstarrs1.csv", index=False)
    pd.DataFrame(
        [
            {"catalog": "NED", "catalog_object_id": name, "ra": 250.0 + dx / 3600 / cosd, "dec": dec, "Type": t}
            for name, dx, t in ned
        ]
    ).to_csv(tmp_path / "ned.csv", index=False)
    out = tmp_path / "assoc.csv"
    _stage1().run(tmp_path, out)
    return pd.read_csv(out)


def test_band_only_ned_entries_join_one_star(tmp_path):
    # 2.47.0: NED keeps a star's 2MASS / WISE entries apart until it
    # cross-identifies them; they describe the photometric object.
    a = _annotation_field(tmp_path, [("2MASS J1", 0.1, "IrS"), ("WISEA J1", 0.2, "IrS"), ("CGCS 1", 0.05, "C*")])
    assert a.object_id.nunique() == 1


def test_supernova_and_its_host_galaxy_stay_apart(tmp_path):
    # Reference-object probe (SN 2005mq): NED lists the supernova and its host
    # at one position; both carry a physical type, so they are two objects.
    a = _annotation_field(tmp_path, [("SDSS J1", 0.0, "G"), ("SN 2005mq", 0.0, "SN")])
    ned = a[a.catalog == "NED"].set_index("catalog_object_id")
    assert ned.object_id["SDSS J1"] != ned.object_id["SN 2005mq"]


def test_physical_ned_type_is_read_before_band_detection(tmp_path):
    a = _annotation_field(tmp_path, [("CGCS 1", 0.05, "C*"), ("WISEA J1", 0.0, "IrS")])
    a.to_csv(tmp_path / "assoc.csv", index=False)
    s = importlib.util.spec_from_file_location("s2", PRE / "02_integrate_objects.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    out = tmp_path / "objects.csv"
    m.run(tmp_path / "assoc.csv", tmp_path, out)
    import pandas as pd

    o = pd.read_csv(out)
    assert len(o) == 1 and o["ned__Type"].iloc[0] == "C*"


def test_photometric_prior_rejects_a_red_wise_source_offset_from_a_star(tmp_path, monkeypatch):
    # Reference object J042925 (2.47.0): an AllWISE carbon star 4.8" from an
    # unrelated Gaia star (G - W1 ~ 11) was merged with it at 4.7 sigma.  With
    # the NWAY-style colour prior (opt-in) the pair is no longer accepted;
    # a normal-colour WISE counterpart is unaffected.
    import pandas as pd

    dec = 55.6
    cosd = math.cos(math.radians(dec))

    def field(w1, dx):
        pd.DataFrame([{"catalog": "Gaia DR3", "catalog_object_id": "g1", "ra": 67.0, "dec": dec, "phot_g_mean_mag": 17.5,
                       "ra_error": 0.1, "dec_error": 0.1}]).to_csv(tmp_path / "gaia.csv", index=False)
        pd.DataFrame([{"catalog": "AllWISE", "catalog_object_id": "w1", "ra": 67.0 + dx / 3600 / cosd, "dec": dec, "W1mag": w1}]).to_csv(
            tmp_path / "allwise.csv", index=False)
        out = tmp_path.parent / f"{tmp_path.name}_assoc.csv"  # outside the raw folder
        _stage1().run(tmp_path, out)
        return pd.read_csv(out).object_id.nunique()

    monkeypatch.setenv("V2_ASSOC_PHOT_PRIOR", "0")
    assert field(6.5, 4.6) == 1  # merged on position alone
    monkeypatch.setenv("V2_ASSOC_PHOT_PRIOR", "1")
    assert field(6.5, 4.6) == 2  # G - W1 = 11: not a counterpart
    assert field(14.5, 1.0) == 1  # G - W1 = 3, 1": still merged


def test_ls_forced_wise_replaces_allwise_photometry():
    s = importlib.util.spec_from_file_location("s2w", PRE / "02_integrate_objects.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    rec = {"allwise__W1mag": 12.0, "allwise__W2mag": 11.0, "allwise__snr1": 50.0, "allwise__snr2": 40.0,
           "desi_legacy_surveys_dr10__flux_w1": 100.0, "desi_legacy_surveys_dr10__flux_ivar_w1": 1.0,
           "desi_legacy_surveys_dr10__flux_w2": 100.0, "desi_legacy_surveys_dr10__flux_ivar_w2": 0.25}
    m.ls_forced_wise(rec)
    # 100 nanomaggies = AB 17.5; Vega W1 = 14.801, W2 = 14.161
    assert math.isclose(rec["allwise__W1mag"], 17.5 - 2.699, abs_tol=1e-6)
    assert math.isclose(rec["allwise__W2mag"], 17.5 - 3.339, abs_tol=1e-6)
    assert math.isclose(rec["allwise__snr2"], 50.0) and rec["allwise__W1mag_catalog"] == 12.0
    assert rec["wise_photometry_source"] == "LS_FORCED_UNWISE"
    # no AllWISE row: nothing is added
    only_ls = {"desi_legacy_surveys_dr10__flux_w1": 100.0, "desi_legacy_surveys_dr10__flux_ivar_w1": 1.0}
    m.ls_forced_wise(only_ls)
    assert "allwise__W1mag" not in only_ls
