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
def no_pause(monkeypatch):
    monkeypatch.setattr(throttle, "pause", lambda: 0.0)
    throttle._preferred.update(host=None, until=0.0)


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

    r = throttle._with_mirrors(lambda self, m, url, *a, **k: V())(None, "POST", "https://vizier.cds.unistra.fr/viz-bin/votable")
    assert "<TABLE" not in r.text


def test_404_from_strasbourg_moves_to_a_mirror():
    # 2026-11-11: Strasbourg answered 404 to every viz-bin/votable query (2.51.0)
    seen = []
    req = throttle._with_mirrors(_send({"vizier.cds.unistra.fr": 404}, seen))
    r = req(None, "GET", "https://vizier.cds.unistra.fr/viz-bin/votable?-source=II/328/allwise")
    assert r.status_code == 200 and "vizier.cfa.harvard.edu" in seen[-1]
