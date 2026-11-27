"""The ambiguity switches of Stage 1 (2.61.7): all off by default, each resolves only the case it is built for."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Preprocess"))
import association_model as am  # noqa: E402

ARC = 1.0 / 3600.0


def _s1():
    spec = importlib.util.spec_from_file_location("s1_ambiguity", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(raw: Path, name: str, catalog: str, xs, **extra):
    """Rows of one catalogue on a line of constant Dec: ``xs`` are the offsets in arcsec along RA (Dec = 2 deg: cos = 1 - 6e-4)."""
    rows = [dict(catalog=catalog, catalog_object_id=f"{name}{i}", ra=150.0 + x * ARC, dec=2.0, query_radius_arcmin=1.0, **extra)
            for i, x in enumerate(xs)]  # fmt: skip
    pd.DataFrame(rows).to_csv(raw / f"{name}_x.csv", index=False)


def _run(tmp_path, s1, monkeypatch, fix=(), ls=(0.0, 0.2), other="SDSS DR18 PhotoObj", other_x=(0.08,), other_file="sdss_dr18", ls_catalog="DESI Legacy Surveys DR10"):
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset(fix))
    monkeypatch.setattr(s1, "AMBIG_FIX", frozenset(fix))
    monkeypatch.setattr(s1, "TARGET_SPECTRA", s1.DESI_SPECTRA + (s1.SPECTRA_EXTRA if "spectra" in fix else ()))
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    _write(raw, "ls" if ls_catalog.startswith("DESI") else "ps1", ls_catalog, ls)
    _write(raw, other_file, other, other_x)
    out = tmp_path / f"assoc_{'_'.join(sorted(fix)) or 'off'}.csv"
    s1.run(raw, out)
    t = pd.read_csv(out)
    return t[t.catalog == other].iloc[0], t


def test_parse_ambig():
    assert am.parse_ambig("") == frozenset()
    assert am.parse_ambig(None) == frozenset()
    assert am.parse_ambig("all") == {"profiles", "spectra", "same", "nearest"}
    assert am.parse_ambig("same, best") == {"same", "best"}
    with pytest.raises(ValueError):
        am.parse_ambig("sam")  # a typo is an error, not a variant that did nothing


def test_default_is_unchanged_and_writes_no_new_column(tmp_path, monkeypatch):
    r, t = _run(tmp_path, _s1(), monkeypatch)
    assert r.association_status == "ambiguous_new"  # two Legacy Surveys fragments 0.2'' apart, the SDSS row between them
    assert "ambiguity_resolution" not in t.columns


def test_same_object_joins_when_the_two_candidates_are_fragments_of_one_object(tmp_path, monkeypatch):
    r, t = _run(tmp_path, _s1(), monkeypatch, fix=("same",))
    assert r.association_status == "matched" and r.ambiguity_resolution == "same_object"
    # the candidates 0.6'' apart are two objects: the row stays ambiguous
    r2, _ = _run(tmp_path / "far", _s1(), monkeypatch, fix=("same",), ls=(0.0, 0.6))
    assert r2.association_status == "ambiguous_new"


def test_nearest_joins_only_when_clearly_nearest(tmp_path, monkeypatch):
    s1 = _s1()
    r, _ = _run(tmp_path, s1, monkeypatch, fix=("nearest",), ls=(0.0, 0.6), other_x=(0.08,))  # 0.08'' against 0.52''
    assert r.association_status == "matched" and r.ambiguity_resolution == "nearest_clear"
    r2, _ = _run(tmp_path / "mid", s1, monkeypatch, fix=("nearest",), ls=(0.0, 0.6), other_x=(0.3,))  # 0.3'' against 0.3'': not clear
    assert r2.association_status == "ambiguous_new"
    r3, _ = _run(tmp_path / "wide", s1, monkeypatch, fix=("nearest",), ls=(0.0, 0.2), other_x=(0.08,))  # 0.08'' against 0.12'': ratio 1.5
    assert r3.association_status == "ambiguous_new"


def test_best_never_leaves_an_ambiguity(tmp_path, monkeypatch):
    r, _ = _run(tmp_path, _s1(), monkeypatch, fix=("best",), ls=(0.0, 0.6), other_x=(0.3,))
    assert r.association_status == "matched" and r.ambiguity_resolution == "best"


def test_lamost_is_a_target_only_with_spectra(tmp_path, monkeypatch):
    s1 = _s1()
    kw = dict(ls=(0.0, 0.6), ls_catalog="Pan-STARRS1 DR2 MeanObject", other="LAMOST DR catalog", other_file="lamost_spectroscopy", other_x=(0.1,))
    r, _ = _run(tmp_path, s1, monkeypatch, **kw)
    assert r.association_status == "ambiguous_new"  # LAMOST's default 0.6'' makes the 0.1'' and 0.5'' PS1 rows equal
    r2, _ = _run(tmp_path / "on", s1, monkeypatch, fix=("spectra",), **kw)
    assert r2.association_status == "matched" and r2.association_method == "spectroscopic_target"
    assert (r2.object_anchor_catalog == "Pan-STARRS1 DR2 MeanObject") and abs(r2.match_separation_arcsec - 0.1) < 0.02


def test_profiles_change_only_the_listed_catalogues(monkeypatch):
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())
    assert am.infer_poserr_arcsec("SDSS DR18 PhotoObj", {"type": 6}) == 0.6
    assert am.profile_for("VLASS") is am.DEFAULT_PROFILE
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset({"profiles"}))
    assert am.infer_poserr_arcsec("SDSS DR18 PhotoObj", {"type": 6}) == 0.1  # point source: Pier et al. 2003
    assert am.infer_poserr_arcsec("SDSS DR18 PhotoObj", {"type": 3}) == am.LS_RESOLVED_FLOOR_ARCSEC  # galaxy keeps the resolved floor
    assert am.infer_poserr_arcsec("VLASS", {"dec": 30.0}) == 0.5 and am.infer_poserr_arcsec("VLASS", {"dec": -35.0}) == 1.0
    assert abs(am.infer_poserr_arcsec("LoTSS DR2", {"e_RAJ2000": 0.3, "e_DEJ2000": 0.1}) - (0.3**2 + 0.2**2) ** 0.5) < 1e-12
    assert am.infer_poserr_arcsec("LAMOST DR catalog", {}) == 0.6  # no literature value found: unchanged
    assert am.infer_poserr_arcsec("Gaia DR3", {"ra_error": 0.5, "dec_error": 0.4}) == 0.0005  # profiled catalogues unchanged
