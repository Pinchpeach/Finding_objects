"""High-confidence flag (v2/high_confidence.py, 2.36.0)."""

import importlib.util
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("v2_high_confidence_t", V2 / "high_confidence.py")
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)

TABLE = {
    "magnitude_columns": ["std_mag__ls_r"],
    "edges": [None, 20.0, None],
    "labels": ["bright", "faint"],
    "thresholds": {"bright": {"STAR": 0.5, "GALAXY": 0.9, "QSO": None}, "faint": {"STAR": None, "GALAXY": 0.5, "QSO": None}},
    "purity_lower_bound": {"bright": {"STAR": 0.999}},
}


def _df(**cols):
    base = {"primary_class": "STAR", "classification_status": "CLASSIFIED", "primary_confidence": 0.95, "std_mag__ls_r": 18.0}
    base.update(cols)
    return pd.DataFrame([base])


def test_photometric_threshold_by_class_and_magnitude():
    assert hc.apply(_df(), table=TABLE).high_confidence.iloc[0]
    assert not hc.apply(_df(std_mag__ls_r=21.0), table=TABLE).high_confidence.iloc[0]  # faint STAR: none
    assert not hc.apply(_df(primary_class="GALAXY", primary_confidence=0.8), table=TABLE).high_confidence.iloc[0]
    assert not hc.apply(_df(primary_class="QSO", primary_confidence=0.9999), table=TABLE).high_confidence.iloc[0]
    assert not hc.apply(_df(std_mag__ls_r=float("nan")), table=TABLE).high_confidence.iloc[0]  # no magnitude
    assert not hc.apply(_df(classification_status="LOW_CONFIDENCE"), table=TABLE).high_confidence.iloc[0]


def test_spectrum_confirms_even_a_quasar():
    d = _df(
        primary_class="QSO",
        primary_confidence=0.6,
        std_mag__ls_r=21.5,
        desi_dr1_spectroscopy__OType="QSO",
        catalog_confidence_desi_spectroscopy=1.0,
        association_confidence__desi_dr1_spectroscopy=0.95,
    )
    r = hc.apply(d, table=TABLE)
    assert r.high_confidence.iloc[0] and r.high_confidence_basis.iloc[0] == "spectrum (DESI DR1)"
    # a low-quality spectrum, a disagreeing one or a doubtful association does not
    assert not hc.apply(d.assign(catalog_confidence_desi_spectroscopy=0.5), table=TABLE).high_confidence.iloc[0]
    assert not hc.apply(d.assign(desi_dr1_spectroscopy__OType="GALAXY"), table=TABLE).high_confidence.iloc[0]
    assert not hc.apply(d.assign(association_confidence__desi_dr1_spectroscopy=0.5), table=TABLE).high_confidence.iloc[0]


def test_failed_key_archive_withholds_photometric_route_only():
    cov = {"known": True, "failed": [{"collector": "gaia_dr3", "key": True}], "key_failed": True}
    assert not hc.apply(_df(), cov, table=TABLE).high_confidence.iloc[0]
    d = _df(sdss_dr18_spectroscopy__class="STAR", catalog_confidence_sdss_spectroscopy=1.0)
    assert hc.apply(d, cov, table=TABLE).high_confidence.iloc[0]


def test_committed_table_loads():
    t = hc.load_table()
    assert t and t["target_purity"] >= 0.98 and all(v.get("QSO") is None for v in t["thresholds"].values())
