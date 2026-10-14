"""Local archive cache / mirror (2.9.1)."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import archive_cache as ac  # noqa: E402


def _frame():
    return pd.DataFrame(
        {
            "catalog": "X",
            "catalog_object_id": ["18446744073709551615", "2"],
            "object_name": ["a", "b"],
            "ra": [10.0, 10.0],
            "dec": [0.0, 0.05],
            "v": [1.5, None],
        }
    )


def test_containment_filter_and_text_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "c"))
    src = tmp_path / "coll.py"
    src.write_text("x = 1\n")
    ac.put("coll", src, 10.0, 0.0, 5.0, _frame())
    same = ac.get("coll", src, 10.0, 0.0, 5.0)
    assert same is not None and same.catalog_object_id.tolist() == ["18446744073709551615", "2"]
    sub = ac.get("coll", src, 10.0, 0.0, 1.0)  # inside: only the central row (0.05 deg = 3')
    assert sub.catalog_object_id.tolist() == ["18446744073709551615"]
    assert ac.get("coll", src, 10.0, 0.1, 1.0) is None  # not contained
    src.write_text("x = 2\n")  # collector changed: old rows never reused
    assert ac.get("coll", src, 10.0, 0.0, 1.0) is None
    monkeypatch.setenv("V2_CACHE", "0")
    src.write_text("x = 1\n")
    assert ac.get("coll", src, 10.0, 0.0, 1.0) is None


def test_empty_results_expire_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "c"))
    src = tmp_path / "coll.py"
    src.write_text("x = 1\n")
    ac.put("coll", src, 1.0, 1.0, 1.0, pd.DataFrame(columns=["catalog", "ra", "dec"]))
    assert ac.get("coll", src, 1.0, 1.0, 1.0) is not None
    monkeypatch.setattr(ac.time, "time", lambda: 1e12)  # far future
    assert ac.get("coll", src, 1.0, 1.0, 1.0) is None


def test_controller_second_run_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "c"))
    spec = importlib.util.spec_from_file_location("v2_controller_cache_t", GET / "controller.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    calls = []

    class Fake:
        CATALOG = "NVSS"

        @staticmethod
        def fetch(ra, dec, r):
            calls.append(r)
            return _frame()

        @staticmethod
        def save(df, path):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, index=False)

    monkeypatch.setattr(ctl, "_load_collector", lambda name: Fake)
    a = ctl._collect_one("nvss", 10.0, 0.0, 5.0, tmp_path / "out", "t1")
    b = ctl._collect_one("nvss", 10.0, 0.0, 1.0, tmp_path / "out", "t2")
    assert (a["cache"], b["cache"], len(calls)) == ("miss", "hit", 1)
    assert b["rows"] == 1
    out = pd.read_csv(tmp_path / "out" / "nvss_t2.csv", dtype=str)
    assert out.catalog_object_id.tolist() == ["18446744073709551615"]


def test_review_fixes(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "c"))
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    src = pkg / "coll.py"
    src.write_text("x = 1\n")
    helper = pkg / "_helper.py"
    helper.write_text("y = 1\n")
    df = _frame().assign(dec=[20.5, 20.55], query_radius_arcmin="5.0")
    ac.put("coll", src, 10.0, 20.5, 5.0, df)
    # identical cone at dec != 0 (acos rounding used to miss)
    assert ac.get("coll", src, 10.0, 20.5, 5.0) is not None
    # smaller cone: rows filtered and the recorded radius is the requested one
    sub = ac.get("coll", src, 10.0, 20.5, 1.0)
    assert len(sub) == 1 and float(sub.query_radius_arcmin[0]) == 1.0
    # a collector margin keeps rows beyond the bare radius (SGA-2020)
    assert len(ac.get("coll", src, 10.0, 20.5, 1.0, margin_arcmin=3.0)) == 2
    # a shared helper module changed: old rows never reused
    helper.write_text("y = 2\n")
    assert ac.get("coll", src, 10.0, 20.5, 5.0) is None
    # partial results are not stored
    ac.put("coll", src, 50.0, 0.0, 1.0, _frame().assign(gaia_ap_query_status="error:TimeoutError"))
    assert ac.get("coll", src, 50.0, 0.0, 1.0) is None
    ac.put("coll", src, 50.0, 0.0, 1.0, _frame().assign(gaia_ap_query_status="ok"))
    assert ac.get("coll", src, 50.0, 0.0, 1.0) is not None
