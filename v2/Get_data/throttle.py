"""Pause 3-5 s before every archive request (project rule, 2.33.0).

``install()`` wraps the two places every client used here sends a request
through: ``requests.Session.request`` (requests, astroquery, pyvo) and
``http.client.HTTPConnection.request`` (astroquery's Gaia TAP client, urllib).
A request that passes through both (urllib3 1.x) pauses once.  The pause is
per request, so the follow-up requests of one query (an async TAP job's
status polls, a column-list probe) are spaced as well.  Public archives limit
scripted clients (CDS blocks a host that sends SIMBAD more than a few queries
per second); the random jitter keeps parallel collectors out of lock-step.

VizieR mirrors (2.36.4): a VizieR request whose connection is refused or
times out, or that answers 502/503/504, is sent again to the next official
mirror (CDS list of VizieR sites: Strasbourg, CfA, NAOJ, IUCAA, China-VO,
IDIA; same catalogues).  On 2026-10-24 the Strasbourg server refused every
connection from the validation runners for hours, which stopped every
VizieR-backed collector.  A mirror that answered is preferred for
MIRROR_STICKY_S, then Strasbourg is tried first again.
"""

from __future__ import annotations

import http.client
import random
import threading
import time

MIN_PAUSE_S, MAX_PAUSE_S = 3.0, 5.0
VIZIER_HOSTS = (
    "vizier.cds.unistra.fr",
    "vizier.cfa.harvard.edu",
    "vizier.nao.ac.jp",
    "vizier.iucaa.in",
    "vizier.china-vo.org",
    "vizier.idia.ac.za",
)
MIRROR_STICKY_S = 600.0
RETRY_STATUS = {502, 503, 504}
_preferred = {"host": None, "until": 0.0}

_local = threading.local()
_lock = threading.Lock()
_installed = False


def pause() -> float:
    """Sleep for a random 3-5 s; the seconds slept."""
    s = random.uniform(MIN_PAUSE_S, MAX_PAUSE_S)
    time.sleep(s)
    return s


def _paced(send):
    def request(*args, **kwargs):
        if getattr(_local, "inside", False):  # an outer layer already paused
            return send(*args, **kwargs)
        _local.inside = True
        try:
            pause()
            return send(*args, **kwargs)
        finally:
            _local.inside = False

    request.__wrapped__ = send
    return request


def _vizier_order(host: str) -> list[str]:
    """Hosts to try for a VizieR request to ``host``: the recently working mirror first."""
    hosts = [host] + [h for h in VIZIER_HOSTS if h != host]
    pref = _preferred["host"]
    if pref and time.monotonic() < _preferred["until"] and pref in hosts:
        hosts.remove(pref)
        hosts.insert(0, pref)
    return hosts


def _with_mirrors(send):
    """requests.Session.request that fails over between VizieR mirrors."""
    from urllib.parse import urlsplit, urlunsplit

    import requests

    def request(self, method, url, *args, **kwargs):
        parts = urlsplit(str(url))
        if parts.hostname not in VIZIER_HOSTS:
            return send(self, method, url, *args, **kwargs)
        hosts = _vizier_order(parts.hostname)
        last = None
        for i, host in enumerate(hosts):
            if i:
                pause()  # every retry is an archive request too
            target = urlunsplit(parts._replace(netloc=parts.netloc.replace(parts.hostname, host)))
            try:
                resp = send(self, method, target, *args, **kwargs)
            except requests.exceptions.ConnectionError as exc:  # refused, DNS, connect timeout
                last = exc
                continue
            if resp.status_code in RETRY_STATUS and i < len(hosts) - 1:
                last = resp
                continue
            if host != VIZIER_HOSTS[0]:
                _preferred.update(host=host, until=time.monotonic() + MIRROR_STICKY_S)
            elif _preferred["host"]:
                _preferred.update(host=None, until=0.0)
            return resp
        if isinstance(last, Exception):
            raise last
        return last

    request.__wrapped__ = send
    return request


def install() -> None:
    """Pace every HTTP request made by this process (idempotent)."""
    global _installed
    with _lock:
        if _installed:
            return
        import requests

        requests.Session.request = _paced(_with_mirrors(requests.Session.request))
        http.client.HTTPConnection.request = _paced(http.client.HTTPConnection.request)
        _installed = True
