"""Missing-archive warning (v2/catalog_coverage.py, 2.36.0)."""

import importlib.util
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("v2_catalog_coverage_t", V2 / "catalog_coverage.py")
cov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cov)


def test_failed_key_archive_is_reported(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(
        [
            {"collector": "gaia_dr3", "status": "timeout", "rows": 0, "error": "exceeded 300 s"},
            {"collector": "nvss", "status": "error", "rows": 0, "error": "HTTP 502"},
            {"collector": "allwise", "status": "ok", "rows": 10, "error": ""},
            {"collector": "first", "status": "empty", "rows": 0, "error": ""},
        ]
    ).to_csv(raw / "collection_summary_x.csv", index=False)
    c = cov.write(tmp_path, raw)
    assert c["known"] and c["key_failed"]
    assert [f["collector"] for f in c["failed"]] == ["gaia_dr3", "nvss"]
    msg = cov.message(cov.read(tmp_path))
    assert "Gaia DR3" in msg and "NVSS" in msg and "less certain" in msg
    assert "AllWISE" not in msg and "FIRST" not in msg  # ok / empty are not failures


def test_no_summary_is_unknown_not_all_clear(tmp_path):
    c = cov.summarize(tmp_path)
    assert c == {"known": False, "failed": [], "key_failed": False}
    assert cov.message(c) == "" and cov.message(None) == ""


def test_every_collector_has_an_impact():
    spec = importlib.util.spec_from_file_location("v2_ctrl_t", V2 / "Get_data" / "controller.py")
    import sys

    sys.path.insert(0, str(V2 / "Get_data"))
    ctrl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctrl)
    assert set(ctrl.COLLECTORS) <= set(cov.IMPACT)
