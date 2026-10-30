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
