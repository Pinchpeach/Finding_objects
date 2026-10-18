"""Unconfirmed Pan-STARRS1-only detections (detection_quality.py, 2.30.0)."""

import importlib.util
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def _dq():
    s = importlib.util.spec_from_file_location("dq", V2 / "detection_quality.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _row(ra, dec, catalogs, **kw):
    base = {
        "ra": ra,
        "dec": dec,
        "catalogs": catalogs,
        "primary_class": "UNKNOWN",
        "classification_status": "NO_EVIDENCE",
    }
    return {**base, **kw}


def test_ps1_pair_without_legacy_counterpart_is_unconfirmed():
    dq = _dq()
    ls = [_row(20.0 + i * 0.002, 0.001 * i, "DESI Legacy Surveys DR10", primary_class="GALAXY") for i in range(5)]
    ps1 = dict(pan_starrs1_dr2_meanobject__nDetections=2, std_mag__ps1_g=21.6, std_mag__ps1_r=None, std_mag__ps1_i=None)
    rows = ls + [
        _row(20.001, 0.003, "Pan-STARRS1 DR2 MeanObject", **ps1),  # no LS object within 2": unconfirmed
        _row(20.0, 0.0002, "Pan-STARRS1 DR2 MeanObject", **ps1),  # LS object 0.7" away: kept
        _row(30.0, 0.0, "Pan-STARRS1 DR2 MeanObject", **ps1),  # outside LS coverage: kept
        _row(20.001, 0.003, "Pan-STARRS1 DR2 MeanObject", **{**ps1, "pan_starrs1_dr2_meanobject__nDetections": 5}),
        _row(
            20.001, 0.003, "Pan-STARRS1 DR2 MeanObject|SIMBAD", **ps1
        ),  # literature entry does not confirm a detection
    ]
    out = dq.apply(pd.DataFrame(rows))
    assert out.classification_status.tolist()[5:] == [
        "UNCONFIRMED",
        "NO_EVIDENCE",
        "NO_EVIDENCE",
        "NO_EVIDENCE",
        "UNCONFIRMED",
    ]
    assert "Legacy Surveys" in out.unknown_reason.iloc[5]
