"""``V2_OBJECT_POSITION`` (task "버"): the printed position of an object is the most precise member's, and NOTHING else changes.

The rule (object_position.py): the member with the smallest effective error ``max(poserr, 0.02'', PSF / 6)`` (the error of the association, without the proper-motion term), ties by the
astrometric priority of the catalogue; one member's position at that member's epoch, no mixing.  The switch is applied once, at the end of ``pipeline.py``: a run with ``best`` equals the
default run in every column but ``ra`` / ``dec`` and the six new columns.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
_spec = importlib.util.spec_from_file_location("v2_object_position_t", V2 / "object_position.py")
OP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(OP)
import association_model as AM  # noqa: E402


def det(cat, ra, dec, poserr, psf, oid="OBJ1", did=None, epoch=None):
    return dict(object_id=oid, catalog=cat, ra=ra, dec=dec, poserr_arcsec=poserr, psf_fwhm_arcsec=psf, ref_epoch=epoch, detection_id=did or f"{cat}:{ra}")


def frame(*rows):
    return pd.DataFrame(list(rows))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv(OP.ENV, raising=False)


def test_the_switch_values(monkeypatch):
    assert OP.mode() == "anchor"
    for v, want in (("", "anchor"), ("anchor", "anchor"), ("BEST", "best"), (" best ", "best")):
        monkeypatch.setenv(OP.ENV, v)
        assert OP.mode() == want
    monkeypatch.setenv(OP.ENV, "ivw")
    with pytest.raises(ValueError):
        OP.mode()


def test_effective_sigma_is_the_one_of_the_association():
    rows = [det("Gaia DR3", 1, 1, 0.0003, 0.18), det("AllWISE", 1, 1, 0.2, 6.1), det("DESI Legacy Surveys DR10", 1, 1, 0.05, 1.2), det("VLASS", 1, 1, 2e-5, 2.5), det("X", 1, 1, 0.3, None)]
    s = OP.effective_sigma(frame(*rows))
    for r, v in zip(rows, s):
        assert v == pytest.approx(AM.effective_sigma_arcsec({"catalog": r["catalog"], "poserr_arcsec": r["poserr_arcsec"], "psf_fwhm_arcsec": r["psf_fwhm_arcsec"]}))


def test_the_most_precise_member_wins_and_allwise_does_not():
    a = frame(det("AllWISE", 10.0003, 5.0, 0.2, 6.1, did="w"), det("DESI Legacy Surveys DR10", 10.0, 5.0, 0.05, 1.2, did="ls"), det("2MASS PSC", 10.0001, 5.0, 0.08, 2.5, did="2m"))
    b = OP.best_positions(a).loc["OBJ1"]
    assert b.source == "DESI Legacy Surveys DR10" and b.sigma == pytest.approx(0.2) and b.ra == 10.0
    g = frame(det("Gaia DR3", 10.0, 5.0, 0.0003, 0.18, epoch=2016.0), *a.to_dict("records"))
    b = OP.best_positions(g).loc["OBJ1"]
    assert b.source == "Gaia DR3" and b.sigma == pytest.approx(0.03) and b.epoch == 2016.0


def test_a_radio_row_with_a_legacy_unit_error_does_not_win():
    """VLASS stored its error in degrees, read as arcsec it is 2e-5'' (the default legacy units, benchmark/position_errors/UNITS.md): the PSF / 6 floor keeps it behind an optical row."""
    a = frame(det("VLASS Epoch 1 QL", 3.0, 3.0, 2e-5, 2.5, did="v"), det("DESI Legacy Surveys DR10", 3.0002, 3.0, 0.05, 1.2, did="ls"))
    assert OP.best_positions(a).loc["OBJ1"].source == "DESI Legacy Surveys DR10"


def test_ties_are_broken_by_the_catalogue_priority_not_the_row_order():
    rows = [det("Pan-STARRS1 DR2 MeanObject", 1.0, 1.0, 0.05, 1.2, did="p"), det("DESI Legacy Surveys DR10", 1.0001, 1.0, 0.05, 1.2, did="l")]
    for order in (rows, rows[::-1]):
        assert OP.best_positions(frame(*order)).loc["OBJ1"].source == "DESI Legacy Surveys DR10"  # both 0.2'': Legacy Surveys ranks first


def test_the_result_does_not_depend_on_the_row_order():
    rng = np.random.default_rng(0)
    rows = [det(c, 20 + 1e-4 * i, 4.0, s, p, did=f"d{i}") for i, (c, s, p) in enumerate([("AllWISE", 0.2, 6.1), ("2MASS PSC", 0.08, 2.5), ("GALEX AIS", 0.5, 5.3), ("SDSS DR18 PhotoObj", 0.1, 1.4), ("Pan-STARRS1 DR2 MeanObject", 0.05, 1.2)])]
    base = OP.best_positions(frame(*rows))
    for _ in range(5):
        idx = rng.permutation(len(rows))
        pd.testing.assert_frame_equal(OP.best_positions(frame(*[rows[i] for i in idx])), base)


def test_the_default_mode_returns_the_table_untouched():
    out = pd.DataFrame({"object_id": ["OBJ1"], "ra": [10.0003], "dec": [5.0], "primary_class": ["STAR"]})
    assert OP.apply(out, frame(det("DESI Legacy Surveys DR10", 10.0, 5.0, 0.05, 1.2))) is out


def test_best_mode_changes_only_ra_dec_and_adds_six_columns(monkeypatch):
    monkeypatch.setenv(OP.ENV, "best")
    assoc = frame(det("AllWISE", 10.0003, 5.0, 0.2, 6.1, did="w"), det("DESI Legacy Surveys DR10", 10.0, 5.0, 0.05, 1.2, did="ls"), det("2MASS PSC", 77.0, 8.0, 0.08, 2.5, oid="OBJ2", did="2m"))
    out = pd.DataFrame({"object_id": ["OBJ1", "OBJ2", "OBJ9"], "ra": [10.0003, 77.0, 1.0], "dec": [5.0, 8.0, 2.0], "primary_class": ["GALAXY", "STAR", "UNKNOWN"]})
    new = OP.apply(out, assoc)
    assert list(new.columns[:4]) == list(out.columns) and list(new.columns[4:]) == OP.NEW_COLUMNS
    assert (new.primary_class == out.primary_class).all() and list(new.object_id) == ["OBJ1", "OBJ2", "OBJ9"]
    assert new.ra.tolist() == [10.0, 77.0, 1.0]  # OBJ9 is not in the association: unchanged
    assert new.ra_anchor.tolist() == [10.0003, 77.0, 1.0]
    assert new.position_source.tolist()[:2] == ["DESI Legacy Surveys DR10", "2MASS PSC"] and pd.isna(new.position_source.iloc[2])
    assert new.position_shift_arcsec.iloc[0] == pytest.approx(0.0003 * np.cos(np.radians(5.0)) * 3600.0, rel=1e-6) and new.position_shift_arcsec.iloc[1] == 0.0
    assert np.isnan(new.position_shift_arcsec.iloc[2])


def test_an_empty_search_gets_the_columns_too(monkeypatch):
    monkeypatch.setenv(OP.ENV, "best")
    out = OP.apply(pd.DataFrame(columns=["object_id", "ra", "dec"]), pd.DataFrame())
    assert list(out.columns) == ["object_id", "ra", "dec"] + OP.NEW_COLUMNS and len(out) == 0


def test_the_pipeline_with_the_switch_equals_the_default_run_in_every_other_column(tmp_path, monkeypatch):
    """The committed NGC 4522 raw data, 12' (89 objects): labels, probabilities, names, distances and the object set are those of the default run."""
    spec = importlib.util.spec_from_file_location("v2_pipeline_pos", V2 / "pipeline.py")
    pipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipe)
    raw = V2 / "rawdata"
    kw = dict(ra=188.4155, dec=9.1751, radius=12.0)
    a = pipe.run(tmp_path / "a", raw, **kw)
    monkeypatch.setenv(OP.ENV, "best")
    b = pipe.run(tmp_path / "b", raw, **kw)
    assert list(b.columns[: len(a.columns)]) == list(a.columns) and list(b.columns[len(a.columns):]) == OP.NEW_COLUMNS
    for c in a.columns:
        if c in ("ra", "dec"):
            continue
        assert ((a[c].isna() & b[c].isna()) | (a[c] == b[c])).all(), f"column {c} changed"
    assert (b.position_shift_arcsec.fillna(0) < 5.0).all() and (b.position_shift_arcsec > 0).any()
    s = pd.read_csv(tmp_path / "b" / "objects_summary.csv")
    assert "position_source" in s and "position_source" not in pd.read_csv(tmp_path / "a" / "objects_summary.csv")
