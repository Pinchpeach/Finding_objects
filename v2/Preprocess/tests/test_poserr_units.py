"""Units of the catalogue position-error columns (2.62.0): VLASS e_RAJ2000 is degrees, NVSS e_RAJ2000 is seconds of time.

The stored rows say so (benchmark/position_errors/UNITS.md): VLASS e_RAJ2000 equals its e_RAMdeg column and is 4.7e-5 at the median
(0.17'' as degrees, 5e-5'' as arcsec: no radio component has that); NVSS e_RA x 15 cos(dec) / e_Dec has a median of 0.99 over 47 rows
(0.067 read as arcsec).  ``V2_POSERR_UNITS=legacy`` is the 2.61.9 reading.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import association_model as am  # noqa: E402

ARC = 1.0 / 3600.0


def _units(monkeypatch, mode):
    monkeypatch.setattr(am, "POSERR_UNITS", mode)
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())


def test_vlass_is_degrees_in_fixed_and_arcsec_in_legacy(monkeypatch):
    row = {"e_RAJ2000": 2.245e-05, "e_DEJ2000": 2.353e-05, "dec": 2.0}
    _units(monkeypatch, "fixed")
    assert am.infer_poserr_arcsec("VLASS", row) == pytest.approx(2.353e-05 * 3600.0)  # 0.085''
    _units(monkeypatch, "legacy")
    assert am.infer_poserr_arcsec("VLASS", row) == pytest.approx(2.353e-05)  # the old reading: 2e-5'' (the pair floor of 0.02'' held it up)


def test_nvss_ra_error_is_seconds_of_time_and_dec_is_arcsec(monkeypatch):
    row = {"e_RAJ2000": 0.09, "e_DEJ2000": 1.1, "dec": 2.0}
    _units(monkeypatch, "fixed")
    assert am.native_radec_errors_arcsec("NVSS", row) == pytest.approx((0.09 * 15.0 * 0.99939, 1.1), rel=1e-3)
    assert am.infer_poserr_arcsec("NVSS", row) == pytest.approx(0.09 * 15.0 * 0.99939, rel=1e-3)  # RA error wins at the equator: 1.35''
    # the same source at Dec 60: 15 cos(dec) halves the RA error, Dec wins
    assert am.infer_poserr_arcsec("NVSS", {**row, "dec": 60.0}) == pytest.approx(1.1)
    _units(monkeypatch, "legacy")
    assert am.infer_poserr_arcsec("NVSS", row) == pytest.approx(1.1)  # max(0.09, 1.1)


@pytest.mark.parametrize("catalog", ["TGSS ADR1", "LoTSS DR2", "SomeNewCatalogue"])
def test_arcsec_catalogues_and_unknown_ones_are_not_converted(monkeypatch, catalog):
    row = {"e_RAJ2000": 2.05, "e_DEJ2000": 1.6, "dec": 30.0}
    _units(monkeypatch, "fixed")
    assert am.infer_poserr_arcsec(catalog, row) == 2.05  # TGSS ADR1: "1-sigma uncertainty in the right ascension in arcseconds"
    _units(monkeypatch, "legacy")
    assert am.infer_poserr_arcsec(catalog, row) == 2.05


def test_nothing_else_changes_between_fixed_and_legacy(monkeypatch):
    """Every other column that reaches infer_poserr_arcsec is untouched, row by row."""
    rows = [
        ("Gaia DR3", {"ra_error": 0.3, "dec_error": 0.2}),  # mas
        ("AllWISE", {"eeMaj": 0.34, "eeMin": 0.31, "e_RA_pm": 0.41, "e_DE_pm": 0.45}),  # not read: the 0.5'' profile
        ("AllWISE", {"sigra": 0.3, "sigdec": 0.2}),  # IPAC: arcsec
        ("2MASS PSC", {"errMaj": 0.08, "errMin": 0.08}),
        ("Pan-STARRS1 DR2 MeanObject", {"raMeanErr": 0.04, "decMeanErr": 0.05}),
        ("DESI Legacy Surveys DR10", {"ra_ivar": 5.5e9, "dec_ivar": 5.4e9, "type": "PSF", "dec": 2.0}),
        ("eROSITA eRASS1", {"posErr": 4.9, "e_RA_ICRS": 4.0}),
        ("XMM 4XMM-DR13", {"ePos": 0.84}),
        ("Chandra CSC 2.0", {"r0": 0.93, "r1": 0.86}),
        ("FIRST", {"Rms": 0.15, "Maj": 5.4}),
        ("GALEX AIS", {"Nerr": 1.5, "Nperr": 0.6}),
        ("SDSS DR18 PhotoObj", {"type": 6, "psfMag_r": 18.0}),
        ("SIMBAD", {"coo_err_maj": 150.0}),
    ]
    for catalog, row in rows:
        _units(monkeypatch, "fixed")
        a = am.infer_poserr_arcsec(catalog, row)
        _units(monkeypatch, "legacy")
        assert am.infer_poserr_arcsec(catalog, row) == a, catalog


def test_the_profiles_switch_still_wins_for_vlass(monkeypatch):
    _units(monkeypatch, "fixed")
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset({"profiles"}))
    assert am.infer_poserr_arcsec("VLASS", {"e_RAJ2000": 2e-5, "e_DEJ2000": 2e-5, "dec": 30.0}) == 0.5  # Gordon et al. 2021, Sect. 2.1


def test_an_unknown_value_is_an_error_not_a_variant_that_did_nothing():
    env = {**os.environ, "V2_POSERR_UNITS": "arcsec"}
    r = subprocess.run([sys.executable, "-c", "import association_model"], cwd=V2 / "Preprocess", env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "V2_POSERR_UNITS" in r.stderr


def _s1():
    spec = importlib.util.spec_from_file_location("s1_poserr", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stage1(tmp_path, monkeypatch, mode, sep=0.15):
    """A PS1 row (error 0.01'', held at 0.02'' by the pair floor) and a VLASS row ``sep`` arcsec away (e_RA 2.4e-5 deg = 0.086'')."""
    monkeypatch.setattr(am, "POSERR_UNITS", mode)
    s1 = _s1()
    raw = tmp_path / mode / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([dict(catalog="Pan-STARRS1 DR2 MeanObject", catalog_object_id="p0", ra=150.0, dec=2.0, raMeanErr=0.01, decMeanErr=0.01, query_radius_arcmin=1.0)]).to_csv(raw / "panstarrs1_x.csv", index=False)
    pd.DataFrame([dict(catalog="VLASS", catalog_object_id="v0", ra=150.0 + sep * ARC, dec=2.0, e_RAJ2000=2.4e-5, e_DEJ2000=2.4e-5, query_radius_arcmin=1.0)]).to_csv(raw / "vlass_x.csv", index=False)
    out = tmp_path / f"{mode}.csv"
    s1.run(raw, out)
    t = pd.read_csv(out)
    return t[t.catalog == "VLASS"].iloc[0], t[t.catalog.str.startswith("Pan-STARRS1")].iloc[0]


def test_stage1_legacy_makes_the_radio_row_the_anchor_and_the_fix_gives_it_back_to_the_optical_row(tmp_path, monkeypatch):
    """The association order is by position error.  A VLASS row with ~0 error comes first and every optical row joins it; with 0.086''
    it comes after PS1.  Same object either way here, but the anchor (and so the object position) is the radio position in the legacy reading."""
    v, p = _stage1(tmp_path, monkeypatch, "fixed")
    assert v.poserr_arcsec == pytest.approx(0.0864, rel=1e-3) and v.association_status == "matched" and p.association_status == "new"
    assert v.object_id == p.object_id and v.object_anchor_catalog == "Pan-STARRS1 DR2 MeanObject"
    v0, p0 = _stage1(tmp_path, monkeypatch, "legacy")
    assert v0.poserr_arcsec == pytest.approx(2.4e-5) and v0.association_status == "new" and p0.association_status == "matched"
    assert v0.object_id == p0.object_id and v0.object_anchor_catalog == "VLASS"


def test_stage1_the_join_radius_moves_by_the_error_it_adds_not_by_orders_of_magnitude(tmp_path, monkeypatch):
    """At 1.0'' the PS1 pair floor (PSF / 6) dominates the combined sigma: fixed 0.218'' vs legacy 0.2'': the row joins at 1.0'' only with the fixed error."""
    v, p = _stage1(tmp_path, monkeypatch, "fixed", sep=1.0)
    assert v.object_id == p.object_id
    v0, p0 = _stage1(tmp_path, monkeypatch, "legacy", sep=1.0)
    assert v0.object_id != p0.object_id


def test_the_default_reading_is_legacy_until_the_documented_units_are_read():
    """2.62.2: the merge keeps the 2.61.9 reading as the default (the units VizieR documents could not be read yet); ``fixed`` is the switch."""
    env = {k: v for k, v in os.environ.items() if k != "V2_POSERR_UNITS"}
    code = "import association_model as am; print(am.POSERR_UNITS)"
    r = subprocess.run([sys.executable, "-c", code], cwd=str(Path(am.__file__).parent), env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "legacy"
