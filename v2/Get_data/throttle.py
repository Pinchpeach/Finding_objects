"""Pause 3-5 s before every archive request (project rule, 2.33.0).

``install()`` wraps the two places every client used here sends a request
through: ``requests.Session.request`` (requests, astroquery, pyvo) and
``http.client.HTTPConnection.request`` (astroquery's Gaia TAP client, urllib).
A request that passes through both (urllib3 1.x) pauses once.  The pause is
per request, so the follow-up requests of one query (an async TAP job's
status polls, a column-list probe) are spaced as well.  Public archives limit
scripted clients (CDS blocks a host that sends SIMBAD more than a few queries
per second); the random jitter keeps parallel collectors out of lock-step.

VizieR mirrors (2.36.4): a VizieR request whose connection is refused,
that times out (connecting or reading), or that answers 404/500/502/503/504, is sent
again to the next official
mirror (CDS list of VizieR sites: Strasbourg, CfA, NAOJ, IUCAA, China-VO,
IDIA; same catalogues).  On 2026-10-24 the Strasbourg server refused every
connection from the validation runners for hours, and later answered so
slowly that every query ran into the 60 s read timeout; either stopped every
VizieR-backed collector.  A mirror that answered is preferred for
MIRROR_STICKY_S, then Strasbourg is tried first again.

Connect timeout (2.44.0): a VizieR request waits at most CONNECT_TIMEOUT_S
for the TCP connection (the read timeout the client asked for is kept).  On
2026-10-30 the Strasbourg server stopped accepting connections; each request
waited astroquery's full 60 s before failing over, a collector made several,
and VizieR-backed collectors took ~270 s, pushing Gaia (whose VizieR copy is
the fallback for a slow ESA TAP) past the 300 s collector budget in every
validation field.  A healthy server connects in well under a second.

Empty answers of a mirror (2.54.0): astroquery asks for ``-out.form=mini``,
whose answer to a cone without rows has no <TABLE>, like the answer of a
mirror that lacks the catalogue.  A table-less mirror answer was therefore
sent on to every other mirror (2.47.0 rule below).  On 2026-11-14/15, with
Strasbourg answering 404, each empty cone went Strasbourg -> CfA -> NAOJ and
IUCAA (10 s connect timeouts each) -> China-VO -> IDIA, ~50 s per query:
the 0-row AGB (4 tables, 201 s), Gaia SOS (3 tables, 154 s) and radio
collectors (53 s each) set a field's ~340 s collection.  The same mirror is
now asked once more without the mini form (one row): a known catalogue then
answers with an empty <TABLE>, an unknown one without (practical-use probe,
CfA and IDIA, 2026-11-15), so a confirmed empty cone is accepted at once.
A confirmation with a row means the table-less answer was wrong (CfA did
this for a Gaia DR3 cone of 349 sources): the next mirror is asked.
A mirror that refused the connection, did not connect within
CONNECT_TIMEOUT_S or answered a RETRY_STATUS is tried last for
MIRROR_STICKY_S (Strasbourg's 404 and the NAOJ / IUCAA connect timeouts were
paid again by every query).
"""

from __future__ import annotations

import http.client
import os
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
CONNECT_TIMEOUT_S = 10.0
# 500 added in 2.44.0: on 2026-10-31 the IDIA mirror, preferred after
# Strasbourg failed, answered 500 to every query for hours (48 fields lost
# every VizieR catalogue).
# 404 (2.51.0): on 2026-11-11 Strasbourg answered 404 Not Found to every
# viz-bin/votable query all day, while the mirrors served the catalogues; an
# existing catalogue with no rows in the cone answers 200 with an empty
# table, so a 404 is never a valid VizieR answer.  Every validation run of
# that day lost AllWISE and 2MASS (allwise_rows = 0 in assoc_stats.csv).
RETRY_STATUS = {404, 500, 502, 503, 504}
_preferred = {"host": None, "until": 0.0}
_unreachable: dict[str, float] = {}  # host -> monotonic time until which it is tried last

_local = threading.local()
_lock = threading.Lock()
_installed = False


def pause() -> float:
    """Sleep for a random 3-5 s; the seconds slept."""
    s = random.uniform(MIN_PAUSE_S, MAX_PAUSE_S)
    time.sleep(s)
    return s


def _log(host, outcome, started) -> None:
    """One line per archive request when V2_HTTP_LOG=1 (2.54.0): the thread
    name is the collector (controller._run_bounded), so a slow collector's
    time can be split into requests, mirrors and their answers."""
    if os.environ.get("V2_HTTP_LOG", "").strip() not in {"1", "true", "yes", "on"}:
        return
    print(
        f"[http] {threading.current_thread().name} {host} {outcome} {time.monotonic() - started:.2f}s",
        flush=True,
    )


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
    now = time.monotonic()
    pref = _preferred["host"]
    if pref and now < _preferred["until"] and pref in hosts:
        hosts.remove(pref)
        hosts.insert(0, pref)
    # stable: reachable hosts keep their order, unreachable ones go last
    return sorted(hosts, key=lambda h: now < _unreachable.get(h, 0.0))


def _without_mini_form(data):
    """The request body asking for one row in the standard VOTable form."""
    if isinstance(data, bytes):
        return _without_mini_form(data.decode()).encode()
    if isinstance(data, str):
        lines = [l for l in data.splitlines() if not l.startswith(("-out.form=", "-out.max="))]
        return "\n".join(lines + ["-out.max=1"])
    if isinstance(data, dict):
        d = {k: v for k, v in data.items() if k not in ("-out.form",)}
        d["-out.max"] = 1
        return d
    return None


def _confirmed_empty(send, session, method, target, args, kwargs) -> bool:
    """Ask the mirror again without the mini form: an empty <TABLE> means the
    catalogue is there and the cone has no rows."""
    data = _without_mini_form(kwargs.get("data"))
    if data is None:
        return False
    pause()
    t0 = time.monotonic()
    try:
        resp = send(session, method, target, *args, **dict(kwargs, data=data))
    except Exception as exc:
        _log(target.split("/")[2], f"confirm {type(exc).__name__}", t0)
        return False
    text = (resp.text or "").upper()
    # An empty <TABLE> only: rows here mean the first answer was wrong, not
    # empty (CfA answered table-less for a Gaia DR3 cone with 349 sources,
    # practical-use probe 2026-11-15), so the next mirror is asked.
    ok = resp.status_code == 200 and "<TABLE" in text and "<TR" not in text
    what = "empty table" if ok else ("rows" if "<TR" in text else "no table")
    if what == "no table":  # the server's reason, for the log
        import re

        info = re.findall(r'<INFO[^>]*name="(?:QUERY_STATUS|Error|Warning)"[^>]*>([^<]{0,160})', resp.text or "", re.I)
        what += f" {info[:2]}"
    _log(target.split("/")[2], f"confirm {resp.status_code} {what}", t0)
    return ok


def _tableless_votable(resp) -> bool:
    """A 200 VOTable answer without any <TABLE> (no rows for any catalogue)."""
    if getattr(resp, "status_code", None) != 200:
        return False
    try:
        text = resp.text or ""
    except Exception:
        return False
    head = str(getattr(resp, "headers", {}).get("Content-Type", "")).lower()
    if "votable" not in head and "<VOTABLE" not in text[:2000].upper():
        return False
    return "<TABLE" not in text.upper()


def _with_mirrors(send):
    """requests.Session.request that fails over between VizieR mirrors."""
    from urllib.parse import urlsplit, urlunsplit

    import requests

    def request(self, method, url, *args, **kwargs):
        parts = urlsplit(str(url))
        if parts.hostname not in VIZIER_HOSTS:
            t0 = time.monotonic()
            try:
                resp = send(self, method, url, *args, **kwargs)
            except Exception as exc:
                _log(parts.hostname, type(exc).__name__, t0)
                raise
            _log(parts.hostname, resp.status_code, t0)
            return resp
        hosts = _vizier_order(parts.hostname)
        read = kwargs.get("timeout")
        read = read[1] if isinstance(read, tuple) else read
        kwargs["timeout"] = (CONNECT_TIMEOUT_S, read)
        last = None
        empty = None
        for i, host in enumerate(hosts):
            if i:
                pause()  # every retry is an archive request too
            target = urlunsplit(parts._replace(netloc=parts.netloc.replace(parts.hostname, host)))
            t0 = time.monotonic()
            try:
                resp = send(self, method, target, *args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:  # refused, DNS, connect/read timeout
                _log(host, type(exc).__name__, t0)
                if isinstance(exc, requests.exceptions.ConnectionError):  # not connected (a read timeout is a slow answer)
                    _unreachable[host] = time.monotonic() + MIRROR_STICKY_S
                last = exc
                continue
            _log(host, f"{resp.status_code}{' tableless' if _tableless_votable(resp) else ''}", t0)
            if resp.status_code in RETRY_STATUS and i < len(hosts) - 1:
                _unreachable[host] = time.monotonic() + MIRROR_STICKY_S  # failing: tried last for a while
                last = resp
                continue
            # A mirror's table-less answer is not trusted on its own (2.47.0):
            # on 2026-11-07, with Strasbourg unreachable, the CfA mirror
            # answered 200 with a VOTable holding no table for every
            # catalogue (AllWISE, 2MASS, NVSS) while IDIA returned the
            # AllWISE rows; the empty answer was accepted and made the
            # preferred mirror, so every VizieR collector of the 520
            # reference-object runs came back empty.  Such an answer is kept
            # only if no other mirror returns a table.
            if host != VIZIER_HOSTS[0] and _tableless_votable(resp):
                if not _confirmed_empty(send, self, method, target, args, kwargs):
                    empty = empty or resp
                    continue
            if host != VIZIER_HOSTS[0]:
                _preferred.update(host=host, until=time.monotonic() + MIRROR_STICKY_S)
            elif _preferred["host"]:
                _preferred.update(host=None, until=0.0)
            return resp
        if empty is not None:
            return empty
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
