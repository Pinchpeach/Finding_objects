"""Fewer archive requests per search (2.60.0): the SIMBAD collector's request count, the memory of a failed server,
and the request log (V2_HTTP_LOG) of requests that do not go through ``requests``."""

import sys
import time
from pathlib import Path

import pandas as pd
import pytest

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import archive_cache  # noqa: E402
import simbad  # noqa: E402
import throttle  # noqa: E402

CDS, HARVARD = simbad.SERVERS


class Table:
    def __init__(self, cols):
        self.cols = cols

    def to_pandas(self):
        return pd.DataFrame(self.cols)

    def __len__(self):
        return len(next(iter(self.cols.values())))


MAIN = {
    "main_id": ["M  1", "NGC 1"],
    "ra": [150.1, 150.2],
    "dec": [2.1, 2.2],
    "otype": ["SNR", "G"],
    "otype_label": ["Supernova Remnant", "Galaxy"],
}
REFS = {
    "main_id": ["M  1", "M  1", "M  1", "M  1", "NGC 1"],
    "nbref": [900, 900, 900, 900, 12],
    "bibcode": ["a", "b", "c", "d", "e"],
    "ref_year": [2001, 2002, 2003, 2004, 1999],
    "title": ["A", "B", "C", "D", "E|x"],
    "obj_freq": [1, 5, 5, 0, 2],
}


@pytest.fixture
def sim(monkeypatch, tmp_path):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("V2_CACHE", raising=False)
    monkeypatch.delenv("V2_FAILURE_MEMORY_S", raising=False)
    monkeypatch.setattr(simbad, "_cone_numbers", lambda ra, dec, r: (ra, dec, r / 60.0))
    calls = []

    def install(down=(), main=MAIN, refs=REFS, overflow=False):
        def tap(server, adql, maxrec=simbad.MAXREC):
            calls.append((server, adql))
            if server in down:
                raise simbad._ServerFailed("HTTP 404")
            if "has_ref" in adql:
                return Table(refs), overflow
            return Table(main), overflow

        monkeypatch.setattr(simbad, "_tap_sync", tap)
        return calls

    return install


def test_a_search_is_two_requests_the_cone_and_its_references(sim):
    calls = sim(down=(CDS,))
    d = simbad.fetch(150.15, 2.15, 2.0)
    assert [c[0] for c in calls] == [CDS, HARVARD, HARVARD]  # the failing server once, then cone, references
    cone, refs = calls[1][1], calls[2][1]
    # one query for the cone with the labels, one for the references of the same cone: no IN list of names
    assert "LEFT JOIN otypedef" in cone and "CONTAINS(POINT('ICRS', basic.ra, basic.dec)" in cone
    assert "b.oid IN (SELECT basic.oid FROM basic WHERE CONTAINS(" in refs and "main_id IN" not in refs
    circle = "CIRCLE('ICRS', 150.15, 2.15, 0.03333333333333333)"
    assert circle in cone and circle in refs  # the same circle
    assert d.simbad_server.eq(HARVARD).all() and d.simbad_reference_query_status.eq("ok").all()


def test_the_references_are_the_three_most_discussed_papers_of_each_object(sim):
    sim()
    d = simbad.fetch(150.15, 2.15, 2.0).set_index("catalog_object_id")
    assert d.loc["M  1", "simbad_ref_bibcodes"] == "c|b|a"  # obj_freq 5 (newer first), then 1
    assert d.loc["M  1", "simbad_nbref"] == 900
    assert d.loc["NGC 1", "simbad_ref_titles"] == "E/x"  # '|' of a title cannot split the list
    assert (
        d.loc["NGC 1", "simbad_otype_label"] == "Galaxy" and d.loc["M  1", "simbad_otype_label"] == "Supernova Remnant"
    )
    cols = list(d.reset_index().columns)
    assert "otype_label" not in cols and cols.index("simbad_otype_label") == cols.index("simbad_server") + 1


def test_equally_ranked_papers_are_taken_in_bibcode_order_whatever_the_server_order(sim):
    tied = {
        "main_id": ["M  1"] * 5,
        "nbref": [5] * 5,
        "bibcode": ["2020z", "2020b", "2020y", "2020a", "2020c"],
        "ref_year": [2020] * 5,
        "title": ["z", "b", "y", "a", "c"],
        "obj_freq": [3] * 5,
    }
    sim(refs=tied)
    d = simbad.fetch(150.15, 2.15, 2.0).set_index("catalog_object_id")
    assert d.loc["M  1", "simbad_ref_bibcodes"] == "2020a|2020b|2020c"
    sim(refs={k: v[::-1] for k, v in tied.items()})  # the server answers in the opposite order
    d = simbad.fetch(150.15, 2.15, 2.0).set_index("catalog_object_id")
    assert d.loc["M  1", "simbad_ref_bibcodes"] == "2020a|2020b|2020c"


def test_an_empty_cone_asks_nothing_more(sim):
    calls = sim(main={k: [] for k in MAIN})
    d = simbad.fetch(150.15, 2.15, 2.0)
    assert len(calls) == 2 - 1 and len(d) == 0  # the cone query only (Strasbourg answers here)
    assert list(d.simbad_reference_status) == [] and "simbad_otype_label" in d


def test_a_server_that_failed_is_asked_last_for_the_failure_memory(sim, monkeypatch):
    calls = sim(down=(CDS,))
    simbad.fetch(150.15, 2.15, 2.0)
    assert archive_cache.source_down(f"simbad:{CDS}")
    calls.clear()
    simbad.fetch(150.15, 2.15, 2.0)
    assert [c[0] for c in calls] == [HARVARD, HARVARD]  # Strasbourg not asked again: 2 requests, not 3
    # it is not skipped for good: when the mirror fails, Strasbourg is asked, and its answer forgets the failure
    calls.clear()
    sim(down=(HARVARD,))
    d = simbad.fetch(150.15, 2.15, 2.0)
    assert [c[0] for c in calls] == [HARVARD, CDS, CDS] and d.simbad_server.eq(CDS).all()
    assert archive_cache.source_down(f"simbad:{HARVARD}") and not archive_cache.source_down(f"simbad:{CDS}")
    # both failing: the error of the last one is raised (the collector reports an error as before)
    sim(down=(HARVARD, CDS))
    with pytest.raises(simbad._ServerFailed):
        simbad.fetch(150.15, 2.15, 2.0)


def test_the_memory_ends_with_its_time_and_an_answer_forgets_it(sim, monkeypatch):
    archive_cache.note_source("simbad:x", False)
    assert archive_cache.source_down("simbad:x")
    archive_cache.note_source("simbad:x", True)  # it answered
    assert not archive_cache.source_down("simbad:x")
    archive_cache.note_source("simbad:y", False)
    monkeypatch.setenv("V2_FAILURE_MEMORY_S", "0.05")
    time.sleep(0.1)
    assert not archive_cache.source_down("simbad:y")
    monkeypatch.setenv("V2_FAILURE_MEMORY_S", "0")  # 0 = off
    archive_cache.note_source("simbad:z", False)
    assert not archive_cache.source_down("simbad:z")


def test_without_the_cache_nothing_is_remembered(sim, monkeypatch):
    monkeypatch.setenv("V2_CACHE", "0")
    calls = sim(down=(CDS,))
    simbad.fetch(150.15, 2.15, 2.0)
    calls.clear()
    simbad.fetch(150.15, 2.15, 2.0)
    assert [c[0] for c in calls] == [CDS, HARVARD, HARVARD]


def test_more_objects_than_the_row_limit_is_an_error_not_a_short_list(sim):
    sim(overflow=True)
    with pytest.raises(RuntimeError, match="more than"):
        simbad.fetch(150.15, 2.15, 2.0)


def test_the_cone_query_selects_what_astroquery_selected():
    """The payload of astroquery 0.4.11 for add_votable_fields(otype, sp, plx, pmra, pmdec, rvz_redshift) + query_region,
    2026-11-23: the same columns in the same order and the same predicate (the results are the same rows)."""
    cols = (
        'basic."main_id", basic."ra", basic."dec", basic."coo_err_maj", basic."coo_err_min", basic."coo_err_angle", '
        'basic."coo_wavelength", basic."coo_bibcode", basic."pmra", basic."pmdec", basic."rvz_redshift", '
        'basic."otype", basic."sp_type", basic."sp_qual", basic."sp_bibcode", basic."plx_value"'
    )
    where = "WHERE CONTAINS(POINT('ICRS', basic.ra, basic.dec), CIRCLE('ICRS', 150.1, 2.25, 0.03333333333333333)) = 1"
    q = simbad._main_adql(150.1, 2.25, 0.03333333333333333)
    assert q.startswith(f"SELECT {cols}, ") and q.endswith(where)


def test_the_request_log_has_the_requests_astroquery_gaia_makes_and_names_helper_threads(monkeypatch, capsys):
    monkeypatch.setenv("V2_HTTP_LOG", "1")
    monkeypatch.setattr(throttle, "MIN_PAUSE_S", 0.0)
    monkeypatch.setattr(throttle, "MAX_PAUSE_S", 0.0)
    sent = []

    class Conn:
        host = "gea.esac.esa.int"

        def request(self, method, url, *a, **k):
            sent.append((method, url))

    logged = throttle._paced(throttle._logged_client(Conn.request))
    logged(Conn(), "POST", "/tap-server/tap/sync?x=1")
    assert sent == [("POST", "/tap-server/tap/sync?x=1")]
    assert "gea.esac.esa.int POST /tap-server/tap/sync (http.client)" in capsys.readouterr().out

    # a request that came through requests is logged by the requests layer, once
    def through_requests(self, method, url):
        throttle._logged_client(Conn.request)(self, method, url)

    throttle._paced(through_requests, via_requests=True)(Conn(), "GET", "/x")
    assert "http.client" not in capsys.readouterr().out
    import threading

    names = []
    t = threading.Thread(target=lambda: names.append(throttle.child_name("tap")), name="gaia_dr3")
    t.start()
    t.join()
    assert names == ["gaia_dr3/tap"]


def test_a_cone_with_very_many_objects_skips_the_references(sim, monkeypatch):
    """2.60.0 review: the references of a cone are objects x papers with titles (COSMOS 20', 192,486 objects:
    1.9 GB with them); above REFERENCE_MAX_OBJECTS only the cone rows are fetched, and the result says so."""
    monkeypatch.setattr(simbad, "REFERENCE_MAX_OBJECTS", 1)
    calls = sim()
    d = simbad.fetch(150.15, 2.15, 2.0)
    assert [c[0] for c in calls] == [CDS]  # the cone only
    assert len(d) == 2 and d.simbad_reference_status.str.startswith("skipped:more_than_1_objects").all()
    assert d.simbad_otype_label.tolist() == ["Supernova Remnant", "Galaxy"]
    # complete rows, but not cached: a smaller cone served from it would lack its references (PR #76 review)
    assert d.simbad_reference_query_status.str.startswith("skipped").all() and not archive_cache.cacheable(d)


def test_vizier_cone_queries_bypass_astroquerys_disk_cache(monkeypatch):
    """2.60.0 review: Vizier.query_region passes cache=True itself, which overrode the global switch of
    controller._disable_astroquery_cache(); every VizieR answer was replayed for 7 days."""
    import types

    import _catalog_utils

    seen = {}

    class FakeVizier:
        def __init__(self, *a, **k):
            pass

        def query_region(self, *a, **k):
            seen.update(k)
            return []

    # a stand-in module: the CI test job has no astroquery (PR #76 review)
    fake = types.ModuleType("astroquery.vizier")
    fake.Vizier = FakeVizier
    if "astroquery" not in sys.modules:
        monkeypatch.setitem(sys.modules, "astroquery", types.ModuleType("astroquery"))
    monkeypatch.setitem(sys.modules, "astroquery.vizier", fake)
    assert _catalog_utils.vizier_cone("I/355/gaiadr3", 10.0, 20.0, 1.0) is None
    assert seen.get("cache") is False
    src = (GET / "pn_spectroscopy.py").read_text()
    import re

    assert re.search(r"query_constraints\(\s*catalog=INTENS,\s*PNG=png,\s*cache=False\s*\)", src)
