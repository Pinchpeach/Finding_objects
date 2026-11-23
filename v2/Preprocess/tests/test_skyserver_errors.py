"""SkyServer error pages (2.56.0).

SkyServer reports a failure as an HTML page with HTTP status 200.  One such
page (fixtures/skyserver_error_403.html, received 2026-11-23 for the COSMOS 2'
spectroscopy cone) was stored by astroquery's request cache and replayed to
every later search of that cone, where reading it as a table raised
InconsistentTableError: the failure the 2.55.0 evaluation saw at NGC 4522 2'
on three days.
"""

import sys
from pathlib import Path

import pytest

GET_DATA = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET_DATA))
import _catalog_utils as cu  # noqa: E402

ERROR_PAGE = (Path(__file__).parent / "fixtures" / "skyserver_error_403.html").read_text()
TABLE = (
    "#Table1\nobjID,specobjid,bestobjid,ra,dec,plate,mjd,fiberid,class,subclass,z,zerr,zwarning\n"
    "1237658491746123826,1388316819500066816,1237658491746123826,188.41545,9.174999,1233,52734,299,"
    "GALAXY,STARFORMING,0.007724506,8.744262E-06,0\n"
)


class _R:
    def __init__(self, text):
        self.text = text


def test_error_page_is_recognised_and_tables_are_not():
    msg = cu.skyserver_error(_R(ERROR_PAGE))
    assert "403" in msg and "Forbidden" in msg and "<" not in msg
    assert cu.skyserver_error(_R(TABLE)) == ""
    assert cu.skyserver_error(_R('[\r\n  {\r\n    "TableName": "Table1"')) == ""
    assert cu.skyserver_error(_R("")) == ""


def _client(tmp_path, monkeypatch, answers):
    requests = pytest.importorskip("requests")
    pytest.importorskip("astroquery.sdss")
    from astropy.config import set_temp_cache

    sent = []

    class Offline(requests.adapters.BaseAdapter):
        def send(self, request, **kw):
            r = requests.Response()
            r.status_code, r.url, r.request = 200, request.url, request
            r._content = answers[min(len(sent), len(answers) - 1)].encode()
            sent.append(request.url)
            return r

        def close(self):
            pass

    monkeypatch.setattr(cu.time, "sleep", lambda s: None)
    ctx = set_temp_cache(str(tmp_path))
    ctx.__enter__()
    client = cu._sdss()
    client._session.mount("https://", Offline())
    return client, sent, ctx


def test_error_page_is_retried_and_never_left_in_the_cache(tmp_path, monkeypatch):
    client, sent, ctx = _client(tmp_path, monkeypatch, [ERROR_PAGE, TABLE])
    try:
        url, q = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch", {"cmd": "SELECT 1"}
        r = client._request("GET", url, params=q, cache=True)
        assert r.text == TABLE and len(sent) == 2
        t = client._parse_result(r)
        assert len(t) == 1 and str(t["class"][0]) == "GALAXY"
        # the same request again: no stored error page is replayed
        again = client._request("GET", url, params=q, cache=True)
        assert cu.skyserver_error(again) == "" and len(client._parse_result(again)) == 1
        import pickle

        for f in Path(client.cache_location).glob("*.pickle"):
            assert cu.skyserver_error(pickle.loads(f.read_bytes())) == ""
    finally:
        ctx.__exit__(None, None, None)


def test_error_page_that_keeps_coming_is_raised_as_a_server_error(tmp_path, monkeypatch):
    client, sent, ctx = _client(tmp_path, monkeypatch, [ERROR_PAGE])
    try:
        with pytest.raises(cu.SkyServerError, match="403"):
            client._request("GET", "https://skyserver.sdss.org/x", params={"cmd": "SELECT 1"}, cache=True)
        assert len(sent) == 1 + len(cu.SKYSERVER_RETRY_WAITS_S)
        assert not list(Path(client.cache_location).glob("*.pickle"))
    finally:
        ctx.__exit__(None, None, None)


def test_line_queries_stay_under_the_get_limit():
    """An 80-id query of 19-20 digit BOSS ids passed IIS's 2,048-character
    query string and answered 404: the EW errors (2.53.0) and Dn4000 were lost."""
    from urllib.parse import quote_plus

    import sdss_spectroscopy as s

    ids = [str(10**19 + i) for i in range(300)] + [str(10**17 + i) for i in range(300)]
    for tpl in (s.PORT_SQL, s.MPA_SQL, s._port_sql(s.LINES_NO_ERR), s._mpa_sql(s.LINES_NO_ERR)):
        chunks = s._chunks(tpl, ids)
        assert [i for c in chunks for i in c] == ids
        for c in chunks:
            assert len(quote_plus(tpl.format(ids=",".join(c)))) <= s.MAX_ENCODED_SQL
        assert len(chunks[0]) < 80  # 20-digit ids: fewer than the old 80 per query
    assert s._chunks(s.PORT_SQL, []) == []


def test_a_404_page_is_not_asked_again(tmp_path, monkeypatch):
    page = ERROR_PAGE.replace("403 - Forbidden: Access is denied.", "404 - File or directory not found.")
    client, sent, ctx = _client(tmp_path, monkeypatch, [page])
    try:
        with pytest.raises(cu.SkyServerError, match="404"):
            client._request("GET", "https://skyserver.sdss.org/x", params={"cmd": "SELECT 1"}, cache=True)
        assert len(sent) == 1
    finally:
        ctx.__exit__(None, None, None)
