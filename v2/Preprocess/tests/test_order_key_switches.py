"""The order key of Stage 1 and AllWISE eeMaj (2.62.7, task "너"): ``V2_POSERR_NATIVE=allwise_order|allwise_sigma`` and ``V2_ASSOC_ORDER_KEY=floored``.

``V2_POSERR_NATIVE=allwise`` (2.62.4) puts eeMaj in ``poserr_arcsec``, which the match radius reads (through ``effective_sigma_arcsec``, whose PSF/6 floor holds almost every AllWISE row
at 1.02'') and which the ORDER of the groups reads without a floor (``_anchor_key``).  The measured gain (+5.2 % correct joins) is then the order.  The three new switches pull the two apart
(benchmark/association_truth/PREDICTIONS_ORDER_KEY_2026-11-28.md); all are off by default and change nothing unless given.
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


def _set(monkeypatch, native=(), order=()):
    monkeypatch.setattr(am, "POSERR_NATIVE", frozenset(native))
    monkeypatch.setattr(am, "ORDER_KEY", frozenset(order))
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())


def test_defaults_are_off_and_the_order_key_is_the_position_error(monkeypatch):
    assert am.ORDER_KEY == frozenset() and am.POSERR_NATIVE == frozenset()
    assert am.order_poserr_arcsec("AllWISE", {"eeMaj": 0.34}, 0.5, 6.1) is None
    assert am.order_poserr_arcsec("2MASS PSC", {}, 0.25, 2.5) is None


def test_allwise_order_ranks_by_eemaj_and_keeps_sigma(monkeypatch):
    _set(monkeypatch, native=["allwise_order"])
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.9}) == 0.5  # sigma as in the base run
    assert am.order_poserr_arcsec("AllWISE", {"eeMaj": 0.9}, 0.5, 6.1) == pytest.approx(0.9)
    assert am.order_poserr_arcsec("AllWISE", {"eeMaj": float("nan")}, 0.5, 6.1) is None  # no eeMaj: the base value
    assert am.order_poserr_arcsec("GALEX AIS", {"Nerr": 1.5}, 0.8, 5.3) is None


def test_allwise_sigma_reads_eemaj_for_sigma_and_ranks_by_the_base_value(monkeypatch):
    _set(monkeypatch, native=["allwise_sigma"])
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.9}) == pytest.approx(0.9)
    assert am.order_poserr_arcsec("AllWISE", {"eeMaj": 0.9}, 0.9, 6.1) == 0.5
    assert am.infer_poserr_arcsec("AllWISE", {"eeMaj": 0.9}, native=False) == 0.5
    assert am.order_poserr_arcsec("SIMBAD", {}, 0.6, None) is None


def test_floored_ranks_every_row_by_the_sigma_the_match_uses(monkeypatch):
    _set(monkeypatch, order=["floored"])
    assert am.order_poserr_arcsec("AllWISE", {}, 0.5, 6.1) == pytest.approx(6.1 / 6)  # the floor of the match radius, not the 0.5'' assumption
    assert am.order_poserr_arcsec("2MASS PSC", {}, 0.25, 2.5) == pytest.approx(2.5 / 6)  # 0.42'' against the stated 0.25''
    assert am.order_poserr_arcsec("Pan-STARRS1 DR2 MeanObject", {}, 0.04, None) == pytest.approx(0.04)  # no PSF: the 0.02'' pair floor only
    assert am.order_poserr_arcsec("Pan-STARRS1 DR2 MeanObject", {}, 0.01, None) == pytest.approx(0.02)
    _set(monkeypatch, native=["allwise_order"], order=["floored"])  # eeMaj through the floor: the information in eeMaj is lost below 1.02''
    assert am.order_poserr_arcsec("AllWISE", {"eeMaj": 0.34}, 0.5, 6.1) == pytest.approx(6.1 / 6)
    assert am.order_poserr_arcsec("AllWISE", {"eeMaj": 1.4}, 0.5, 6.1) == pytest.approx(1.4)


@pytest.mark.parametrize("name,value", [("V2_ASSOC_ORDER_KEY", "typo"), ("V2_POSERR_NATIVE", "allwise_typo")])
def test_an_unknown_option_is_an_error(name, value):
    r = subprocess.run([sys.executable, "-c", "import association_model"], cwd=V2 / "Preprocess", env={**os.environ, name: value}, capture_output=True, text=True)
    assert r.returncode != 0 and name in r.stderr


def _s1():
    spec = importlib.util.spec_from_file_location("s1_order", V2 / "Preprocess" / "01_source_association.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _field(tmp_path, tag, eemaj):
    """A PS1 row with a 0.55'' error (the order key 0.55) and an AllWISE row 0.4'' away: the base AllWISE error 0.5'' ranks it before PS1, an eeMaj of 0.9'' after it."""
    raw = tmp_path / tag / "raw"
    raw.mkdir(parents=True)
    pd.DataFrame([dict(catalog="Pan-STARRS1 DR2 MeanObject", catalog_object_id="p0", ra=150.0, dec=2.0, raMeanErr=0.55, decMeanErr=0.55, query_radius_arcmin=1.0)]).to_csv(raw / "panstarrs1_x.csv", index=False)
    pd.DataFrame([dict(catalog="AllWISE", catalog_object_id="w0", ra=150.0 + 0.4 / 3600.0, dec=2.0, eeMaj=eemaj, query_radius_arcmin=1.0)]).to_csv(raw / "allwise_x.csv", index=False)
    return raw


def _anchor(tmp_path, monkeypatch, tag, native=(), order=(), eemaj=0.9):
    _set(monkeypatch, native=native, order=order)
    s1 = _s1()
    monkeypatch.setattr(s1, "order_poserr_arcsec", am.order_poserr_arcsec)
    out = tmp_path / f"{tag}.csv"
    s1.run(_field(tmp_path, tag, eemaj), out)
    d = pd.read_csv(out)
    assert d.object_id.nunique() == 1  # both rows are one object in every variant: only who anchors it differs
    return d.object_anchor_catalog.iloc[0]


def test_the_order_decides_who_anchors_the_object(tmp_path, monkeypatch):
    assert _anchor(tmp_path, monkeypatch, "base") == "AllWISE"  # 0.5'' < 0.55''
    assert _anchor(tmp_path, monkeypatch, "order", native=["allwise_order"]) == "Pan-STARRS1 DR2 MeanObject"  # eeMaj 0.9'' > 0.55''
    assert _anchor(tmp_path, monkeypatch, "sigma", native=["allwise_sigma"]) == "AllWISE"  # the order is the base one
    assert _anchor(tmp_path, monkeypatch, "both", native=["allwise"]) == "Pan-STARRS1 DR2 MeanObject"  # eeMaj is the order key too
    assert _anchor(tmp_path, monkeypatch, "floored", order=["floored"]) == "Pan-STARRS1 DR2 MeanObject"  # 6.1''/6 = 1.02'' > 0.55''
    assert _anchor(tmp_path, monkeypatch, "small", native=["allwise_order"], eemaj=0.2) == "AllWISE"  # a precise AllWISE row still anchors
