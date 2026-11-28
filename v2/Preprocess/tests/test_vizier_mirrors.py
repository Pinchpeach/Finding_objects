"""VizieR mirror fail-over in Get_data/throttle.py (2.36.4)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Get_data"))
import throttle  # noqa: E402


class Resp:
    def __init__(self, code):
        self.status_code = code


@pytest.fixture(autouse=True)
def no_pause(monkeypatch, tmp_path):
    monkeypatch.setenv("V2_CACHE_DIR", str(tmp_path))  # the mirror memory shared with other searches (2.60.0)
    monkeypatch.delenv("V2_CACHE", raising=False)
    monkeypatch.delenv("V2_FAILURE_MEMORY_S", raising=False)
    monkeypatch.setattr(throttle, "pause", lambda: 0.0)
    throttle._preferred.update(host=None, until=0.0)
    throttle._unreachable.clear()


def _send(behaviour, seen):
    import requests

    def send(self, method, url, *a, **k):
        seen.append(url)
        for host, result in behaviour.items():
            if host in url:
                if result == "refuse":
                    raise requests.exceptions.ConnectionError("refused")
                if result == "slow":
                    raise requests.exceptions.ReadTimeout("read timed out")
                return Resp(result)
        return Resp(200)

    return send


def test_refused_cds_falls_over_and_sticks():
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": "refuse"}, seen))
    r = req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=V/164")
    assert r.status_code == 200 and "vizier.cfa.harvard.edu/viz-bin/votable?-source=V/164" in seen[-1]
    seen.clear()
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert "vizier.cfa.harvard.edu" in seen[0]  # the working mirror is tried first


def test_503_is_retried_other_hosts_untouched():
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": 503}, seen))
    assert req(None, "GET", "https://vizier.cds.unistra.fr/x").status_code == 200
    seen.clear()
    req(None, "GET", "https://gea.esac.esa.int/tap-server/tap")
    assert seen == ["https://gea.esac.esa.int/tap-server/tap"]


def test_all_mirrors_refuse_raises():
    import requests

    seen = []
    req = throttle._with_mirrors(_send({h: "refuse" for h in throttle.VIZIER_HOSTS}, seen))
    with pytest.raises(requests.exceptions.ConnectionError):
        req(None, "GET", "https://vizier.cds.unistra.fr/x")
    assert len(seen) == len(throttle.VIZIER_HOSTS)


def test_read_timeout_falls_over():
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": "slow"}, seen))
    assert req(None, "GET", "https://vizier.cds.unistra.fr/x").status_code == 200
    assert "vizier.cfa.harvard.edu" in seen[-1]


def test_short_connect_timeout_keeps_the_read_timeout():
    import requests

    seen = []

    def send(self, method, url, *args, **kwargs):
        seen.append((url.split("/")[2], kwargs.get("timeout")))
        if "unistra" in url:
            raise requests.exceptions.ConnectTimeout("down")
        return Resp(200)

    r = throttle._with_mirrors(send)(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable", timeout=60)
    assert r.status_code == 200
    t = (throttle.CONNECT_TIMEOUT_S, 60)
    assert seen == [("vizier.cds.unistra.fr", t), ("vizier.cfa.harvard.edu", t)]


def test_server_error_moves_to_the_next_mirror():
    seen = []

    def send(self, method, url, *args, **kwargs):
        host = url.split("/")[2]
        seen.append(host)
        return Resp(500 if host == "vizier.idia.ac.za" else 200)

    throttle._preferred.update(host="vizier.idia.ac.za", until=throttle.time.monotonic() + 600)
    r = throttle._with_mirrors(send)(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert r.status_code == 200 and seen[:2] == ["vizier.idia.ac.za", "vizier.cds.unistra.fr"]


def test_tableless_mirror_answer_is_not_trusted():
    """2.47.0: CfA answered 200 with a VOTable holding no table for every
    catalogue while Strasbourg was down; the next mirror's table wins."""
    import requests

    class V:
        def __init__(self, text):
            self.status_code, self.text, self.headers = 200, text, {"Content-Type": "text/xml;content=x-votable"}

    seen = []

    def send(self, method, url, *a, **k):
        seen.append(url)
        if "cds.unistra" in url:
            raise requests.exceptions.ConnectionError("refused")
        if "cfa.harvard" in url:
            return V("<VOTABLE><RESOURCE></RESOURCE></VOTABLE>")
        return V("<VOTABLE><RESOURCE><TABLE><TR><TD>1</TD></TR></TABLE></RESOURCE></VOTABLE>")

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert "<TABLE>" in r.text
    assert "cfa.harvard" not in str(throttle._preferred["host"])


def test_tableless_everywhere_is_a_real_empty_cone():
    class V:
        def __init__(self):
            self.status_code, self.text, self.headers = 200, "<VOTABLE><RESOURCE></RESOURCE></VOTABLE>", {}

    r = throttle._with_mirrors(lambda self, m, url, *a, **k: V())(
        None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable"
    )
    assert "<TABLE" not in r.text


def test_404_from_strasbourg_moves_to_a_mirror():
    # 2026-11-11: Strasbourg answered 404 to every viz-bin/votable query (2.51.0)
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": 404}, seen))
    r = req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=II/328/allwise")
    assert r.status_code == 200 and "vizier.cfa.harvard.edu" in seen[-1]


MINI = "-source=VIII/65/nvss\n-out.max=unlimited\n-out.all\n-c=150.1+2.2\n-c.rs=2.0\n-out.form=mini\n-oc.form=d"


class _V:
    def __init__(self, text):
        self.status_code, self.text, self.headers = 200, text, {"Content-Type": "text/xml;content=x-votable"}


def test_empty_cone_on_a_mirror_is_confirmed_not_cascaded():
    """2.54.0: with Strasbourg at 404, astroquery's mini-form answer to an
    empty cone has no <TABLE>; asked again without the mini form the mirror
    returns an empty table, so the answer is accepted there instead of being
    sent to every other mirror (~50 s per query on 2026-11-15)."""
    seen = []

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append((host, "-out.form=mini" in (data or "")))
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        if "-out.form=mini" in data:
            return _V("<VOTABLE><RESOURCE><INFO name='x'/></RESOURCE></VOTABLE>")
        return _V(
            "<VOTABLE><RESOURCE><TABLE><FIELD name='_RAJ2000'/><DATA><TABLEDATA></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"
        )

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert "<TABLE" not in r.text  # the original (empty) answer is returned
    assert seen == [
        ("vizier.cds.unistra.fr", True),
        ("vizier.cfa.harvard.edu", True),
        ("vizier.cfa.harvard.edu", False),
    ]
    assert throttle._preferred["host"] == "vizier.cfa.harvard.edu"


def test_mirror_without_the_catalogue_is_still_passed_over():
    """The confirmation of a mirror that lacks the catalogue has no table
    either (unknown catalogue: plain <RESOURCE>): the next mirror is asked."""
    seen = []

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        if host == "vizier.cfa.harvard.edu":
            return _V("<VOTABLE><RESOURCE></RESOURCE></VOTABLE>")
        return _V("<VOTABLE><RESOURCE><TABLE><TR><TD>1</TD></TR></TABLE></RESOURCE></VOTABLE>")

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert "<TR>" in r.text
    # the confirmation has no table either; the existence probe (the catalogue without a cone) has none: it lacks it
    assert seen[:5] == [
        "vizier.cds.unistra.fr",
        "vizier.cfa.harvard.edu",
        "vizier.cfa.harvard.edu",
        "vizier.cfa.harvard.edu",
        "vizier.nao.ac.jp",
    ]


def test_unreachable_mirror_is_tried_last():
    import requests

    seen = []

    def send(self, method, url, *a, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host in ("vizier.cds.unistra.fr", "vizier.cfa.harvard.edu"):
            raise requests.exceptions.ConnectTimeout("no connection")
        return Resp(200)

    req = throttle._with_mirrors(send)
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert seen == ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.nao.ac.jp"]
    seen.clear()
    throttle._preferred.update(host=None, until=0.0)
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert seen[0] == "vizier.nao.ac.jp"  # both hosts that did not connect come last
    assert throttle._vizier_order("vizier.cds.unistra.fr")[-2:] == ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu"]


def test_mini_form_removed_from_the_body():
    assert throttle._without_mini_form(MINI).splitlines()[-1] == "-out.max=1"
    assert "-out.form" not in throttle._without_mini_form(MINI)
    assert throttle._without_mini_form(None) is None


def test_confirmation_with_rows_is_not_an_empty_cone():
    """A table-less mini answer whose confirmation has a row was wrong (CfA,
    Gaia DR3 cone with 349 sources, 2026-11-15): the next mirror is asked."""
    seen = []

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        if host == "vizier.cfa.harvard.edu":
            if "-out.form=mini" in data:
                return _V("<VOTABLE><RESOURCE></RESOURCE></VOTABLE>")
            return _V(
                "<VOTABLE><RESOURCE><TABLE><DATA><TABLEDATA><TR><TD>1</TD></TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"
            )
        return _V(
            "<VOTABLE><RESOURCE><TABLE><DATA><TABLEDATA><TR><TD>1</TD></TR><TR><TD>2</TD></TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"
        )

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert r.text.count("<TR>") == 2
    assert seen[:4] == ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.cfa.harvard.edu", "vizier.nao.ac.jp"]


def test_a_mirror_that_failed_is_tried_last_by_the_next_search():
    """2.60.0: the failed-mirror memory is shared through archive_cache, so a new process does not ask the
    refusing / timing-out mirrors first again (a cold search spent ~57 s of collector time on them)."""
    seen = []
    behaviour = {
        "vizier.cds.unistra.fr": "refuse",
        "vizier.cfa.harvard.edu": 404,
        "vizier.nao.ac.jp": "refuse",
        "vizier.iucaa.in": "slow",
    }
    req = throttle._with_mirrors(_send(behaviour, seen))
    r = req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=J/x")
    assert r.status_code == 200 and "vizier.china-vo.org" in seen[-1]  # cds, cfa, nao, iucaa failed first
    assert len(seen) == 5
    # a new process: nothing in memory, only the file
    throttle._preferred.update(host=None, until=0.0)
    throttle._unreachable.clear()
    order = throttle._vizier_order("vizier.cds.unistra.fr")
    assert order[0] == "vizier.china-vo.org" or order[:2] == ["vizier.china-vo.org", "vizier.idia.ac.za"]
    assert set(order[-4:]) == {"vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.nao.ac.jp", "vizier.iucaa.in"}
    seen.clear()
    assert req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable").status_code == 200
    assert len(seen) == 1  # China-VO answered at once: the four failed mirrors were not asked


def test_the_failed_mirror_is_asked_when_the_others_fail_and_an_answer_forgets_it():
    import archive_cache

    seen = []
    behaviour = {h: "refuse" for h in throttle.VIZIER_HOSTS if h != "vizier.nao.ac.jp"}
    req = throttle._with_mirrors(_send(behaviour, seen))
    throttle._unreachable.clear()
    archive_cache.note_source("vizier:vizier.nao.ac.jp", False)
    assert req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable").status_code == 200  # NAO answered last
    assert seen[-1].startswith("https://vizier.nao.ac.jp")
    assert not archive_cache.source_down("vizier:vizier.nao.ac.jp")  # it answered: forgotten


def test_the_mirror_memory_is_off_without_the_cache(monkeypatch):
    import archive_cache

    monkeypatch.setenv("V2_CACHE", "0")
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": "refuse"}, seen))
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    throttle._unreachable.clear()  # a new process: only the file could tell
    throttle._preferred.update(host=None, until=0.0)
    assert not archive_cache.source_down("vizier:vizier.cds.unistra.fr")
    assert throttle._vizier_order("vizier.cds.unistra.fr")[0] == "vizier.cds.unistra.fr"


def test_catalogue_of_a_request():
    assert (
        throttle._catalog_of("https://vizier.cds.unistra.fr/viz-bin/votable?-source=II/246/out&-c=1", None)
        == "II/246/out"
    )
    assert (
        throttle._catalog_of("https://x/viz-bin/votable", "-c=1 2\n-source=J/ApJS/256/43/table9\n-out.form=mini")
        == "J/ApJS/256/43/table9"
    )
    assert throttle._catalog_of("https://x/viz-bin/votable", b"-source=B/sn/sncat\n-out.max=1") == "B/sn/sncat"
    assert (
        throttle._catalog_of("https://x/viz-bin/votable", {"-source": "VII/274/bzcat5", "-c": "1 2"})
        == "VII/274/bzcat5"
    )
    assert throttle._catalog_of("https://x/viz-bin/votable", None) is None


def _catalogue_send(seen):
    """cds 404; cfa holds nothing (table-less, also without the mini form); nao / iucaa / china refuse; idia has it."""
    import requests

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        if host == "vizier.cfa.harvard.edu":
            return _V("<VOTABLE><RESOURCE></RESOURCE></VOTABLE>")
        if host in ("vizier.nao.ac.jp", "vizier.china-vo.org"):
            raise requests.exceptions.ConnectionError("refused")
        if host == "vizier.iucaa.in":
            raise requests.exceptions.ReadTimeout("read timed out")
        return _V("<VOTABLE><RESOURCE><TABLE><TR><TD>1</TD></TR></TABLE></RESOURCE></VOTABLE>")

    return send


def test_a_mirror_without_the_catalogue_is_asked_last_for_that_catalogue_next_time():
    """2.60.2: a cold search of the four AGB tables spent 8-13 requests on the CfA mirror (no table), the dead mirrors and
    IDIA; the next search asks IDIA first for the catalogues CfA lacks, and CfA first for the others."""
    body = "-source=J/ApJS/256/43/table9\n-out.form=mini"
    seen = []
    req = throttle._with_mirrors(_catalogue_send(seen))
    url = "https://vizier.cds.unistra.fr/viz-bin/votable"
    assert "<TR>" in req(None, "POST", url, data=body).text
    assert seen == [
        "vizier.cds.unistra.fr",
        "vizier.cfa.harvard.edu",
        "vizier.cfa.harvard.edu",  # the confirmation: no table
        "vizier.cfa.harvard.edu",  # the existence probe: no table, it lacks the catalogue
        "vizier.nao.ac.jp",
        "vizier.iucaa.in",
        "vizier.china-vo.org",
        "vizier.idia.ac.za",
    ]  # 8 requests
    throttle._preferred.update(host=None, until=0.0)  # a new process: only the file remembers
    throttle._unreachable.clear()
    assert throttle._vizier_order("vizier.cds.unistra.fr", "J/ApJS/256/43/table9")[0] == "vizier.idia.ac.za"
    assert (
        throttle._vizier_order("vizier.cds.unistra.fr", "J/other")[0] == "vizier.cfa.harvard.edu"
    )  # not lacking there
    seen.clear()
    assert "<TR>" in req(None, "POST", url, data=body).text
    assert seen == ["vizier.idia.ac.za"]  # one request instead of eight


def test_the_catalogue_memory_ends_off_and_is_forgotten_when_the_mirror_has_it(monkeypatch):
    import archive_cache

    body = "-source=J/x\n-out.form=mini"
    seen = []
    throttle._with_mirrors(_catalogue_send(seen))(
        None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=body
    )
    assert throttle._lacking("J/x") == {"vizier.cfa.harvard.edu"}
    # the mirror answers with an empty table (it has the catalogue): the memory is forgotten
    throttle._lacks("vizier.cfa.harvard.edu", "J/x", ok=True)
    assert throttle._lacking("J/x") == set()
    # off: V2_CATALOG_MEMORY_S = 0 remembers nothing
    monkeypatch.setenv("V2_CATALOG_MEMORY_S", "0")
    throttle._lacks("vizier.cfa.harvard.edu", "J/x")
    assert throttle._lacking("J/x") == set()
    # an entry ends with its own time, shorter than the failure memory
    monkeypatch.setenv("V2_CATALOG_MEMORY_S", "0.05")
    throttle._lacks("vizier.cfa.harvard.edu", "J/x")
    assert throttle._lacking("J/x") == {"vizier.cfa.harvard.edu"}
    import time

    time.sleep(0.1)
    assert throttle._lacking("J/x") == set()
    # a 2.60.0 file ({key: time}) is still read with the failure memory
    archive_cache._sources_path().write_text('{"vizier:vizier.nao.ac.jp": %f}' % time.time())
    assert archive_cache.source_down("vizier:vizier.nao.ac.jp")


def _holding_send(seen):
    """cds 404; cfa answers an empty cone without a table (also without the mini form) but holds the catalogue."""

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append((host, "probe" if data and "-c=" not in data else "cone"))
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        if "-c=" not in (data or ""):  # the existence probe: the catalogue without a cone has a row
            return _V("<VOTABLE><RESOURCE><TABLE><TR><TD>1</TD></TR></TABLE></RESOURCE></VOTABLE>")
        return _V("<VOTABLE><RESOURCE></RESOURCE></VOTABLE>")

    return send


def test_an_empty_cone_of_a_catalogue_the_mirror_holds_is_accepted_after_the_existence_probe():
    """2.60.2: CfA answers an empty cone of J/ApJS/256/43/table10 without a table, before and after the mini form;
    the probe finds a row, so the empty cone is accepted at CfA (before: NAO, IUCAA, China-VO, IDIA, 150 s)."""
    body = "-source=J/ApJS/256/43/table10\n-c=266.4-28.9\n-c.rm=6.0\n-out.form=mini"
    seen = []
    req = throttle._with_mirrors(_holding_send(seen))
    url = "https://vizier.cds.unistra.fr/viz-bin/votable"
    r = req(None, "POST", url, data=body)
    assert "<TABLE" not in r.text  # the empty answer is the answer
    assert seen == [
        ("vizier.cds.unistra.fr", "cone"),
        ("vizier.cfa.harvard.edu", "cone"),
        ("vizier.cfa.harvard.edu", "cone"),  # the confirmation (same cone, no mini form)
        ("vizier.cfa.harvard.edu", "probe"),
    ]
    assert throttle._holds_known("vizier.cfa.harvard.edu", "J/ApJS/256/43/table10")
    seen.clear()
    throttle._preferred.update(host=None, until=0.0)
    throttle._unreachable.clear()
    req(None, "POST", url, data=body)  # a new process: the probe is remembered, the confirmation is not skipped
    assert seen == [("vizier.cfa.harvard.edu", "cone"), ("vizier.cfa.harvard.edu", "cone")]


def test_the_existence_probe_body_has_no_cone_and_one_row():
    body = "-source=J/x\n-c=1+2\n-c.rm=6.0\n-out.all\n-out.max=unlimited\n-out.form=mini\n-oc.form=d"
    assert throttle._probe_body(body).splitlines() == ["-source=J/x", "-out.all", "-out.max=1"]
    d = throttle._probe_body({"-source": "J/x", "-c": "1 2", "-c.rm": 6, "-out.form": "mini"})
    assert d == {"-source": "J/x", "-out.max": 1}
    assert throttle._probe_body(None) is None


DB_DOWN = (
    '<VOTABLE><RESOURCE type="results"><INFO ID="ERROR" NAME="ERROR" VALUE="THE DATABASE IS NOT CURRENTLY REACHABLE."/>'
    '<INFO NAME="ERROR" VALUE=" "/><INFO NAME="ERROR" VALUE=" -- NO CONNECTION"/></RESOURCE></VOTABLE>'
)
NOT_FOUND = (
    '<VOTABLE><RESOURCE type="results"><INFO NAME="ERROR" VALUE="Table or Catalog not found: J/FAKE/999/none;--POSTGRES MSG"/>'
    "</RESOURCE></VOTABLE>"
)
ROWS = "<VOTABLE><RESOURCE><TABLE><TR><TD>1</TD></TR></TABLE></RESOURCE></VOTABLE>"
EMPTY = "<VOTABLE><RESOURCE></RESOURCE></VOTABLE>"


def test_the_error_of_a_votable_is_read():
    assert throttle._answer_error(_V(DB_DOWN)) == "THE DATABASE IS NOT CURRENTLY REACHABLE.; NO CONNECTION"
    assert "not found" in throttle._answer_error(_V(NOT_FOUND)).lower()
    assert throttle._error_kind(throttle._answer_error(_V(DB_DOWN))) == "backend"
    assert throttle._error_kind(throttle._answer_error(_V(NOT_FOUND))) == "not found"
    assert throttle._answer_error(_V(EMPTY)) is None and throttle._answer_error(_V(ROWS)) is None


def test_a_failed_database_of_a_mirror_is_asked_again_before_the_next_mirror():
    """2.60.2: CfA answers 200 with 'THE DATABASE IS NOT CURRENTLY REACHABLE' in 1 of 6 requests (0.1-0.5 s answers);
    the mirrors after it refuse or need 8-17 s: the same mirror is asked once more."""
    seen, calls = [], {"cfa": 0}

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        calls["cfa"] += 1
        return _V(DB_DOWN if calls["cfa"] == 1 else ROWS)

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert "<TR>" in r.text and seen == ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.cfa.harvard.edu"]


def test_a_mirror_whose_database_stays_down_is_left_for_the_next_one():
    seen = []

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        return _V(DB_DOWN if host == "vizier.cfa.harvard.edu" else ROWS)

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert "<TR>" in r.text
    assert seen == ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.cfa.harvard.edu", "vizier.nao.ac.jp"]
    import archive_cache

    assert archive_cache.source_down("vizier:vizier.cfa.harvard.edu")  # tried last by the next search


def test_a_mirror_that_says_not_found_lacks_the_catalogue():
    seen = []

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        return _V(NOT_FOUND if host == "vizier.cfa.harvard.edu" else ROWS)

    body = "-source=VIII/92/first14\n-c=1+2\n-out.form=mini"
    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=body)
    assert "<TR>" in r.text and seen == ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.nao.ac.jp"]
    assert throttle._lacking("VIII/92/first14") == {"vizier.cfa.harvard.edu"}


def test_the_confirmation_of_a_mirror_whose_database_failed_is_asked_again():
    """The first answer is an empty cone; the confirmation hits a failed database once, then says 'empty table'."""
    n = {"confirm": 0}
    seen = []

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        seen.append(host)
        if host == "vizier.cds.unistra.fr":
            return Resp(404)
        if "-out.form=mini" in (data or ""):
            return _V(EMPTY)
        n["confirm"] += 1
        return _V(DB_DOWN if n["confirm"] == 1 else "<VOTABLE><RESOURCE><TABLE></TABLE></RESOURCE></VOTABLE>")

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert "<TABLE" not in r.text  # the empty cone is the answer
    assert seen == ["vizier.cds.unistra.fr"] + ["vizier.cfa.harvard.edu"] * 3  # cone, confirmation, confirmation again


def test_a_mirror_that_timed_out_is_tried_last_by_the_next_request_of_the_process():
    """2.60.2: IUCAA times out after 10 s every time; each of the collectors that ran in parallel paid it again."""
    seen = []
    req = throttle._with_mirrors(
        _send({"vizier.cds.unistra.fr": "refuse", "vizier.cfa.harvard.edu": "slow", "vizier.nao.ac.jp": "slow"}, seen)
    )
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert seen[-1].startswith("https://vizier.nao.ac.jp") is False and "vizier.iucaa.in" in seen[-1]
    seen.clear()
    throttle._preferred.update(host=None, until=0.0)
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert len(seen) == 1 and "vizier.iucaa.in" in seen[0]  # the three that did not answer are not asked first again


def test_a_failed_database_everywhere_is_an_error_not_an_empty_cone():
    """2.60.2 review: CfA's 'database not reachable' (HTTP 200, no table) on the last mirror left was returned as the
    answer, which astroquery reads as a cone without rows; it is an error now."""
    import pytest

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        if host == "vizier.cfa.harvard.edu":
            return _V(DB_DOWN)
        raise __import__("requests").exceptions.ConnectionError("refused")

    with pytest.raises(RuntimeError, match="NOT CURRENTLY REACHABLE"):
        throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert throttle._preferred["host"] is None  # the failing mirror is not preferred


def test_a_catalogue_no_reachable_mirror_holds_is_an_error_not_an_empty_cone():
    """2.60.2 review: Strasbourg down, CfA 'Table or Catalog not found', the rest refused: not an empty cone."""
    import pytest

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        if host == "vizier.cfa.harvard.edu":
            return _V(NOT_FOUND)
        raise __import__("requests").exceptions.ConnectionError("refused")

    with pytest.raises(RuntimeError, match="not found"):
        throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)


def test_a_mirror_whose_probe_says_it_lacks_the_catalogue_is_not_an_empty_cone_when_no_other_answers():
    """2.60.2 review: table-less cone and confirmation, and the existence probe without a table (the mirror lacks the
    catalogue): with every other mirror refused this is an error, not an empty result."""
    import pytest

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        if host == "vizier.cfa.harvard.edu":
            return _V(EMPTY)  # cone, confirmation and probe: no table, no error
        raise __import__("requests").exceptions.ConnectionError("refused")

    with pytest.raises(RuntimeError, match="lacks the catalogue"):
        throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)


def test_a_failed_confirmation_is_not_settled_by_the_existence_probe():
    """PR #78 review: CfA's cone answer has no table, its confirmation fails with 503 and its existence probe finds the
    catalogue; the cone must not be taken as empty: the next mirror's rows win."""
    calls = {"cfa": 0}

    class R:
        def __init__(self, code, text):
            self.status_code, self.text, self.headers = code, text, {"Content-Type": "text/xml;content=x-votable"}

    def send(self, method, url, *a, data=None, **k):
        host = url.split("/")[2]
        if host == "vizier.cds.unistra.fr":
            raise __import__("requests").exceptions.ConnectionError("refused")
        if host == "vizier.cfa.harvard.edu":
            calls["cfa"] += 1
            return {1: R(200, EMPTY), 2: R(503, "")}.get(calls["cfa"], R(200, ROWS))  # cone, confirmation, probe
        return R(200, ROWS.replace("<TD>1</TD>", "<TD>nao</TD>"))

    r = throttle._with_mirrors(send)(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=MINI)
    assert "nao" in r.text  # not CfA's empty cone
    assert calls["cfa"] == 2  # no existence probe after a failed confirmation


# ---- a cut-off answer is a failure of the mirror (2.61.6) --------------------------------------------------------
VOTABLE = b'<?xml version="1.0"?><VOTABLE version="1.4"><RESOURCE><TABLE name="t"><DATA><TABLEDATA><TR><TD>1</TD></TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>\n'


class BodyResp:
    def __init__(self, body: bytes, code: int = 200, ctype: str = "application/x-votable+xml"):
        self.status_code = code
        self.content = body
        self.text = body.decode("utf-8", "replace")
        self.headers = {"Content-Type": ctype}


def _body_send(behaviour, seen):
    """``behaviour``: host -> bytes (a body), an exception class (raised) or a Resp."""

    def send(self, method, url, *a, **k):
        seen.append(url)
        for host, result in behaviour.items():
            if host in url:
                if isinstance(result, type) and issubclass(result, Exception):
                    raise result("cut off")
                return BodyResp(result) if isinstance(result, bytes) else result
        return BodyResp(VOTABLE)

    return send


def test_a_votable_cut_off_before_its_end_tag_is_detected():
    cut = VOTABLE[: len(VOTABLE) // 2]
    assert throttle._truncated_votable(BodyResp(cut))
    assert not throttle._truncated_votable(BodyResp(VOTABLE))
    assert not throttle._truncated_votable(BodyResp(VOTABLE + b"   \n"))
    assert throttle._truncated_votable(BodyResp(b"<VOTABLE><RESOURCE>" + b"x" * 5000, ctype="text/plain"))  # found by its head
    assert not throttle._truncated_votable(BodyResp(b'{"a": [1, 2', ctype="application/json"))  # not a VOTable
    assert not throttle._truncated_votable(BodyResp(cut, code=503))  # an error status is handled as before
    assert not throttle._truncated_votable(Resp(200))  # a fake without a body


def test_a_cut_off_answer_goes_to_the_next_mirror_and_the_cut_mirror_is_tried_last_afterwards():
    seen = []
    cut = VOTABLE[:60]
    req = throttle._with_mirrors(_body_send({"vizier.cds.unistra.fr": cut}, seen))
    r = req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert r.content == VOTABLE and "vizier.cfa.harvard.edu" in seen[-1]
    assert len(seen) == 2
    assert throttle.last_host() == "vizier.cfa.harvard.edu"
    seen.clear()
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert "vizier.cfa.harvard.edu" in seen[0]  # the mirror that cut the answer is not asked first again


def test_a_body_cut_off_in_transfer_goes_to_the_next_mirror():
    import requests

    seen = []
    req = throttle._with_mirrors(_body_send({"vizier.cds.unistra.fr": requests.exceptions.ChunkedEncodingError}, seen))
    assert req(None, "GET", "https://vizier.cds.unistra.fr/x").content == VOTABLE
    assert "vizier.cfa.harvard.edu" in seen[-1]
    seen.clear()
    req(None, "GET", "https://vizier.cds.unistra.fr/x")
    assert "vizier.cds.unistra.fr" not in seen[0]  # remembered as failing


def test_an_answer_that_every_mirror_cuts_off_is_an_error_not_half_a_table():
    import requests

    seen = []
    req = throttle._with_mirrors(_body_send({h: VOTABLE[:60] for h in throttle.VIZIER_HOSTS}, seen))
    with pytest.raises(requests.exceptions.ChunkedEncodingError, match="cut off"):
        req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert len(seen) == len(throttle.VIZIER_HOSTS)  # every mirror was asked once


def test_a_complete_answer_is_returned_as_before():
    seen = []
    req = throttle._with_mirrors(_body_send({}, seen))
    r = req(None, "GET", "https://vizier.cds.unistra.fr/x")
    assert r.content == VOTABLE and len(seen) == 1


def test_a_caller_that_could_not_read_an_answer_distrusts_its_mirror():
    seen = []
    req = throttle._with_mirrors(_body_send({}, seen))
    req(None, "GET", "https://vizier.cds.unistra.fr/x")
    assert throttle.last_host() == "vizier.cds.unistra.fr"
    assert throttle.distrust_last_mirror() == "vizier.cds.unistra.fr"
    seen.clear()
    req(None, "GET", "https://vizier.cds.unistra.fr/x")
    assert "vizier.cds.unistra.fr" not in seen[0]  # the retry starts at another mirror


def test_a_request_that_fails_everywhere_leaves_no_mirror_to_distrust():
    """2.61.6 review: after a request that every mirror cut off, the caller's distrust must not fall on the mirror that
    answered the previous request well."""
    import requests

    seen = []
    good = throttle._with_mirrors(_body_send({}, seen))
    good(None, "GET", "https://vizier.cds.unistra.fr/x")
    assert throttle.last_host() == "vizier.cds.unistra.fr"
    bad = throttle._with_mirrors(_body_send({h: VOTABLE[:60] for h in throttle.VIZIER_HOSTS}, seen))
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        bad(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert throttle.last_host() is None and throttle.distrust_last_mirror() is None


def test_a_cut_answer_is_reported_even_when_the_other_mirrors_refuse():
    """Codex review of 2.61.6: one mirror cuts the table off, every other refuses; the request ends in the truncation
    error (the caller can ask in smaller pieces), not in the last connection error."""
    import requests

    seen = []
    behaviour = {h: requests.exceptions.ConnectionError for h in throttle.VIZIER_HOSTS}
    behaviour["vizier.cfa.harvard.edu"] = VOTABLE[:60]
    req = throttle._with_mirrors(_body_send(behaviour, seen))
    with pytest.raises(requests.exceptions.ChunkedEncodingError, match="cut off"):
        req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert len(seen) == len(throttle.VIZIER_HOSTS)



@pytest.mark.parametrize("broken", ["ChunkedEncodingError", "ContentDecodingError"])
def test_a_body_broken_in_transfer_is_reported_even_when_the_other_mirrors_refuse(broken):
    """Codex review of b51d74b: CfA's body breaks off in transfer, every later mirror refuses or times out; the
    request ends in the truncation error, not in the last connection error, so the caller halves the batch."""
    import requests

    seen = []
    errors = {h: requests.exceptions.ConnectionError("refused") for h in throttle.VIZIER_HOSTS}
    errors["vizier.cfa.harvard.edu"] = getattr(requests.exceptions, broken)("IncompleteRead(1024 bytes read)")
    errors[throttle.VIZIER_HOSTS[-1]] = requests.exceptions.ReadTimeout("read timeout=300")

    def send(self, method, url, *a, **k):
        seen.append(url)
        raise next(e for h, e in errors.items() if h in url)

    req = throttle._with_mirrors(send)
    with pytest.raises(requests.exceptions.ChunkedEncodingError, match=rf"in transfer \({broken}\)"):
        req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert len(seen) == len(throttle.VIZIER_HOSTS)


@pytest.mark.parametrize("status", [503, 404])
def test_a_cut_answer_outranks_the_error_status_of_the_last_mirror(status):
    """Codex review of 4d216f9: CfA cuts the table off, every other mirror (the last one too) answers an error status;
    the request ends in the truncation error, not in the last mirror's error response."""
    import requests

    seen = []
    behaviour = {h: BodyResp(b"Service Unavailable", code=status, ctype="text/html") for h in throttle.VIZIER_HOSTS}
    behaviour["vizier.cfa.harvard.edu"] = VOTABLE[:60]
    req = throttle._with_mirrors(_body_send(behaviour, seen))
    with pytest.raises(requests.exceptions.ChunkedEncodingError, match="before </VOTABLE>"):
        req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert len(seen) == len(throttle.VIZIER_HOSTS)


def test_the_last_mirror_error_status_is_still_returned_when_no_mirror_cut_the_table():
    seen = []
    behaviour = {h: BodyResp(b"Service Unavailable", code=503, ctype="text/html") for h in throttle.VIZIER_HOSTS}
    req = throttle._with_mirrors(_body_send(behaviour, seen))
    resp = req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=I/355/gaiadr3")
    assert resp.status_code == 503 and len(seen) == len(throttle.VIZIER_HOSTS)


def _multi(n):
    """The body astroquery posts for a multi-target cone of ``n`` positions (Vizier.query_region(..., get_query_payload=True))."""
    pos = "\n".join(f"{10 + i * 0.01:.8f}+{1 + i * 0.01:.8f}" for i in range(n))
    return f"-source=I/355/gaiadr3\n-out.max=unlimited\n-out.all\n-out.add=_q\n-c.rs=12.0\n-out.form=mini\n-c=<<====AstroqueryList\n{pos}\n====AstroqueryList"


def test_the_positions_of_a_request_are_counted():
    assert throttle._targets(_multi(500)) == 500 and throttle._targets(_multi(1)) == 1
    assert throttle._targets(_multi(3).encode()) == 3
    assert throttle._targets({"-source": "I/355", "-c": "10.0+1.0"}) == 1 and throttle._targets("-source=I/355&-c=10+1") == 1 and throttle._targets(None) == 1


def test_a_batch_larger_than_a_mirrors_limit_is_not_sent_there_while_another_mirror_can_take_it():
    """2.62.12: CfA answers 504 after 60 s to 500 Gaia positions (probe run 46118073648: 50 answered, 250 never); IDIA answers them."""
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": 404}, seen))
    req(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=_multi(500))
    assert "vizier.cfa.harvard.edu" not in seen[1] and len(seen) == 2  # Strasbourg's 404, then the next mirror within its limit
    throttle._preferred.update(host=None, until=0.0)
    throttle._unreachable.clear()
    seen.clear()
    req(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=_multi(50))
    assert "vizier.cfa.harvard.edu" in seen[0]  # within CfA's limit: the order is unchanged (Strasbourg's 404 is remembered: asked last)
    seen.clear()
    req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=V/164&-c=10+1")
    assert "vizier.cfa.harvard.edu" in seen[0]  # a single cone: unchanged (CfA answered and is now preferred)


def test_a_mirror_over_its_limit_is_still_asked_when_every_other_mirror_fails():
    seen = []
    req = throttle._with_mirrors(_send({h: "refuse" for h in throttle.VIZIER_HOSTS if h != "vizier.cfa.harvard.edu"}, seen))
    assert req(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable", data=_multi(500)).status_code == 200
    assert "vizier.cfa.harvard.edu" in seen[-1] and len(seen) == len(throttle.VIZIER_HOSTS)
