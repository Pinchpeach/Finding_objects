"""Radio-only objects (radio_sources.py, 2.31.0)."""

import importlib.util
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def _rs():
    s = importlib.util.spec_from_file_location("rs", V2 / "radio_sources.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _row(oid, ra, dec, catalogs, cls="UNKNOWN", **kw):
    return {
        "object_id": oid,
        "designation": oid,
        "ra": ra,
        "dec": dec,
        "catalogs": catalogs,
        "primary_class": cls,
        "classification_status": "NO_EVIDENCE" if cls == "UNKNOWN" else "CLASSIFIED",
        **kw,
    }


def test_radio_only_cases():
    rs = _rs()
    d = 1 / 3600
    rows = [
        _row("lobeA", 100.0, 10.0, "VLASS", vlass__Ftot=20.0, vlass__QualFlag=0, vlass__DupFlag=0, vlass__SCode="S"),
        _row(
            "lobeB",
            100.0 + 30 * d,
            10.0,
            "VLASS",
            vlass__Ftot=12.0,
            vlass__QualFlag=0,
            vlass__DupFlag=0,
            vlass__SCode="S",
        ),
        _row("host", 100.0 + 15 * d, 10.0 + 1 * d, "DESI Legacy Surveys DR10|VLASS", cls="GALAXY", vlass__Ftot=2.0),
        _row("dup", 101.0, 10.0, "VLASS", vlass__Ftot=5.0, vlass__QualFlag=0, vlass__DupFlag=2),
        _row("side", 102.0, 10.0, "FIRST", **{"first__Fint": 3.0, "first__p(S)": 0.4}),
        _row("lonely", 103.0, 10.0, "NVSS", **{"nvss__S1.4": 4.0}),
        _row("bright", 104.0, 10.0, "VLASS", vlass__Ftot=500.0, vlass__QualFlag=0, vlass__DupFlag=0),
        _row("faintB", 104.0 + 20 * d, 10.0, "VLASS", vlass__Ftot=2.0, vlass__QualFlag=0, vlass__DupFlag=0),
    ]
    out = rs.apply(pd.DataFrame(rows)).set_index("object_id")
    assert out.loc["lobeA", "classification_status"] == "RADIO_COMPONENT"
    assert "host candidate host" in out.loc["lobeA", "unknown_reason"]
    assert out.loc["dup", "classification_status"] == "UNCONFIRMED"
    assert out.loc["side", "classification_status"] == "UNCONFIRMED"
    assert out.loc["lonely", "classification_status"] == "NO_EVIDENCE"
    assert "high redshift" in out.loc["lonely", "unknown_reason"]
    assert out.loc["bright", "classification_status"] == "NO_EVIDENCE"  # flux ratio 250 > 10: not a lobe pair
    assert out.loc["host", "classification_status"] == "CLASSIFIED"
