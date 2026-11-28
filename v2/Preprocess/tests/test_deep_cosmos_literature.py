"""NED / SIMBAD rows of the 26 deep COSMOS fields (2.62.7, task "더"): the collector and the offline merge.  No network: the services are replaced by small fakes.

The schema facts the collector relies on were read from the services' table lists on 2026-11-28 (``collect_deep_cosmos_literature.py`` docstring); ``probe`` re-reads them at run time.
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, V2 / "benchmark" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(V2 / "benchmark"))
    spec.loader.exec_module(mod)
    return mod


L = _load("collect_deep_cosmos_literature")
M = _load("merge_deep_cosmos_literature")


def test_the_field_list_is_the_26_fields_with_6_arcmin_cones():
    f = L.fields("all")
    assert len(f) == 26 and set(L.fields("first")) | set(L.fields("second")) == set(f)
    assert len(L.fields("first")) == 9 and len(L.fields("second")) == 17
    assert list(L.fields("all", only="deep_cosmos_3 deep_cosmos_10")) == ["deep_cosmos_3", "deep_cosmos_10"]
    with pytest.raises(SystemExit):
        L.fields("all", only="deep_cosmos_99")
    assert L.tag(150.1, 2.25) == "ra150p1_dec2p25_r6arcmin"


def test_the_default_simbad_collector_is_not_changed():
    """The two extra columns are asked in a request of their own: the collector's columns (and so every normal collection's file) stay what they were."""
    sm = L.load_module(V2 / "Get_data" / "simbad.py", "dcl_simbad_guard")
    assert "coo_qual" not in sm.MAIN_COLUMNS and "otypes" not in sm.MAIN_COLUMNS
    assert {"coo_err_maj", "coo_err_min", "coo_err_angle", "coo_wavelength", "coo_bibcode", "otype"} <= set(sm.MAIN_COLUMNS)


def _vosi(table, cols):
    body = "".join(f"<column><name>{n}</name><unit>{u}</unit><dataType>REAL</dataType></column>" for n, u in cols)
    return f"<tableset><schema><name>s</name><table><name>s.{table}</name>{body}</table></schema></tableset>"


class _Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def _good_pages():
    ned = _vosi("objdir", [("prefname", ""), ("ra", "deg"), ("dec", "deg"), ("uncmaja", "arcsec"), ("uncmina", "arcsec"), ("uncposa", "deg")])
    basic = "".join(f"<column><name>{n}</name><unit>{u}</unit></column>" for n, u in [("coo_err_maj", "mas"), ("coo_err_min", "mas"), ("coo_err_angle", "deg"), ("coo_qual", ""),
                                                                                        ("coo_wavelength", ""), ("coo_bibcode", ""), ("otype", "")])  # fmt: skip
    sim = f"<tableset><schema><name>public</name><table><name>public.basic</name>{basic}</table><table><name>public.alltypes</name><column><name>otypes</name></column></table></schema></tableset>"
    return {L.NED_TAP_TABLES: _Resp(ned), L.SIMBAD_TABLES[0]: _Resp("not found", 404), L.SIMBAD_TABLES[1]: _Resp(sim)}


def test_probe_passes_on_the_documented_schema_and_names_what_is_missing(tmp_path):
    pages = _good_pages()
    assert L.probe(tmp_path / "a", http_get=lambda u: pages[u])["ok"]  # the CDS host 404 does not matter while its mirror answers
    bad = dict(pages)
    bad[L.NED_TAP_TABLES] = _Resp(_vosi("objdir", [("prefname", ""), ("ra", "deg"), ("dec", "deg"), ("uncmaja", "arcsec")]))
    r = L.probe(tmp_path / "b", http_get=lambda u: bad[u])
    assert not r["ok"] and r["ned"]["missing"] == ["uncmina", "uncposa"]
    bad = dict(pages)
    bad[L.SIMBAD_TABLES[1]] = _Resp(pages[L.SIMBAD_TABLES[1]].text.replace("<name>coo_qual</name>", "<name>coo_quality</name>"))
    assert not L.probe(tmp_path / "c", http_get=lambda u: bad[u])["ok"]
    bad[L.SIMBAD_TABLES[1]] = _Resp(pages[L.SIMBAD_TABLES[1]].text.replace("<unit>mas</unit>", "<unit>arcsec</unit>"))  # a changed unit is a failure too: 1000x
    assert not L.probe(tmp_path / "d", http_get=lambda u: bad[u])["ok"]
    assert (tmp_path / "a" / "schema_probe.json").exists()


class _FakeSimbad:
    def __init__(self, rows, fail=0):
        self.rows, self.fail, self.calls = rows, fail, []

    def fetch(self, ra, dec, radius):
        return pd.DataFrame(self.rows)

    def _cone_numbers(self, ra, dec, radius):
        return ra, dec, radius / 60.0

    def _ordered_servers(self):
        return ["s1", "s2"]

    def tap(self, server, adql):
        from astropy.table import Table

        self.calls.append((server, adql))
        if self.fail and len(self.calls) <= self.fail:
            raise RuntimeError("HTTP 404")
        return Table({"main_id": ["* A", "* B", "* A"], "coo_qual": ["C", "", "C"], "otypes": ["G|IR", "QSO", "G|IR"]}), False


def _simbad_rows():
    return [dict(catalog="SIMBAD", catalog_object_id="* A", object_name="* A", ra=150.0, dec=2.0, coo_err_maj=12.5, otype="G"),
            dict(catalog="SIMBAD", catalog_object_id="* B", object_name="* B", ra=150.01, dec=2.0, coo_err_maj=np.nan, otype="QSO"),
            dict(catalog="SIMBAD", catalog_object_id="* C", object_name="* C", ra=150.02, dec=2.0, coo_err_maj=np.nan, otype="*")]  # fmt: skip


def test_simbad_extras_are_attached_by_main_id_and_a_failed_server_is_replaced_by_its_mirror():
    sm = _FakeSimbad(_simbad_rows(), fail=1)
    df = L.simbad_with_extras(sm, 150.0, 2.0, 6.0, tap=sm.tap)
    assert [c for c, _ in sm.calls] == ["s1", "s2"]  # the first server failed, the mirror answered
    assert df.attrs["extras"] == "ok"
    assert df.coo_qual.tolist()[0] == "C" and pd.isna(df.coo_qual.tolist()[1]) and pd.isna(df.coo_qual.tolist()[2])  # "" and a missing row are empty, not a grade
    assert df.otypes.tolist()[:2] == ["G|IR", "QSO"] and pd.isna(df.otypes.tolist()[2])
    assert df.coo_err_maj.tolist()[0] == 12.5  # the collector's columns are untouched
    both_fail = _FakeSimbad(_simbad_rows(), fail=9)
    d = L.simbad_with_extras(both_fail, 150.0, 2.0, 6.0, tap=both_fail.tap)
    assert d.attrs["extras"] == "failed" and d.coo_qual.isna().all() and len(d) == 3


def _ned_rows():
    return pd.DataFrame([dict(catalog="NED", catalog_object_id="GAL A", object_name="GAL A", ra=150.0, dec=2.0, Type="G"),
                         dict(catalog="NED", catalog_object_id="GAL B", object_name="GAL B", ra=150.01, dec=2.0, Type="QSO"),
                         dict(catalog="NED", catalog_object_id="GAL C", object_name="GAL C", ra=150.02, dec=2.0, Type="G")])  # fmt: skip


def test_ned_uncertainties_by_name_then_by_position_then_empty():
    tap_rows = pd.DataFrame([dict(prefname="gal  a", ra=150.0, dec=2.0, uncmaja=0.2, uncmina=0.1, uncposa=30.0),  # name differs in case and spaces
                             dict(prefname="OTHER NAME", ra=150.01 + 0.1 / 3600.0, dec=2.0, uncmaja=1.5, uncmina=1.0, uncposa=10.0),  # GAL B: no name, 0.1'' away
                             dict(prefname="FAR", ra=150.5, dec=2.0, uncmaja=9.0, uncmina=9.0, uncposa=0.0)])  # fmt: skip
    got, state = L.ned_uncertainties(_ned_rows(), 150.0, 2.0, 6.0, tap=lambda q: tap_rows)
    assert got.ned_unc_source.tolist() == ["name", "position", ""]
    assert got.ned_unc_maj_arcsec.tolist()[:2] == [0.2, 1.5] and pd.isna(got.ned_unc_maj_arcsec.iloc[2])
    assert state["method"] == "cone" and state["requests"] == 1 and state["with_uncertainty"] == 2 and state["matched_by_position"] == 1


def test_ned_names_are_asked_in_batches_when_the_cone_query_is_refused():
    calls = []

    def tap(q):
        calls.append(q)
        if "CIRCLE" in q:
            raise RuntimeError("the view has no position index")
        return pd.DataFrame([dict(prefname="GAL A", ra=150.0, dec=2.0, uncmaja=0.2, uncmina=0.1, uncposa=30.0)])

    many = pd.concat([_ned_rows()] * 120, ignore_index=True)  # 360 rows, 3 distinct names: one batch
    got, state = L.ned_uncertainties(many, 150.0, 2.0, 6.0, tap=tap)
    assert state["method"] == "names" and state["requests"] == 2 and sum("IN (" in c for c in calls) == 1
    names = [f"N{i}" for i in range(400)]
    many = pd.DataFrame([dict(catalog="NED", catalog_object_id=n, object_name=n, ra=150.0, dec=2.0) for n in names])
    calls.clear()
    _, state = L.ned_uncertainties(many, 150.0, 2.0, 6.0, tap=tap)
    assert state["requests"] == 1 + 3 and sum("IN (" in c for c in calls) == 3  # 400 names, batches of 150


def test_the_ned_query_is_the_documented_table_and_columns():
    q = L.ned_cone_adql(150.1, 2.25, 6.0)
    assert "FROM NEDTAP.objdir" in q and "uncmaja" in q and "uncposa" in q and "CIRCLE('ICRS', 150.100000000, 2.25000000, 0.100000000)" in q
    assert "O''BRIEN" in L.ned_names_adql(["O'BRIEN"])  # a quote in a name is escaped


def test_a_collected_field_is_written_once(tmp_path):
    sm = _FakeSimbad(_simbad_rows())

    class _Ned:
        n = 0

        def fetch(self, ra, dec, radius):
            _Ned.n += 1
            return _ned_rows()

    tap_rows = pd.DataFrame([dict(prefname="GAL A", ra=150.0, dec=2.0, uncmaja=0.2, uncmina=0.1, uncposa=30.0)])
    st = L.collect_field("deep_cosmos_x", 150.1, 2.25, tmp_path, sm=sm, nd=_Ned(), tap_simbad=sm.tap, tap_ned=lambda q: tap_rows)
    assert st["ok"] and st["simbad_rows"] == 3 and st["ned_rows"] == 3 and st["simbad_coo_qual_filled"] == 1
    assert (tmp_path / "deep_cosmos_x" / "simbad_ra150p1_dec2p25_r6arcmin.csv").exists() and (tmp_path / "deep_cosmos_x" / "ned_ra150p1_dec2p25_r6arcmin.csv").exists()
    again = L.collect_field("deep_cosmos_x", 150.1, 2.25, tmp_path, sm=sm, nd=_Ned(), tap_simbad=sm.tap, tap_ned=lambda q: tap_rows)
    assert again["ok"] and _Ned.n == 1  # a finished field is not asked again


# ---- the offline merge ---------------------------------------------------------------------------------------------------------------------------------------
def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _blind(tmp_path):
    raw = tmp_path / "blind" / "deep_cosmos_x" / "raw" / "ra150p1_dec2p25_r6arcmin"
    raw.mkdir(parents=True)
    (raw / "panstarrs1_ra150p1_dec2p25_r6arcmin.csv").write_text("catalog,ra,dec\nPan-STARRS1 DR2 MeanObject,150.0,2.0\n")
    (raw / "collection_summary_x.csv").write_text("collector,status\nps1,ok\n")
    lit = tmp_path / "lit" / "deep_cosmos_x"
    lit.mkdir(parents=True)
    (lit / "simbad_ra150p1_dec2p25_r6arcmin.csv").write_text("catalog,ra,dec\nSIMBAD,150.0,2.0\n")
    (lit / "ned_ra150p1_dec2p25_r6arcmin.csv").write_text("catalog,ra,dec\nNED,150.0,2.0\n")
    (lit / "literature_state.json").write_text(json.dumps({"ok": True, "tag": "ra150p1_dec2p25_r6arcmin"}))
    return tmp_path / "blind", tmp_path / "lit"


def test_the_merge_copies_next_to_the_blind_rows_and_never_writes_into_them(tmp_path):
    blind, lit = _blind(tmp_path)
    before = {p: _sha(p) for p in blind.rglob("*") if p.is_file()}
    out = tmp_path / "merged"
    man = M.merge(blind, lit, out)
    raw = out / "deep_cosmos_x" / "raw" / "ra150p1_dec2p25_r6arcmin"
    assert sorted(p.name for p in raw.iterdir()) == ["collection_summary_x.csv", "ned_ra150p1_dec2p25_r6arcmin.csv", "panstarrs1_ra150p1_dec2p25_r6arcmin.csv", "simbad_ra150p1_dec2p25_r6arcmin.csv"]
    assert {p: _sha(p) for p in blind.rglob("*") if p.is_file()} == before  # the blind bundles are untouched
    assert man["fields"]["deep_cosmos_x"]["added"] == ["ned_ra150p1_dec2p25_r6arcmin.csv", "simbad_ra150p1_dec2p25_r6arcmin.csv"]
    assert (out / "merge_manifest.json").exists()


def test_the_merge_refuses_to_overwrite_and_to_write_into_the_blind_data(tmp_path):
    blind, lit = _blind(tmp_path)
    with pytest.raises(SystemExit):
        M.merge(blind, lit, blind / "inside")  # inside the blind root
    out = tmp_path / "merged"
    M.merge(blind, lit, out)
    with pytest.raises(SystemExit):
        M.merge(blind, lit, out)  # an existing, non-empty directory
    blind2, lit2 = _blind(tmp_path / "second")
    (blind2 / "deep_cosmos_x" / "raw" / "ra150p1_dec2p25_r6arcmin" / "simbad_ra150p1_dec2p25_r6arcmin.csv").write_text("x\n")  # a blind bundle that already holds a SIMBAD file
    with pytest.raises(SystemExit):
        M.merge(blind2, lit2, tmp_path / "merged2")
    (lit2 / "deep_cosmos_x" / "literature_state.json").write_text(json.dumps({"ok": False}))
    with pytest.raises(SystemExit):
        M.merge(*_blind(tmp_path / "third")[:1], lit2, tmp_path / "merged3")  # a field whose collection did not finish


# ---- the switches that read the literature's own position errors -------------------------------------------------------------------------------------------------
sys.path.insert(0, str(V2 / "Preprocess"))
import association_model as am  # noqa: E402


def _annot(monkeypatch, *words):
    monkeypatch.setattr(am, "ANNOT_ASSOC", frozenset(words))
    monkeypatch.setattr(am, "AMBIG_FIX", frozenset())


def test_the_literature_error_switches_are_off_by_default(monkeypatch):
    _annot(monkeypatch)
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 150.0, "coo_qual": "D"}) == 0.6
    assert am.infer_poserr_arcsec("NED", {"ned_unc_maj_arcsec": 1.2}) == 0.6


def test_qual_floors_the_simbad_error_by_the_grade_and_uses_the_grade_when_the_error_is_missing(monkeypatch):
    _annot(monkeypatch, "qual")
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 40.0, "coo_qual": "C"}) == pytest.approx(0.1)  # 0.04'' read, grade C is at least 0.1''
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 400.0, "coo_qual": "C"}) == pytest.approx(0.4)  # inside the band: the error itself
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": float("nan"), "coo_qual": "D"}) == pytest.approx(3.0)  # no error: the middle of the band
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": float("nan"), "coo_qual": "E"}) == pytest.approx(10.0)
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 250.0, "coo_qual": float("nan")}) == pytest.approx(0.25)  # no grade: the error alone, as ``err``
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_qual": "?"}) == 0.6  # neither: the profile value
    assert am.infer_poserr_arcsec("NED", {"coo_qual": "D"}) == 0.6  # SIMBAD rows only


def test_err_alone_does_not_read_the_grade(monkeypatch):
    _annot(monkeypatch, "err")
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": 40.0, "coo_qual": "C"}) == pytest.approx(0.04)
    assert am.infer_poserr_arcsec("SIMBAD", {"coo_err_maj": float("nan"), "coo_qual": "D"}) == 0.6


def test_ned_unc_converts_the_95_percent_semi_major_axis_to_a_sigma(monkeypatch):
    _annot(monkeypatch, "ned_unc")
    assert am.infer_poserr_arcsec("NED", {"ned_unc_maj_arcsec": 2.448}) == pytest.approx(1.0)
    assert am.infer_poserr_arcsec("NED", {"ned_unc_maj_arcsec": float("nan")}) == 0.6
    assert am.infer_poserr_arcsec("SIMBAD", {"ned_unc_maj_arcsec": 2.448}) == 0.6


# ---- the workflow --------------------------------------------------------------------------------------------------------------------------------------------
def test_the_literature_workflow_is_manual_stores_under_its_own_path_and_leaves_the_blind_bundles_alone():
    import yaml

    path = V2.parent / ".github" / "workflows" / "v2_deep_cosmos_literature.yml"
    text = path.read_text()
    y = yaml.safe_load(text)
    on = y.get("on", y.get(True))
    assert set(on) == {"workflow_dispatch"}
    store = json.dumps(y["jobs"]["store"])
    assert "deep_cosmos_lit/" in store and "validation-data" in store and "push_with_retry.sh validation-data" in store
    assert "deep_cosmos1/" not in store and "deep_cosmos2/" not in store  # the blind bundles are not written
    assert "gea.esac.esa.int" not in text and "--require-gaia-tap" not in text  # not tied to the Gaia archive
    assert "probe" in y["jobs"]["field"]["needs"] and y["jobs"]["field"]["strategy"]["max-parallel"] <= 2  # the schema is checked first, few requests at a time
    assert y["jobs"]["store"]["permissions"] == {"contents": "write"} and y["permissions"] == {"contents": "read"}
