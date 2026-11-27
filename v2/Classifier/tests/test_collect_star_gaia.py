"""The VizieR fallback of collect_star_gaia.py retries over the mirrors and splits a batch no mirror delivers (2.61.6)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "Get_data"))
import throttle  # noqa: E402


def _module():
    spec = importlib.util.spec_from_file_location("collect_star_gaia_under_test", V2 / "Classifier" / "collect_star_gaia.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


VOTABLE = b'<?xml version="1.0"?><VOTABLE><RESOURCE><TABLE><DATA></DATA></TABLE></RESOURCE></VOTABLE>'


class Answer:
    def __init__(self, body: bytes):
        self.status_code, self.content, self.headers = 200, body, {"Content-Type": "application/x-votable+xml"}
        self.text = body.decode()


class FakeVizier:
    """What astroquery's Vizier does here: ask the mirrors through ``throttle`` (one request per query_region call),
    then read the answer.  ``scenario`` maps a mirror to what it serves: ``ok``, ``cut`` (a VOTable cut off), ``bad``
    (a complete body the parser rejects).  ``calls`` lists (positions, mirror) of every query."""

    scenario: dict = {}
    calls: list = []
    cached: dict = {}  # astroquery caches a body before parsing it and serves it again to an identical cached request

    def __init__(self, columns=None, row_limit=None):
        self.TIMEOUT = None

    def query_region(self, coords, radius=None, catalog=None, cache=True):
        n = len(coords)
        seen = []
        key = (n, float(coords[0].ra.deg))
        if cache and key in FakeVizier.cached:
            FakeVizier.calls.append((n, "cache"))
            return self._read(FakeVizier.cached[key], n)

        def send(self, method, url, *a, **k):
            seen.append(url)
            host = next(h for h in throttle.VIZIER_HOSTS if h in url)
            what = FakeVizier.scenario.get(host, "ok")
            if isinstance(what, dict):  # {"n>": 3, "what": "cut"}: a long answer is cut off, a short one is not
                what = what["what"] if n > what["n>"] else "ok"
            return Answer(VOTABLE[:40] if what == "cut" else VOTABLE + (b"<!--bad-->" if what == "bad" else b""))

        resp = throttle._with_mirrors(send)(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
        FakeVizier.calls.append((n, throttle.last_host()))
        if cache:
            FakeVizier.cached[key] = resp.content
        return self._read(resp.content, n)

    @staticmethod
    def _read(content, n):
        if b"<!--bad-->" in content:
            raise ValueError("1027:862: no element found")  # TableParseError of astroquery
        d = pd.DataFrame({"_q": range(1, n + 1), "Source": range(n), "RA_ICRS": [10.0 + i for i in range(n)],
                          "DE_ICRS": [20.0] * n, "Plx": [1.0] * n})  # fmt: skip
        return [types.SimpleNamespace(to_pandas=lambda d=d: d)]


@pytest.fixture
def fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("V2_CACHE", raising=False)
    monkeypatch.setattr(throttle, "pause", lambda: 0.0)
    monkeypatch.setattr(throttle, "install", lambda: None)  # no global patch of requests in the test process
    throttle._preferred.update(host=None, until=0.0)
    throttle._unreachable.clear()
    FakeVizier.scenario, FakeVizier.calls, FakeVizier.cached = {}, [], {}
    pkg, vz = types.ModuleType("astroquery"), types.ModuleType("astroquery.vizier")
    vz.Vizier = FakeVizier
    monkeypatch.setitem(sys.modules, "astroquery", pkg)
    monkeypatch.setitem(sys.modules, "astroquery.vizier", vz)
    m = _module()
    monkeypatch.setattr(m, "RETRY_SLEEP_S", 0.0)
    return m


def _truth(n: int) -> pd.DataFrame:
    return pd.DataFrame({"benchmark_id": [f"B{i:04d}" for i in range(n)], "ra": [10.0 + i for i in range(n)], "dec": [20.0] * n})


def test_a_clean_run_gives_the_xmatch_layout(fallback):
    out = fallback._vizier_fallback(_truth(5), 2.0)
    assert list(out.benchmark_id) == [f"B{i:04d}" for i in range(5)]
    assert {"angDist", "truth_ra", "truth_dec", "Source", "Plx"} <= set(out.columns)
    assert (out.angDist < 1e-6).all()  # the rows sit on the truth positions
    assert len(FakeVizier.calls) == 1  # one request for the batch


def test_a_mirror_that_cuts_the_answer_off_is_passed_over_inside_one_attempt(fallback):
    FakeVizier.scenario = {"vizier.cds.unistra.fr": "cut"}
    out = fallback._vizier_fallback(_truth(5), 2.0)
    assert len(out) == 5
    assert FakeVizier.calls == [(5, "vizier.cfa.harvard.edu")]  # one attempt, answered by the second mirror


def test_a_retry_asks_another_mirror_when_the_answer_could_not_be_read(fallback):
    """The 2026-11-27 failure: the preferred mirror's body is not readable; the retry used to ask it again, four times."""
    FakeVizier.scenario = {"vizier.cds.unistra.fr": "bad"}
    out = fallback._vizier_fallback(_truth(5), 2.0)
    assert len(out) == 5
    hosts = [h for _, h in FakeVizier.calls]
    assert hosts[0] == "vizier.cds.unistra.fr" and hosts[1] != hosts[0] and len(hosts) == 2


def test_a_batch_that_no_mirror_delivers_is_halved_and_the_smaller_size_is_kept(fallback, monkeypatch):
    monkeypatch.setattr(fallback, "MIN_SPLIT", 2)
    FakeVizier.scenario = {h: {"n>": 3, "what": "cut"} for h in throttle.VIZIER_HOSTS}  # more than 3 positions: cut everywhere
    out = fallback._vizier_fallback(_truth(8), 2.0)
    assert sorted(out.benchmark_id) == [f"B{i:04d}" for i in range(8)]
    sizes = [n for n, _ in FakeVizier.calls]
    assert sizes == [2, 2, 2, 2]  # 8 -> 4 + 4 (still cut) -> 2 + 2 + 2 + 2: answered when short enough; a cut request records no call


def test_a_batch_at_the_smallest_size_that_still_fails_raises(fallback, monkeypatch):
    monkeypatch.setattr(fallback, "MIN_SPLIT", 50)
    FakeVizier.scenario = {h: "bad" for h in throttle.VIZIER_HOSTS}
    with pytest.raises(ValueError, match="no element found"):
        fallback._vizier_fallback(_truth(5), 2.0)
    assert len(FakeVizier.calls) == fallback.VIZIER_RETRIES_SMALL  # every attempt made, then the error is the caller's


def test_the_output_does_not_depend_on_how_the_answer_was_delivered(fallback):
    clean = fallback._vizier_fallback(_truth(6), 2.0)
    FakeVizier.scenario, FakeVizier.calls = {"vizier.cds.unistra.fr": "cut"}, []
    throttle._preferred.update(host=None, until=0.0)
    throttle._unreachable.clear()
    retried = fallback._vizier_fallback(_truth(6), 2.0)
    pd.testing.assert_frame_equal(clean.reset_index(drop=True), retried.reset_index(drop=True))


def test_a_failure_that_is_not_about_the_answer_does_not_halve_the_batch(fallback, monkeypatch):
    """A refused connection or an error status says nothing about the size: the batch is retried, not split."""
    import requests

    monkeypatch.setattr(fallback, "MIN_SPLIT", 2)

    def refused(self, coords, radius=None, catalog=None, cache=True):
        FakeVizier.calls.append((len(coords), None))
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(FakeVizier, "query_region", refused)
    with pytest.raises(requests.exceptions.ConnectionError):
        fallback._vizier_fallback(_truth(8), 2.0)
    assert [n for n, _ in FakeVizier.calls] == [8] * fallback.VIZIER_RETRIES  # two attempts at 8 positions, no halving


def test_the_smaller_size_found_by_halving_is_kept_for_the_following_batches(fallback, monkeypatch):
    monkeypatch.setattr(fallback, "MIN_SPLIT", 2)
    FakeVizier.scenario = {h: {"n>": 3, "what": "cut"} for h in throttle.VIZIER_HOSTS}  # 4 or more positions: cut everywhere
    out = fallback._vizier_fallback(_truth(12), 2.0)
    assert sorted(out.benchmark_id) == [f"B{i:04d}" for i in range(12)]
    # 12 positions are cut, 6 are cut, 3 are answered: the size 3 is kept for the other nine (not 12 / 6 again)
    assert [n for n, _ in FakeVizier.calls] == [3, 3, 3, 3]
