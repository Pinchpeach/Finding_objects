"""Pause 3-5 s before every archive request (project rule, 2.33.0).

``install()`` wraps the two places every client used here sends a request
through: ``requests.Session.request`` (requests, astroquery, pyvo) and
``http.client.HTTPConnection.request`` (astroquery's Gaia TAP client, urllib).
A request that passes through both (urllib3 1.x) pauses once.  The pause is
per request, so the follow-up requests of one query (an async TAP job's
status polls, a column-list probe) are spaced as well.  Public archives limit
scripted clients (CDS blocks a host that sends SIMBAD more than a few queries
per second); the random jitter keeps parallel collectors out of lock-step.
"""

from __future__ import annotations

import http.client
import random
import threading
import time

MIN_PAUSE_S, MAX_PAUSE_S = 3.0, 5.0

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


def install() -> None:
    """Pace every HTTP request made by this process (idempotent)."""
    global _installed
    with _lock:
        if _installed:
            return
        import requests

        requests.Session.request = _paced(requests.Session.request)
        http.client.HTTPConnection.request = _paced(http.client.HTTPConnection.request)
        _installed = True
