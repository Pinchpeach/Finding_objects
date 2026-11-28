"""V2_ANNOT_ASSOC and V2_POSERR_NATIVE (2.62.6): both switches are off by default and change nothing unless given.

What they do (benchmark/association_ambiguity/PREDICTIONS_LITERATURE_2026-11-28.md, WORK_REPORT_2026-11-28b.md):
  * ``V2_POSERR_NATIVE=allwise|allwise_raw|galex``  AllWISE ``eeMaj`` / GALEX ``Nerr`` (``Ferr``) as the position error; ``allwise_raw`` also drops the
    PSF/6 floor for AllWISE rows.  VizieR II/328 and II/335 ReadMe.
  * ``V2_ANNOT_ASSOC=density``     a NED / SIMBAD row is judged against the survey objects' density only (not the literature catalogue's own)
  * ``V2_ANNOT_ASSOC=typed_close`` two typed rows of one annotation catalogue within 0.6'' are one object
  * ``V2_ANNOT_ASSOC=err``         SIMBAD ``coo_err_maj`` (mas) is the position error
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


def _native(monkeypatch, *words):
    monkeypatch.setattr(am, "POSERR_NATIVE", frozenset(words))
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())


def test_defaults_are_off_and_the_stored_columns_are_not_read(monkeypatch):
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())
    assert am.POSERR_NATIVE == frozenset() and am.ANNOT_ASSOC == frozenset()
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.34, "eeMin": 0.31}) == 0.5  # the profile constant
    assert am.infer_poserr_arcsec("GALEX AIS", {"Nerr": 1.5, "Ferr": 1.4}) == 0.8
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 150.0}) == 0.6


def test_allwise_reads_eemaj_in_arcsec_and_keeps_the_profile_when_it_is_missing(monkeypatch):
    _native(monkeypatch, "allwise")
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.34}) == pytest.approx(0.34)
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": float("nan")}) == 0.5
    assert am.infer_poserr_arcsec("AllWISE", {}) == 0.5
    assert am.infer_poserr_arcsec("GALEX AIS", {"Nerr": 1.5}) == 0.8  # not asked for
    _native(monkeypatch, "allwise_raw")
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.34}) == pytest.approx(0.34)


def test_galex_reads_the_nuv_error_then_the_fuv_error(monkeypatch):
    _native(monkeypatch, "galex")
    assert am.infer_poserr_arcsec("GALEX AIS", {"Nerr": 1.5, "Ferr": 1.4}) == pytest.approx(1.5)
    assert am.infer_poserr_arcsec("GALEX AIS", {"Nerr": float("nan"), "Ferr": 1.4}) == pytest.approx(1.4)
    assert am.infer_poserr_arcsec("GALEX AIS", {"Nperr": 0.6}) == 0.8  # the Poisson part alone is not the position error
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.34}) == 0.5


def test_the_psf_floor_hides_eemaj_unless_allwise_raw(monkeypatch):
    """6.1''/6 = 1.017'' is above almost every eeMaj (COSMOS 2': median 0.41, q90 0.58), so ``allwise`` alone changes nothing in the sigma used."""
    det = {"catalog": "AllWISE", "poserr_arcsec": 0.34, "psf_fwhm_arcsec": 6.1}
    _native(monkeypatch)
    assert am.effective_sigma_arcsec(det) == pytest.approx(6.1 / 6.0)
    _native(monkeypatch, "allwise")
    assert am.effective_sigma_arcsec(det) == pytest.approx(6.1 / 6.0)
    _native(monkeypatch, "allwise_raw")
    assert am.effective_sigma_arcsec(det) == pytest.approx(0.34)
    assert am.effective_sigma_arcsec({**det, "poserr_arcsec": 1.5}) == pytest.approx(1.5)  # a large error is still read
    other = {"catalog": "GALEX AIS", "poserr_arcsec": 0.5, "psf_fwhm_arcsec": 5.3}
    assert am.effective_sigma_arcsec(other) == pytest.approx(5.3 / 6.0)  # allwise_raw is AllWISE only


def test_simbad_err_is_milliarcseconds_and_only_for_simbad(monkeypatch):
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())
    monkeypatch.setattr(am, "ANNOT_ASSOC", frozenset({"err"}))
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 150.0}) == pytest.approx(0.15)  # 150 mas
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": float("nan")}) == 0.6
    assert am.infer_poserr_arcsec("NED", {"coo_err_maj": 150.0}) == 0.6


@pytest.mark.parametrize("name", ["V2_POSERR_NATIVE", "V2_ANNOT_ASSOC"])
def test_an_unknown_option_is_an_error_not_a_variant_that_did_nothing(name):
    env = {**os.environ, name: "typo"}
    r = subprocess.run([sys.executable, "-c", "import association_model"], cwd=V2 / "Preprocess", env=env, capture_output=True, text=True)
    assert r.returncode != 0 and name in r.stderr


def _s1():
    spec = importlib.util.spec_from_file_location("s1_annot", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _field(tmp_path, tag, simbad):
    """One PS1 row at (150, 2) with five PS1 fillers far away (density 5e-4 / arcsec^2) and the given SIMBAD rows (otype, offset in arcsec along RA) plus
    nine SIMBAD fillers far away.  The SIMBAD cone is recorded as 0.1' so that its own density is 10 / (pi 6^2) = 0.088 / arcsec^2, 170 times the PS1 one."""
    raw = tmp_path / tag / "raw"
    raw.mkdir(parents=True)
    ps1 = [dict(catalog="Pan-STARRS1 DR2 MeanObject", catalog_object_id="p0", ra=150.0, dec=2.0, raMeanErr=0.04, decMeanErr=0.04, query_radius_arcmin=1.0)]
    ps1 += [dict(catalog="Pan-STARRS1 DR2 MeanObject", catalog_object_id=f"pf{k}", ra=150.0 + 0.02 * (k + 1), dec=2.0, raMeanErr=0.04, decMeanErr=0.04, query_radius_arcmin=1.0) for k in range(5)]
    pd.DataFrame(ps1).to_csv(raw / "panstarrs1_x.csv", index=False)
    sim = [dict(catalog="SIMBAD", catalog_object_id=f"s{k}", ra=150.0 + off * ARC, dec=2.0, otype=ot, query_radius_arcmin=0.1) for k, (ot, off) in enumerate(simbad)]
    sim += [dict(catalog="SIMBAD", catalog_object_id=f"sf{k}", ra=150.0, dec=2.0 + 0.0167 * (k + 1), otype="G", query_radius_arcmin=0.1) for k in range(9)]
    pd.DataFrame(sim).to_csv(raw / "simbad_x.csv", index=False)
    return raw


def _stage1(tmp_path, monkeypatch, tag, simbad, annot=()):
    s1 = _s1()
    monkeypatch.setattr(s1, "ANNOT_ASSOC", frozenset(annot))
    raw = _field(tmp_path, tag, simbad)
    out = tmp_path / f"{tag}.csv"
    s1.run(raw, out)
    return pd.read_csv(out).set_index("catalog_object_id")


def test_the_literature_density_blocks_a_join_the_survey_density_allows(tmp_path, monkeypatch):
    """A SIMBAD row 1.8'' from the PS1 row: p_chance 0.59 with SIMBAD's own density, 0.005 with the survey objects'."""
    base = _stage1(tmp_path, monkeypatch, "d0", [("G", 1.8)])
    assert base.loc["s0", "object_id"] != base.loc["p0", "object_id"]  # the old rule: a literature-only object
    dens = _stage1(tmp_path, monkeypatch, "d1", [("G", 1.8)], annot=("density",))
    assert dens.loc["s0", "object_id"] == dens.loc["p0", "object_id"]
    far = _stage1(tmp_path, monkeypatch, "d2", [("G", 4.5)], annot=("density",))
    assert far.loc["s0", "object_id"] != far.loc["p0", "object_id"]  # beyond the match radius (3.2'') whatever the density


def test_typed_close_merges_two_typed_rows_of_one_catalogue_only_when_they_agree_within_0_6_arcsec(tmp_path, monkeypatch):
    rows = [("G", 0.1), ("QSO", -0.4)]
    base = _stage1(tmp_path, monkeypatch, "t0", rows)
    assert len({base.loc[i, "object_id"] for i in ("p0", "s0", "s1")}) == 2  # the second typed row stays a separate object
    close = _stage1(tmp_path, monkeypatch, "t1", rows, annot=("typed_close",))
    assert len({close.loc[i, "object_id"] for i in ("p0", "s0", "s1")}) == 1
    apart = _stage1(tmp_path, monkeypatch, "t2", [("G", 0.1), ("QSO", -1.5)], annot=("typed_close",))
    assert len({apart.loc[i, "object_id"] for i in ("p0", "s0", "s1")}) == 2  # 1.5'' > 0.6'': a supernova and its host stay two objects


def test_the_annotation_switches_do_nothing_where_there_is_no_ned_or_simbad_row(tmp_path, monkeypatch):
    """The blind runs (no literature rows) are unchanged by construction; checked row by row."""
    s1 = _s1()
    raw = tmp_path / "blind" / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([dict(catalog="Pan-STARRS1 DR2 MeanObject", catalog_object_id=f"p{k}", ra=150.0 + 0.0003 * k, dec=2.0, raMeanErr=0.04, decMeanErr=0.04, query_radius_arcmin=1.0) for k in range(8)]).to_csv(raw / "panstarrs1_x.csv", index=False)
    pd.DataFrame([dict(catalog="AllWISE", catalog_object_id=f"w{k}", ra=150.0 + 0.0003 * k + 1.5 * ARC, dec=2.0, eeMaj=0.3, query_radius_arcmin=1.0) for k in range(6)]).to_csv(raw / "allwise_x.csv", index=False)
    monkeypatch.setattr(s1, "ANNOT_ASSOC", frozenset())
    s1.run(raw, tmp_path / "off.csv")
    monkeypatch.setattr(s1, "ANNOT_ASSOC", frozenset({"density", "typed_close", "err"}))
    s1.run(raw, tmp_path / "on.csv")
    pd.testing.assert_frame_equal(pd.read_csv(tmp_path / "off.csv"), pd.read_csv(tmp_path / "on.csv"))
