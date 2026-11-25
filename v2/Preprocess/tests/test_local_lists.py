"""Small fixed catalogue tables kept on the user's own computer (2.60.5, ``Get_data/local_lists.py``)."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table
from astroquery.utils import TableList

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import agb_suh2021 as agb  # noqa: E402
import bzcat  # noqa: E402
import local_lists as L  # noqa: E402


def _spec(verified=False):
    return L.ListSpec(
        "toy",
        "toy list",
        ("T/1", "T/2"),
        {"T/1": 3, "T/2": 2},
        terms_verified=verified,
    )


def _tables():
    t1 = Table(
        {
            "recno": np.array([1, 2, 3], dtype="int32"),
            "RAJ2000": MaskedColumn([10.0, 10.001, 50.0], unit="deg"),
            "DEJ2000": MaskedColumn([20.0, 20.0, -30.0], unit="deg"),
            "Name": MaskedColumn(["a", "b", "c"], mask=[False, True, False]),
        }
    )
    t2 = Table(
        {
            "recno": np.array([1, 2], dtype="int32"),
            "RAJ2000": MaskedColumn([10.0005, 120.0], unit="deg"),
            "DEJ2000": MaskedColumn([20.0005, 5.0], unit="deg"),
            "Name": MaskedColumn(["d", "e"]),
        }
    )
    return {"T/1": t1, "T/2": t2}


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("V2_CACHE", raising=False)
    monkeypatch.delenv("V2_LOCAL_LISTS", raising=False)
    monkeypatch.delenv("V2_LOCAL_LISTS_REFRESH", raising=False)
    L._MEMO.clear()
    L._FAILED.clear()
    yield
    L._MEMO.clear()
    L._FAILED.clear()


# ----------------------------------------------------------------------------------------------- cone search
def test_cone_has_vizier_shape_rows_in_table_order_and_r_first():
    spec = _spec()
    out = L.cone_from(spec, _tables(), 10.0, 20.0, 1.0)
    assert isinstance(out, TableList) and list(out.keys()) == ["T/1", "T/2"]
    t1 = out["T/1"]
    assert t1.colnames[0] == "_r" and list(t1["recno"]) == [1, 2]  # row 3 is far away
    assert abs(float(t1["_r"][0])) < 1e-9 and float(t1["_r"][1]) == 0.0564  # 0.001 deg of RA at dec 20 = 0.0564 arcmin
    assert float(t1["_r"][1]) == round(float(t1["_r"][1]), 4)  # printed to 4 decimals like VizieR
    assert t1["Name"].mask.tolist() == [False, True]  # masks survive
    assert str(t1["recno"].dtype) == "int32" and t1["RAJ2000"].unit == "deg"
    assert list(out["T/2"]["recno"]) == [1]


def test_a_table_without_rows_is_left_out_and_an_empty_answer_is_falsy():
    spec = _spec()
    out = L.cone_from(spec, _tables(), 120.0, 5.0, 0.5)  # only T/2 row 2
    assert list(out.keys()) == ["T/2"]
    empty = L.cone_from(spec, _tables(), 200.0, 60.0, 5.0)
    assert not empty and len(empty) == 0  # as VizieR's empty TableList: `if tables` is False


def test_radius_edge_is_inclusive_and_masked_positions_never_match():
    spec = _spec()
    tabs = _tables()
    tabs["T/1"]["RAJ2000"].mask = [False, True, False]
    out = L.cone_from(spec, tabs, 10.0, 20.0, 5.0)
    assert list(out["T/1"]["recno"]) == [1]  # row 2 has no position
    sep = float(L._separation_arcmin(10.0, 20.0, 10.0005, 20.0005))
    assert 0.0 < sep < 0.1
    assert list(L.cone_from(spec, _tables(), 10.0, 20.0, sep)["T/2"]["recno"]) == [1]  # exactly on the edge: kept


# ----------------------------------------------------------------------------------------------- modes
def test_modes_and_the_gate_on_unverified_terms(monkeypatch):
    s_unverified, s_verified = _spec(False), _spec(True)
    assert L.mode() == "auto" and not L.usable(s_unverified) and L.usable(s_verified)
    monkeypatch.setenv("V2_LOCAL_LISTS", "all")
    assert L.usable(s_unverified)
    monkeypatch.setenv("V2_LOCAL_LISTS", "0")
    assert not L.usable(s_verified) and L.mode() == "0"
    monkeypatch.setenv("V2_LOCAL_LISTS", "all")
    monkeypatch.setenv("V2_CACHE", "0")  # "no on-disk state" wins over everything
    assert L.mode() == "0" and not L.usable(s_unverified)


def test_the_real_lists_are_gated_until_their_terms_are_verified():
    assert set(L.SPECS) == {"suh2021_agb", "roma_bzcat5"}
    assert L.SPECS["suh2021_agb"].rows == {
        "J/ApJS/256/43/table9": 5908,
        "J/ApJS/256/43/table10": 3596,
        "J/ApJS/256/43/table11": 5301,
        "J/ApJS/256/43/table12": 3576,
    }
    assert L.SPECS["roma_bzcat5"].rows == {"VII/274/bzcat5": 3561}
    assert L.cone("suh2021_agb", 0, 0, 1) is None and L.cone("roma_bzcat5", 0, 0, 1) is None  # default: remote


# ----------------------------------------------------------------------------------------------- the store
class _FakeQuery:
    def __init__(self, tables, fail=False):
        self.tables, self.fail, self.calls = tables, fail, []

    def __call__(self, ids, ra, dec, radius_arcmin, columns=("**",)):
        self.calls.append((list(ids), ra, dec, radius_arcmin))
        if self.fail:
            raise RuntimeError("VizieR is down")
        out = []
        for t in ids:
            tb = self.tables[t].copy()
            tb.add_column(MaskedColumn(np.zeros(len(tb)), name="_r"), index=0)
            out.append((t, tb))
        return TableList(out)


def _patch_query(monkeypatch, fake):
    import _catalog_utils

    monkeypatch.setattr(_catalog_utils, "vizier_query", fake)


def test_first_use_downloads_once_stores_a_manifest_and_later_cones_need_no_request(monkeypatch, capsys):
    spec = _spec(True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    fake = _FakeQuery(_tables())
    _patch_query(monkeypatch, fake)
    a = L.cone("toy", 10.0, 20.0, 1.0)
    assert list(a["T/1"]["recno"]) == [1, 2] and len(fake.calls) == 1
    assert fake.calls[0] == (["T/1", "T/2"], 0.0, 0.0, 10800.0)  # the whole sky, every table, one request
    man = json.loads((L.store_dir("toy") / "manifest.json").read_text())
    assert man["tables"]["T/1"]["rows"] == 3 and len(man["tables"]["T/1"]["sha256"]) == 64
    assert man["source"].startswith("VizieR") and man["downloaded"] and man["terms_verified"] is True
    assert "[lists] first use: downloading toy list" in capsys.readouterr().out  # never a silent wait
    L._MEMO.clear()  # a new process: read from the disk copy
    b = L.cone("toy", 120.0, 5.0, 0.5)
    assert list(b["T/2"]["recno"]) == [2] and len(fake.calls) == 1  # no second request
    assert "_r" not in L._load(spec, man)["T/1"].colnames


def test_a_failed_download_falls_back_to_vizier_and_is_not_retried_at_once(monkeypatch):
    spec = _spec(True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    fake = _FakeQuery(_tables(), fail=True)
    _patch_query(monkeypatch, fake)
    assert L.cone("toy", 10.0, 20.0, 1.0) is None  # the collector asks VizieR for this cone
    assert L.cone("toy", 10.0, 20.0, 1.0) is None
    assert len(fake.calls) == 1  # not retried within RETRY_AFTER_S
    assert not (L.store_dir("toy") / "manifest.json").exists()
    L._FAILED.clear()
    fake.fail = False
    assert L.cone("toy", 10.0, 20.0, 1.0) is not None  # a later try works


def test_a_wrong_row_count_is_never_stored(monkeypatch):
    spec = _spec(True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    tabs = _tables()
    tabs["T/1"] = tabs["T/1"][:2]  # truncated answer
    _patch_query(monkeypatch, _FakeQuery(tabs))
    assert L.cone("toy", 10.0, 20.0, 1.0) is None
    assert not (L.store_dir("toy") / "manifest.json").exists()


def test_a_corrupted_file_is_downloaded_again(monkeypatch):
    spec = _spec(True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    fake = _FakeQuery(_tables())
    _patch_query(monkeypatch, fake)
    assert L.cone("toy", 10.0, 20.0, 1.0) is not None and len(fake.calls) == 1
    (L.store_dir("toy") / L._fname("T/1")).write_bytes(b"damaged")
    L._MEMO.clear()
    out = L.cone("toy", 10.0, 20.0, 1.0)  # the hash does not match the manifest: rebuilt, never trusted
    assert out is not None and list(out["T/1"]["recno"]) == [1, 2] and len(fake.calls) == 2


def test_an_old_copy_is_asked_for_again_and_the_user_can_force_it(monkeypatch):
    spec = L.ListSpec("toy", "toy list", ("T/1", "T/2"), {"T/1": 3, "T/2": 2}, max_age_days=0.5, terms_verified=True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    fake = _FakeQuery(_tables())
    _patch_query(monkeypatch, fake)
    L.cone("toy", 10.0, 20.0, 1.0)
    man_path = L.store_dir("toy") / "manifest.json"
    man = json.loads(man_path.read_text())
    man["downloaded"] = "2020-01-01T00:00:00+00:00"
    man_path.write_text(json.dumps(man))
    L._MEMO.clear()
    assert L.status(spec)["stale"] is True
    L.cone("toy", 10.0, 20.0, 1.0)
    assert len(fake.calls) == 2  # asked again
    monkeypatch.setenv("V2_LOCAL_LISTS_REFRESH", "1")
    L._MEMO.clear()
    L.cone("toy", 10.0, 20.0, 1.0)
    assert len(fake.calls) == 3


def test_v2_cache_0_means_no_local_copy_and_no_download(monkeypatch):
    spec = _spec(True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    fake = _FakeQuery(_tables())
    _patch_query(monkeypatch, fake)
    monkeypatch.setenv("V2_CACHE", "0")
    assert L.cone("toy", 10.0, 20.0, 1.0) is None and fake.calls == []
    assert not L.store_dir("toy").exists()


# ----------------------------------------------------------------------------------------------- collectors
def test_collectors_use_the_local_answer_when_there_is_one_and_vizier_otherwise(monkeypatch):
    t = Table(
        {
            "recno": np.array([7], dtype="int32"),
            "RAJ2000": MaskedColumn([266.0], unit="deg"),
            "DEJ2000": MaskedColumn([-29.0], unit="deg"),
            "IRAS": MaskedColumn(["17440-2900"]),
            "OI-N": MaskedColumn([7.0]),
        }
    )
    spec = L.SPECS["suh2021_agb"]
    tables = {tid: t[:0].copy() for tid in spec.tables}
    tables["J/ApJS/256/43/table9"] = t
    monkeypatch.setattr(agb.local_lists, "cone", lambda key, ra, dec, r: L.cone_from(spec, tables, ra, dec, r))
    called = []
    monkeypatch.setattr(agb, "vizier_query", lambda *a, **k: called.append(a))
    got, failed = agb._per_table(266.0, -29.0, 2.0)
    assert failed == [] and called == []  # no request
    assert len(got["J/ApJS/256/43/table9"]) == 1 and got["J/ApJS/256/43/table10"] is None
    # no local copy: VizieR is asked as before
    monkeypatch.setattr(agb.local_lists, "cone", lambda *a: None)
    monkeypatch.setattr(agb, "vizier_query", lambda ids, *a, **k: called.append(ids) or TableList([]))
    got, failed = agb._per_table(266.0, -29.0, 2.0)
    assert called and called[0] == list(agb.TABLES) and all(v is None for v in got.values())


def test_bzcat_collector_reads_the_local_copy(monkeypatch):
    spec = L.SPECS["roma_bzcat5"]
    t = Table(
        {
            "recno": np.array([1], dtype="int32"),
            "Name": MaskedColumn(["5BZB J1058+0133"]),
            "RAJ2000": MaskedColumn([164.62], unit="deg"),
            "DEJ2000": MaskedColumn([1.566], unit="deg"),
        }
    )
    monkeypatch.setattr(
        bzcat.local_lists, "cone", lambda key, ra, dec, r: L.cone_from(spec, {spec.tables[0]: t}, ra, dec, r)
    )
    monkeypatch.setattr(bzcat, "vizier_cone", lambda *a, **k: (_ for _ in ()).throw(AssertionError("VizieR asked")))
    df = bzcat.fetch(164.62, 1.566, 2.0)
    assert list(df["blazar_type"]) == ["BL_LAC"] and list(df["catalog_object_id"]) == ["5BZB J1058+0133"]
    monkeypatch.setattr(
        bzcat.local_lists, "cone", lambda key, ra, dec, r: L.cone_from(spec, {spec.tables[0]: t}, 10.0, 10.0, 1.0)
    )
    assert bzcat.fetch(10.0, 10.0, 1.0).empty  # an empty local cone is an empty answer, no request


def test_the_download_is_visible_in_the_app_status_and_is_not_a_collector():
    sys.path.insert(0, str(GET.parent / "app"))
    import progress

    tr = progress.ProgressTracker(True, 30)
    msg = tr.feed("[lists] first use: downloading Roma-BZCAT 5th edition, VII/274/bzcat5 (3,561 rows) from VizieR once")
    assert msg and msg.startswith("first use: downloading Roma-BZCAT") and tr.fraction == 0.0 and not tr.done_collectors
    assert tr.feed("[agb_suh2021] ok: 3 rows (4.1 s)") == "agb_suh2021: ok"


def test_sexagesimal_positions_are_parsed_at_full_precision():
    """Roma-BZCAT holds its J2000 position as text ("12 24 54.46", "+21 22 46.4"): VizieR measures ``_r`` from that."""
    spec = L.ListSpec("hms", "hms list", ("H/1",), {"H/1": 2})
    tb = Table(
        {
            "recno": np.array([1, 2], dtype="int32"),
            "RAJ2000": MaskedColumn(["12 24 54.46", "00 00 20.39"], mask=[False, False]),
            "DEJ2000": MaskedColumn(["+21 22 46.4", "-32 21 01.00"], mask=[False, False]),
        }
    )
    ra, dec = L.positions(spec, tb)
    assert (
        abs(ra[0] - (12 + 24 / 60 + 54.46 / 3600) * 15) < 1e-12 and abs(dec[0] - (21 + 22 / 60 + 46.4 / 3600)) < 1e-12
    )
    assert abs(dec[1] + (32 + 21 / 60 + 1.0 / 3600)) < 1e-12
    out = L.cone_from(spec, {"H/1": tb}, ra[0], dec[0], 0.5)
    assert list(out["H/1"]["recno"]) == [1] and float(out["H/1"]["_r"][0]) == 0.0
    tb["RAJ2000"].mask = [False, True]  # a masked position never matches
    L._POS.clear()  # (the parsed positions are memoised per stored table, which is never changed in use)
    assert list(L.cone_from(spec, {"H/1": tb}, ra[1], dec[1], 5.0).keys()) == []


def test_a_failing_local_lookup_falls_back_to_vizier_instead_of_failing_the_collector(monkeypatch, capsys):
    spec = _spec(True)
    monkeypatch.setitem(L.SPECS, "toy", spec)
    _patch_query(monkeypatch, _FakeQuery(_tables()))
    assert L.cone("toy", 10.0, 20.0, 1.0) is not None
    monkeypatch.setattr(
        L, "cone_from", lambda *a, **k: (_ for _ in ()).throw(ValueError("could not convert string to float"))
    )
    assert L.cone("toy", 10.0, 20.0, 1.0) is None  # the collector asks VizieR
    assert "the local copy could not answer (ValueError" in capsys.readouterr().out
    assert L.cone("toy", 10.0, 20.0, 1.0) is None  # and is not offered the broken copy again for RETRY_AFTER_S
