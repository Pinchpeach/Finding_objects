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


def test_field_without_pan_starrs1():
    # A3667 field (Dec -57): no Pan-STARRS1 rows, so its columns are absent (2.32.0 crash).
    dq = _dq()
    out = pd.DataFrame([_row(303.1, -56.8, "DESI Legacy Surveys DR10", primary_class="GALAXY")])
    assert dq.apply(out).classification_status.tolist() == ["NO_EVIDENCE"]


def test_ls_z_only_detection_is_unconfirmed():
    """2.55.0: a Legacy Surveys source seen only in z (r measured, not
    detected) and in no other survey is UNKNOWN / UNCONFIRMED; seen by another
    survey, bright in z, or r detected, it keeps its class."""
    import importlib.util as iu
    from pathlib import Path

    spec = iu.spec_from_file_location("dq_zonly", Path(__file__).resolve().parents[2] / "detection_quality.py")
    DQ = iu.module_from_spec(spec)
    spec.loader.exec_module(DQ)
    P = DQ.LS_P
    out = pd.DataFrame(
        {
            "object_id": ["A", "B", "C", "D"],
            "catalogs": [DQ.LS, "AllWISE|" + DQ.LS, DQ.LS + "|NED", DQ.LS],
            "primary_class": ["STAR"] * 4,
            "classification_status": ["CLASSIFIED"] * 4,
            P + "flux_r": [-0.02, -0.02, -0.01, 0.5],
            P + "flux_ivar_r": [300.0] * 4,
            P + "flux_z": [0.8, 0.8, 0.5, 0.8],  # z = 22.7, 22.7, 23.3, 22.7
            "parent_object_id": [None] * 4,
        }
    )
    r = DQ.apply(out).set_index("object_id")
    assert r.loc["A", "primary_class"] == "UNKNOWN" and r.loc["A", "classification_status"] == "UNCONFIRMED"
    assert r.loc["C", "classification_status"] == "UNCONFIRMED"  # a literature entry is no detection
    assert r.loc["B", "primary_class"] == "STAR" and r.loc["D", "primary_class"] == "STAR"
