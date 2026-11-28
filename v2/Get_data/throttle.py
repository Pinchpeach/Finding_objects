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

Mirror memory across searches (2.60.0).  The failed-mirror memory above lived in the process: every new search
asked the unreachable mirrors again.  A cold search of a new field (2026-11-23, Strasbourg down) sent 57-60 of its
83-96 requests to VizieR, 6-7 of them to the mirrors NAO and China-VO (connection refused) and IUCAA (10 s read
timeout), ~57 s of the collectors' time per search, for every catalogue the CfA mirror lacked.  A mirror that
refused, timed out or answered a RETRY_STATUS is now also remembered in ``archive_cache`` (``note_source``,
V2_FAILURE_MEMORY_S, 600 s, shared by the processes through a file) and tried last by every later search until
it answers again.  Only the order changes: no mirror is ever skipped.

Empty answer of a mirror that holds the catalogue (2.60.2).  The confirmation above ("empty table") is not what
every mirror answers: CfA answers a cone without rows with no <TABLE> also without the mini form, for tables it
holds (``J/ApJS/256/43/table10`` and ``table12``: an all-sky one-row request returns a row on CfA).  The answer was
taken for "this mirror lacks the catalogue" and the request went on through NAO, IUCAA and China-VO (refused or 10 s
time-outs) to IDIA, which needs 8-17 s per request: 150 s for the four AGB tables of an empty cone.  A "no table"
confirmation is now settled by one more request, the existence probe: the catalogue without a cone, one row.  A row
means the mirror holds the catalogue, so the empty cone is accepted; no table means it lacks it (CfA lacks
``VIII/92/first14``) and the next mirror is asked.  A mirror that answers no table to everything (2.47.0) still fails
the probe.  "Holds" is remembered for the failure memory, "lacks" for V2_CATALOG_MEMORY_S.

Mirror without the catalogue (2.60.2).  A mirror that lacks a catalogue answers a table-less VOTable to the
cone and, asked again without the mini form, "no table" (the 2.54.0 confirmation).  A cold search paid for it
for every catalogue the CfA mirror did not hold and then for the dead mirrors (NAO, IUCAA, China-VO) before
IDIA answered: 8-13 requests and 85-110 s for the four tables of ``agb_suh2021`` (2026-11-23/24).  The pair
(mirror, catalogue) is now remembered for V2_CATALOG_MEMORY_S (86,400 s; the holdings of a mirror change
slowly) in ``archive_cache`` and the mirror is tried last for that catalogue.  Only the order changes.

A cut-off answer (2.61.6).  A mirror can answer HTTP 200 with a VOTable that stops before its closing tag (a
gateway cut a long answer: the 500-position Gaia batches of ``Classifier/collect_star_gaia.py``, run 46031822845 of
2026-11-27, astropy: "1027:862: no element found"), or break the connection during the body (``ChunkedEncodingError``).
Neither was a failure here: the 200 made the mirror the preferred one and the same cut answer came back on every
retry, four times, and ended the crossmatch.  Both are now a failure of that mirror for that request: the next mirror is
asked, the mirror is tried last for MIRROR_STICKY_S, and a request that every mirror cuts off raises
``ChunkedEncodingError`` instead of returning half a table.  ``distrust_last_mirror()`` lets a caller whose parser
rejected an answer (a body that is complete but wrong) do the same, so that its own retry starts at another mirror.

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
import re
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
# Largest multi-target request (positions) a mirror answers within its own time limit (2.62.12, WORK_REPORT_2026-11-28_vizier_batch.md).  CfA's
# gateway ends a request at 60 s with HTTP 504: the 500-position Gaia DR3 batches of the WD HR-gates run of 2026-11-28 (46108906185) waited 60.3 s
# there three times before IDIA answered, and every 504 also marked CfA as failing for MIRROR_STICKY_S, for the small cones of the other
# collectors too.  Probe run 46118073648 (``probe_vizier_batch.py``, I/355/gaiadr3, radius 12", the collector's request): CfA answered 50
# positions twice (39-40 s), 125 once in two (102.5 s; 504 at 60.1 s), 250 never (504 x2); IDIA answered every size, 50-500, at 3.4-4.6
# positions per second (500 in 87-151 s), three times CfA's rate even at 50.  So a larger request is not sent to CfA while another mirror can
# take it (CfA is asked last), and the caller's batch size is left alone: cutting the batches to CfA's 50 would make the crossmatch slower.
# A mirror not listed takes any size.  Re-measure with the probe (workflow v2_vizier_batch_probe.yml) when a mirror changes.
VIZIER_MAX_TARGETS = {"vizier.cfa.harvard.edu": 50}
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
    time can be split into requests, mirrors and their answers.  A thread a
    collector starts is named ``<collector>/<job>`` (``child_name``), so the
    requests of a collector are the lines whose name starts with it (2.60.0)."""
    if os.environ.get("V2_HTTP_LOG", "").strip() not in {"1", "true", "yes", "on"}:
        return
    print(
        f"[http] {threading.current_thread().name} {host} {outcome} {time.monotonic() - started:.2f}s",
        flush=True,
    )


def child_name(job: str) -> str:
    """Name for a thread a collector starts: ``<this thread's name>/<job>`` (V2_HTTP_LOG lines)."""
    return f"{threading.current_thread().name}/{job}"


def _paced(send, via_requests: bool = False):
    def request(*args, **kwargs):
        if getattr(_local, "inside", False):  # an outer layer already paused
            return send(*args, **kwargs)
        _local.inside = True
        _local.via_requests = via_requests
        try:
            pause()
            return send(*args, **kwargs)
        finally:
            _local.inside = False
            _local.via_requests = False

    request.__wrapped__ = send
    return request


def _logged_client(send):
    """http.client.HTTPConnection.request that writes the V2_HTTP_LOG line of a request that did not come
    through ``requests`` (astroquery's Gaia TAP client): those were not in the log before 2.60.0."""

    def request(self, method, url, *args, **kwargs):
        t0 = time.monotonic()
        try:
            return send(self, method, url, *args, **kwargs)
        finally:
            if not getattr(_local, "via_requests", False):
                _log(getattr(self, "host", "?"), f"{method} {str(url).split('?')[0][:48]} (http.client)", t0)

    request.__wrapped__ = send
    return request


def _remember(host: str, ok: bool) -> None:
    """Share the health of a VizieR mirror with the other processes (archive_cache; a failure is tried last)."""
    try:
        import archive_cache

        archive_cache.note_source(f"vizier:{host}", ok)
    except Exception:  # never fail a request over the memory
        pass


def _recently_failed() -> set:
    try:
        import archive_cache

        return {k.split(":", 1)[1] for k in archive_cache.down_keys() if k.startswith("vizier:")}
    except Exception:
        return set()


_SOURCE = re.compile(r"-source=([^\s&]+)")


def _catalog_of(url: str, data) -> str | None:
    """The VizieR catalogue a request asks for (``-source=`` in the query string or in the body)."""
    text = url.split("?", 1)[1] if "?" in url else ""
    if isinstance(data, dict):
        v = data.get("-source")
        text += f"&-source={v}" if v else ""
    elif isinstance(data, bytes):
        text += " " + data.decode(errors="replace")
    elif isinstance(data, str):
        text += " " + data
    m = _SOURCE.search(text)
    return m.group(1) if m else None


def _lacks(host: str, catalog: str | None, ok: bool = False) -> None:
    """Remember that the mirror ``host`` has no ``catalog`` (or forget it)."""
    if catalog is None:
        return
    try:
        import archive_cache

        ttl = archive_cache.catalog_memory_s()
        if ttl > 0:
            archive_cache.note_source(f"vizier-catalog:{host}|{catalog}", ok, ttl=ttl)
    except Exception:
        pass


def _lacking(catalog: str | None) -> set:
    """The mirrors remembered as not holding ``catalog``."""
    if catalog is None:
        return set()
    try:
        import archive_cache

        tail = f"|{catalog}"
        return {
            k[len("vizier-catalog:") : -len(tail)]
            for k in archive_cache.down_keys()
            if k.startswith("vizier-catalog:") and k.endswith(tail)
        }
    except Exception:
        return set()


_TARGET_LIST = re.compile(r"-c=<<====(\S+)\n(.*?)\n====\1", re.S)


def _targets(data) -> int:
    """Positions of a VizieR request: the lines of a multi-target list (``-c=<<====AstroqueryList ... ====AstroqueryList``, astroquery), else 1."""
    if isinstance(data, bytes):
        data = data.decode(errors="replace")
    if not isinstance(data, str):
        return 1
    m = _TARGET_LIST.search(data)
    return sum(1 for line in m.group(2).splitlines() if line.strip()) if m else 1


def _within_limits(hosts: list[str], targets: int) -> list[str]:
    """``hosts`` with the mirrors whose VIZIER_MAX_TARGETS is below ``targets`` moved to the end (still asked if the others fail)."""
    return sorted(hosts, key=lambda h: targets > VIZIER_MAX_TARGETS.get(h, targets))


def _vizier_order(host: str, catalog: str | None = None) -> list[str]:
    """Hosts to try for a VizieR request to ``host``: the recently working mirror first."""
    hosts = [host] + [h for h in VIZIER_HOSTS if h != host]
    now = time.monotonic()
    pref = _preferred["host"]
    if pref and now < _preferred["until"] and pref in hosts:
        hosts.remove(pref)
        hosts.insert(0, pref)
    # stable: reachable hosts keep their order, unreachable ones go last (also those another search saw failing)
    failed = _recently_failed()
    lacking = _lacking(catalog)
    return sorted(hosts, key=lambda h: (now < _unreachable.get(h, 0.0) or h in failed, h in lacking))


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


def _confirm_status(send, session, method, target, args, kwargs) -> str:
    """Ask the mirror again without the mini form: "empty table" means the catalogue is there and the cone has no
    rows; "rows" the first answer was wrong; "no table" an answer without table and without error; "not found" the
    mirror lacks the catalogue; "backend" its database failed (asked once more first); "error" / "unknown"."""
    data = _without_mini_form(kwargs.get("data"))
    if data is None:
        return "unknown"
    for attempt in range(2):
        pause()
        t0 = time.monotonic()
        try:
            resp = send(session, method, target, *args, **dict(kwargs, data=data))
        except Exception as exc:
            _log(target.split("/")[2], f"confirm {type(exc).__name__}", t0)
            return "error"
        reason = _answer_error(resp) if resp.status_code == 200 else None
        if reason is not None and _error_kind(reason) == "backend" and attempt == 0:
            _log(target.split("/")[2], f"confirm backend error, again: {reason[:60]}", t0)
            continue
        break
    if resp.status_code != 200:
        # a failed confirmation (503, 404 ...) says nothing about the cone: the next mirror is asked (PR #78 review:
        # it was "no table", and an existence probe that found the catalogue then accepted the first, empty answer)
        _log(target.split("/")[2], f"confirm {resp.status_code} error", t0)
        return "error"
    text = (resp.text or "").upper()
    if reason is not None:
        what = _error_kind(reason)
        _log(target.split("/")[2], f"confirm {resp.status_code} {what}: {reason[:60]}", t0)
        return what
    # An empty <TABLE> only: rows here mean the first answer was wrong, not
    # empty (CfA answered table-less for a Gaia DR3 cone with 349 sources,
    # practical-use probe 2026-11-15), so the next mirror is asked.
    ok = resp.status_code == 200 and "<TABLE" in text and "<TR" not in text
    what = "empty table" if ok else ("rows" if "<TR" in text else "no table")
    _log(target.split("/")[2], f"confirm {resp.status_code} {what}", t0)
    return what


def _probe_body(data):
    """The body of the existence probe: the catalogue of the request without its cone, one row, standard form."""
    if isinstance(data, bytes):
        probe = _probe_body(data.decode())
        return None if probe is None else probe.encode()
    if isinstance(data, str):
        drop = ("-c", "-out.form=", "-out.max=", "-oc.form=")
        return "\n".join([l for l in data.splitlines() if not l.startswith(drop)] + ["-out.max=1"])
    if isinstance(data, dict):
        d = {k: v for k, v in data.items() if not str(k).startswith("-c") and k not in ("-out.form", "-oc.form")}
        d["-out.max"] = 1
        return d
    return None


def _holds_probe(send, session, method, target, args, kwargs) -> str:
    """ "holds" when the mirror returns a row of the catalogue without any cone, "lacks" when the answer has no table
    (or says "not found"), "backend" when its database failed twice, "error"."""
    data = _probe_body(kwargs.get("data"))
    if data is None:
        return "unknown"
    for attempt in range(2):
        pause()
        t0 = time.monotonic()
        try:
            resp = send(session, method, target, *args, **dict(kwargs, data=data))
        except Exception as exc:
            _log(target.split("/")[2], f"probe {type(exc).__name__}", t0)
            return "error"
        reason = _answer_error(resp) if resp.status_code == 200 else None
        if reason is not None and _error_kind(reason) == "backend" and attempt == 0:
            _log(target.split("/")[2], f"probe backend error, again: {reason[:60]}", t0)
            continue
        break
    if resp.status_code != 200:
        what = "error"
    elif reason is not None and _error_kind(reason) == "backend":
        what = "backend"
    elif "<TABLE" in (resp.text or "").upper():
        what = "holds"
    else:
        what = "lacks"
    _log(target.split("/")[2], f"probe {resp.status_code} {what}", t0)
    return what


def _holds_known(host: str, catalog: str | None) -> bool:
    """True when the existence probe found the catalogue on the mirror less than the failure memory ago."""
    if catalog is None:
        return False
    try:
        import archive_cache

        return f"vizier-holds:{host}|{catalog}" in archive_cache.down_keys()
    except Exception:
        return False


def _holds_note(host: str, catalog: str | None) -> None:
    """Remember that the mirror holds the catalogue (the entry is stored like a failure: for the failure memory)."""
    if catalog is None:
        return
    try:
        import archive_cache

        archive_cache.note_source(f"vizier-holds:{host}|{catalog}", False)
    except Exception:
        pass


def _confirmed_empty(send, session, method, target, args, kwargs) -> bool:
    return _confirm_status(send, session, method, target, args, kwargs) == "empty table"


_ERROR_INFO = re.compile(r'<INFO[^>]*\bname="error"[^>]*\bvalue="([^"]*)"', re.I)


def _answer_error(resp) -> str | None:
    """The reason a VOTable carries (``<INFO name="ERROR" value="...">``), None when it has none.  CfA answers with
    HTTP 200 and no table both a database that it cannot reach ("The database is not currently reachable. -- no
    connection", 1 request in 6 on 2026-11-24) and a catalogue it does not have ("Table or Catalog not found")."""
    try:
        text = resp.text or ""
    except Exception:
        return None
    reasons = [v.strip(" -\n") for v in _ERROR_INFO.findall(text)]
    reasons = [v for v in reasons if v]
    return "; ".join(reasons) if reasons else None


def _error_kind(reason: str) -> str:
    return "not found" if re.search(r"not found", reason, re.I) else "backend"


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


def _truncated_votable(resp) -> bool:
    """A 200 answer that is a VOTable but ends before its closing ``</VOTABLE>``: cut off in transfer."""
    if getattr(resp, "status_code", None) != 200:
        return False
    try:
        body = resp.content
        if not isinstance(body, (bytes, bytearray)):
            body = (resp.text or "").encode("utf-8", "replace")
    except Exception:
        return False
    if not body:
        return False
    head = str(getattr(resp, "headers", {}).get("Content-Type", "")).lower()
    if "votable" not in head and b"<VOTABLE" not in bytes(body[:2000]).upper():
        return False  # not a VOTable (JSON, text, HTML): nothing to say about its end
    return b"</VOTABLE>" not in bytes(body[-2048:]).upper()


def last_host() -> str | None:
    """The VizieR mirror that gave this thread's last answer (None before the first)."""
    return getattr(_local, "last_host", None)


def distrust_last_mirror() -> str | None:
    """Treat the last answer of this thread as a failure of its mirror (a caller that could not read it): the mirror is
    tried last for MIRROR_STICKY_S, here and in the other processes, so the caller's retry starts at another one.
    Returns the mirror (None when there was none)."""
    host = last_host()
    if host:
        _unreachable[host] = time.monotonic() + MIRROR_STICKY_S
        _remember(host, False)
        if _preferred["host"] == host:
            _preferred.update(host=None, until=0.0)
    return host


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
        # 2.61.6 review: forget the last answer's mirror before asking, so that after a request that fails on every mirror
        # ``distrust_last_mirror`` names no mirror instead of one that answered an earlier request well
        _local.last_host = None
        catalog = _catalog_of(str(url), kwargs.get("data"))
        hosts = _within_limits(_vizier_order(parts.hostname, catalog), _targets(kwargs.get("data")))
        read = kwargs.get("timeout")
        read = read[1] if isinstance(read, tuple) else read
        kwargs["timeout"] = (CONNECT_TIMEOUT_S, read)
        last = None
        empty = None
        # 2.60.2 review: answers that say the mirror's database failed or that it lacks the catalogue are never an
        # empty cone.  When no mirror gives data they end in an error (the collector reports it) instead of being
        # returned as a table-less answer, which astroquery reads as "no rows" (the 2026-11-07 kind of silence).
        lacked = None
        cut = None  # the last answer that stopped before </VOTABLE> or broke off in transfer (2.61.6)
        retried: set = set()  # mirrors asked again after a database error of their own
        for i, host in enumerate(hosts):
            if i:
                pause()  # every retry is an archive request too
            target = urlunsplit(parts._replace(netloc=parts.netloc.replace(parts.hostname, host)))
            t0 = time.monotonic()
            try:
                resp = send(self, method, target, *args, **kwargs)
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,  # the body was cut off in transfer (2.61.6)
                requests.exceptions.ContentDecodingError,
            ) as exc:  # refused, DNS, connect/read timeout, broken body
                _log(host, type(exc).__name__, t0)
                # not connected, or no answer in the 10 s of the client (IUCAA, 2026-11-24: every request, 6 in a
                # search): the mirror is tried last for MIRROR_STICKY_S, in this process (2.60.2: a timeout too; 2.54.0
                # left it out as "a slow answer") and in the others
                _unreachable[host] = time.monotonic() + MIRROR_STICKY_S
                _remember(host, False)
                last = exc
                if isinstance(exc, (requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError)):
                    cut = exc  # the body broke off in transfer: the same "too long" signal as a cut VOTable (Codex, 2.61.6)
                continue
            if _truncated_votable(resp):  # 200, but the table stops half way: a failure of this mirror (2.61.6)
                _log(host, f"{resp.status_code} truncated", t0)
                _unreachable[host] = time.monotonic() + MIRROR_STICKY_S
                _remember(host, False)
                if _preferred["host"] == host:
                    _preferred.update(host=None, until=0.0)
                cut = last = resp
                continue
            tableless = _tableless_votable(resp)
            reason = _answer_error(resp) if tableless else None
            _log(
                host,
                f"{resp.status_code}{' tableless' if tableless else ''}{' error: ' + reason[:60] if reason else ''}",
                t0,
            )
            if resp.status_code in RETRY_STATUS or (reason is not None and _error_kind(reason) == "backend"):
                _remember(host, False)
            elif reason is None:
                _remember(host, True)  # it answered
            # the last mirror's error status is returned as the answer, unless an earlier mirror cut the table off: that
            # signal outranks it (Codex review of 4d216f9: CfA cut, the others 503 -> a 503, and the batch was never halved)
            if resp.status_code in RETRY_STATUS and (i < len(hosts) - 1 or cut is not None):
                _unreachable[host] = time.monotonic() + MIRROR_STICKY_S  # failing: tried last for a while
                last = resp
                continue
            if reason is not None:
                # The mirror's database failed (CfA, "no connection": it answers HTTP 200 with a VOTable without a
                # table) or it does not have the catalogue ("Table or Catalog not found"): neither is an empty cone.
                # A failed database is asked once more first: CfA answers in 0.1-0.5 s, the mirrors after it refuse
                # or need 8-17 s.
                if _error_kind(reason) == "backend":
                    if host not in retried:
                        retried.add(host)
                        hosts.insert(i + 1, host)  # the same mirror once more (the pause is at the top of the loop)
                        continue
                else:
                    _lacks(host, catalog)  # other searches ask this mirror last for this catalogue
                lacked = resp
                continue  # the last mirror too: an error answer is never returned as the result
            # A mirror's table-less answer is not trusted on its own (2.47.0):
            # on 2026-11-07, with Strasbourg unreachable, the CfA mirror
            # answered 200 with a VOTable holding no table for every
            # catalogue (AllWISE, 2MASS, NVSS) while IDIA returned the
            # AllWISE rows; the empty answer was accepted and made the
            # preferred mirror, so every VizieR collector of the 520
            # reference-object runs came back empty.  Such an answer is kept
            # only if no other mirror returns a table.
            if host != VIZIER_HOSTS[0] and tableless and reason is None:
                what = _confirm_status(send, self, method, target, args, kwargs)
                probe = None
                if what == "no table":
                    # an empty cone of a catalogue the mirror holds (CfA) or a mirror without the catalogue: the
                    # existence probe tells them apart (a probe done less than the failure memory ago is kept)
                    probe = (
                        "holds"
                        if _holds_known(host, catalog)
                        else _holds_probe(send, self, method, target, args, kwargs)
                    )
                    if probe == "holds":
                        _holds_note(host, catalog)
                        what = "empty table"
                    elif probe == "lacks":
                        _lacks(host, catalog)  # other searches ask this mirror last for this catalogue
                    elif probe == "backend":
                        _remember(host, False)
                elif what == "not found":
                    _lacks(host, catalog)
                elif what == "backend":
                    _remember(host, False)
                if what == "empty table":
                    _lacks(host, catalog, ok=True)  # it holds the catalogue (the cone is empty)
                elif what in ("not found", "backend") or probe in ("lacks", "backend"):
                    lacked = resp  # lacks the catalogue or its database failed: not an empty cone
                    continue
                else:
                    empty = empty or resp
                    continue
            if host != VIZIER_HOSTS[0]:
                _preferred.update(host=host, until=time.monotonic() + MIRROR_STICKY_S)
            elif _preferred["host"]:
                _preferred.update(host=None, until=0.0)
            _local.last_host = host
            return resp
        if cut is not None:
            # A mirror served the table but cut it off, and no mirror gave it whole (the others cut it too, refused, timed
            # out, lacked it or answered table-less): the request is too long for the mirrors, not absent.  That signal
            # outranks a later connection error or an empty answer, so a caller can ask again in smaller pieces
            # (Codex review of 2.61.6: CfA cut, the other five refused -> ConnectionError, and the batch was never halved;
            # the same for a body that broke off in transfer, ChunkedEncodingError / ContentDecodingError, on review of b51d74b).
            how = f"in transfer ({type(cut).__name__})" if isinstance(cut, Exception) else "before </VOTABLE>"
            raise requests.exceptions.ChunkedEncodingError(
                f"VizieR: a mirror cut off a VOTable {how} and no mirror gave it whole ({catalog or 'the table'})"
            ) from (cut if isinstance(cut, Exception) else None)
        if empty is not None:
            return empty  # a table-less answer without an error that no mirror contradicted (2.47.0)
        if lacked is not None:
            why = _answer_error(lacked) or "no table, and the mirror lacks the catalogue"
            raise RuntimeError(f"VizieR: no mirror gave {catalog or 'the table'}: {why[:160]}")
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

        requests.Session.request = _paced(_with_mirrors(requests.Session.request), via_requests=True)
        http.client.HTTPConnection.request = _paced(_logged_client(http.client.HTTPConnection.request))
        _installed = True
