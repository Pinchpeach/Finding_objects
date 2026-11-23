"""Independent DESI Legacy Surveys DR10 cone-search collector.

Uses the NOIRLab Astro Data Lab TAP service and the combined ls_dr10.tractor
catalog (DR10 South + DR9 North).  No classification/truth labels are queried.

Second path (2.57.0): the Legacy Surveys viewer's catalogue service
(``https://www.legacysurvey.org/viewer/ls-dr10/cat.fits?ralo=&rahi=&declo=&dechi=``,
hosted at NERSC; the URL formats are documented at ``/viewer/urls``) serves the
same Tractor rows.  Checked on NGC 4522 (0.5', 28 rows) and COSMOS (see
WORK_REPORT_2026-11-23b.md): the same ``ls_id`` set, and every column of the
TAP query equal (``ls_id`` = release * 2**40 + brickid * 2**20 + objid, and the
viewer's ``dchisq`` array = dchisq_1..5), for the DR10 South release (10000) as
for the DR9 North one (9011).  The Data Lab TAP stalled for 300 s in the first
COSMOS search of 2026-11-23 (270 objects instead of 3,582 in the result), and
a TAP outage on 2026-11-17 made every run wait 246-300 s.  The viewer is
asked in addition (request hedging, Dean & Barroso 2013, CACM 56, 74: a second
request after the time a healthy answer takes, the first answer wins) when the
Data Lab has not answered within HEDGE_DELAY_S or an attempt failed; a healthy
day sends it nothing.  It is a visualisation server, not a TAP service: only
cones up to MAX_VIEWER_RADIUS_ARCMIN (a 30' cone is 688 MB and 88 s) and
not near a pole.
"""

from pathlib import Path
import pandas as pd

import sys

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import throttle  # noqa: E402

throttle.install()  # 3-5 s before every archive request (2.33.0)

CATALOG = "DESI Legacy Surveys DR10"
TAP_URL = "https://datalab.noirlab.edu/tap"
TABLE = "ls_dr10.tractor"


# The Data Lab TAP service intermittently stalls for minutes and then
# errors; short bounded attempts recover far more often than one long wait.
ATTEMPT_BUDGET_S = 80.0
ATTEMPTS = 3
# After a recent failure (controller._budget, 2.55.0): one attempt, so a
# re-run during a Data Lab outage waits ~90 s, not 3 x 80 s.
RETRY_BUDGET_S = 90.0


# pyvo sends requests without a socket timeout, so a stalled Data Lab call
# blocked its (abandoned) thread forever and threads piled up over a long
# app session.  One shared session with a default timeout (connect, read)
# bounds every attempt and reuses connections (2.19.0).
HTTP_TIMEOUT_S = (15.0, ATTEMPT_BUDGET_S)
_SERVICE = None

# ---- second path: the Legacy Surveys viewer catalogue (2.57.0) -----------------
VIEWER_URL = "https://www.legacysurvey.org/viewer/{layer}/cat.fits"
VIEWER_LAYER = "ls-dr10"  # DR10 South; the same layer returns the DR9 North rows (release 9011) in the North
# A healthy Data Lab cone takes 5-16 s (controller.py); 30 s is about twice that.
HEDGE_DELAY_S = 30.0
VIEWER_TIMEOUT_S = (15.0, 90.0)  # connect, read
# 10' = 31,845 rows, 78 MB, 14.5 s; 30' = 281,328 rows, 688 MB, 88 s (2026-11-23).
MAX_VIEWER_RADIUS_ARCMIN = 10.0
HEDGE_STATUS = "viewer_fallback"  # legacy_query_status; archive_cache keeps such a result one day
# The columns of the TAP query below, in its order (a test keeps the two in step).
TAP_COLUMNS = (
    "ls_id ra dec type release brickid objid ra_ivar dec_ivar ref_epoch "
    "flux_g flux_r flux_i flux_z flux_ivar_g flux_ivar_r flux_ivar_i flux_ivar_z "
    "mw_transmission_g mw_transmission_r mw_transmission_i mw_transmission_z "
    "nobs_g nobs_r nobs_i nobs_z maskbits flux_w1 flux_w2 flux_ivar_w1 flux_ivar_w2 "
    "mw_transmission_w1 mw_transmission_w2 sersic shape_r shape_r_ivar "
    "dchisq_1 dchisq_2 dchisq_3 dchisq_4 dchisq_5 fiberflux_r fracflux_g fracflux_r fracflux_z"
).split()


def _service():
    global _SERVICE
    if _SERVICE is None:
        import pyvo
        import requests

        class _TimeoutSession(requests.Session):
            def request(self, *args, **kwargs):
                kwargs.setdefault("timeout", HTTP_TIMEOUT_S)
                return super().request(*args, **kwargs)

        _SERVICE = pyvo.dal.TAPService(TAP_URL, session=_TimeoutSession())
    return _SERVICE


class TapTimeout(RuntimeError):
    """Every attempt ran out of time (as opposed to a rejected query)."""


def _query_with_retries(run, hedge=None):
    """Result of ``run()`` (the Data Lab TAP), in up to ATTEMPTS attempts of
    ATTEMPT_BUDGET_S each.  ``hedge`` (2.57.0): a second path to the same rows,
    started once, in its own thread, when an attempt fails or the first one has
    not answered within HEDGE_DELAY_S; the first answer of either is returned
    (the TAP's when both are there)."""
    import threading, time

    hedged = {}  # {"thread", "value", "error"} once started

    def start_hedge(why):
        if hedge is None or hedged:
            return
        hedged["thread"] = threading.Thread(target=_box_target(hedge, hedged), daemon=True)
        hedged["thread"].start()
        print(f"[desi_legacy] Data Lab TAP {why}: asking the Legacy Surveys viewer catalogue as well", flush=True)

    def hedge_value():
        return hedged.get("value")

    last = None
    for attempt in range(ATTEMPTS):
        box = {}
        t0 = time.monotonic()
        t = threading.Thread(target=_box_target(run, box), daemon=True)
        t.start()
        while t.is_alive() and time.monotonic() - t0 < ATTEMPT_BUDGET_S:
            t.join(0.25)
            if hedge_value() is not None and "value" not in box:
                return hedge_value()
            if time.monotonic() - t0 >= HEDGE_DELAY_S:
                start_hedge(f"has not answered in {HEDGE_DELAY_S:.0f} s")
        if "value" in box:
            return box["value"]
        last = box.get("error") or TimeoutError(f"Data Lab TAP exceeded {ATTEMPT_BUDGET_S:.0f} s")
        start_hedge("attempt failed")
        if hedge_value() is not None:
            return hedge_value()
        if attempt + 1 < ATTEMPTS:
            time.sleep(2.0 * (attempt + 1))
    if hedged.get("thread") is not None:  # the viewer may still be on its way
        hedged["thread"].join(VIEWER_TIMEOUT_S[1] + VIEWER_TIMEOUT_S[0])
        if hedge_value() is not None:
            return hedge_value()
    err = TapTimeout if isinstance(last, TimeoutError) else RuntimeError
    raise err(f"Legacy Surveys TAP failed after {ATTEMPTS} attempts: {last!r}")


def _box_target(fn, box):
    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # reported by the caller
            box["error"] = exc

    return target


def viewer_usable(ra: float, dec: float, radius_arcmin: float) -> bool:
    """The viewer catalogue is a second path for this cone (small, away from a pole)."""
    return 0 < float(radius_arcmin) <= MAX_VIEWER_RADIUS_ARCMIN and abs(float(dec)) + float(radius_arcmin) / 60.0 < 89.0


def viewer_boxes(ra: float, dec: float, radius_arcmin: float) -> list[tuple[float, float, float, float]]:
    """(ralo, rahi, declo, dechi) boxes in degrees that cover the cone; two when it crosses RA = 0/360
    (the viewer's answer for a box that wraps was not reliable: 2026-11-23, 20 s and a partial table)."""
    import math

    r = float(radius_arcmin) / 60.0
    dra = math.degrees(math.asin(min(1.0, math.sin(math.radians(r)) / math.cos(math.radians(dec)))))
    lo, hi = float(ra) - dra, float(ra) + dra
    dlo, dhi = float(dec) - r, float(dec) + r
    if lo < 0.0:
        return [(lo + 360.0, 360.0, dlo, dhi), (0.0, hi, dlo, dhi)]
    if hi > 360.0:
        return [(lo, 360.0, dlo, dhi), (0.0, hi - 360.0, dlo, dhi)]
    return [(lo, hi, dlo, dhi)]


def _viewer_fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    """The Tractor rows of the cone from the viewer catalogue, as the TAP query returns them.

    Same columns in the same order (TAP_COLUMNS), the primary (non-duplicate) rows inside the
    cone, ``legacy_query_status`` = HEDGE_STATUS.  A box without catalogue sources is answered
    with a one-line text, i.e. an empty table (outside the footprint: the Galactic-plane field)."""
    import io

    import numpy as np
    import requests
    from astropy.table import Table

    parts = []
    for ralo, rahi, declo, dechi in viewer_boxes(ra, dec, radius_arcmin):
        resp = requests.get(
            VIEWER_URL.format(layer=VIEWER_LAYER),
            params={"ralo": f"{ralo:.8f}", "rahi": f"{rahi:.8f}", "declo": f"{declo:.8f}", "dechi": f"{dechi:.8f}"},
            timeout=VIEWER_TIMEOUT_S,
        )
        resp.raise_for_status()
        if resp.content[:6] != b"SIMPLE":  # "No catalog sources in layer and RA,Dec box"
            if b"No catalog sources" in resp.content[:200]:
                continue
            raise RuntimeError(f"Legacy Surveys viewer: not a FITS table: {resp.content[:100]!r}")
        tab = Table.read(io.BytesIO(resp.content), format="fits")

        def col(name):  # FITS is big-endian; pandas needs native byte order
            a = np.asarray(tab[name])
            return a.astype(a.dtype.newbyteorder("="))

        data = {}
        for name in TAP_COLUMNS:
            if name == "ls_id":
                data[name] = (
                    col("release").astype(np.int64) * 2**40 + col("brickid").astype(np.int64) * 2**20
                ) + col("objid").astype(np.int64)
            elif name.startswith("dchisq_"):
                data[name] = col("dchisq")[:, int(name[-1]) - 1]
            elif name == "type":
                data[name] = np.char.strip(np.char.decode(col("type").astype("S"), "ascii"))
            else:
                data[name] = col(name)
        df = pd.DataFrame(data)
        keep = col("brick_primary").astype(bool) if "brick_primary" in tab.colnames else np.ones(len(df), bool)
        parts.append(df[keep])
    if not parts:
        return pd.DataFrame(columns=list(TAP_COLUMNS) + ["legacy_query_status"])
    df = pd.concat(parts, ignore_index=True).drop_duplicates("ls_id", keep="last")
    # the cone (Q3C_RADIAL_QUERY on the sphere), not the box
    a, d = np.radians(df.ra.to_numpy(float)), np.radians(df.dec.to_numpy(float))
    a0, d0 = np.radians(float(ra)), np.radians(float(dec))
    h = np.sin((d - d0) / 2) ** 2 + np.cos(d0) * np.cos(d) * np.sin((a - a0) / 2) ** 2
    sep_arcmin = np.degrees(2 * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))) * 60.0
    df = df[sep_arcmin <= float(radius_arcmin)].reset_index(drop=True)
    df["legacy_query_status"] = HEDGE_STATUS
    return df


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    import pyvo

    radius_deg = float(radius_arcmin) / 60.0
    # Keep the feature set compact and purely photometric/morphological.  In
    # particular, do not join spectroscopy or any truth/classification table.
    # W1/W2 are unWISE forced photometry at the optical positions (Dey+2019),
    # far deeper than AllWISE; quasars' mid-IR excess separates them from
    # stars where astrometry is unavailable (Chaussidon+2023).  The Tractor
    # Sersic index and half-light radius give the galaxy light profile.
    # ra_ivar/dec_ivar (1/deg^2) and ref_epoch give the per-source position
    # error and, for Gaia-matched stars, the epoch of the position (Dey+2019
    # sec. 8; LS DR10 catalogue schema) -- used by the association (2.16.0).
    # dchisq_1..5 are the chi^2 improvements of the PSF, REX, DEV, EXP and SER
    # models over no source (Dey+2019 sec. 6); the REX-PSF difference and the
    # half-light-radius significance shape_r*sqrt(shape_r_ivar) measure how
    # extended a faint source is beyond the discrete TYPE (Liu et al. 2025,
    # PASP 137, 084501; Chaussidon et al. 2023, ApJ 944, 107).  fracflux_*
    # (flux share of neighbours) and fiberflux_r flag blended fits (2.44.0).
    extra = ", ra_ivar, dec_ivar, ref_epoch"
    query = f"""
        SELECT ls_id, ra, dec, type, release, brickid, objid{{extra}},
               flux_g, flux_r, flux_i, flux_z,
               flux_ivar_g, flux_ivar_r, flux_ivar_i, flux_ivar_z,
               mw_transmission_g, mw_transmission_r,
               mw_transmission_i, mw_transmission_z,
               nobs_g, nobs_r, nobs_i, nobs_z, maskbits,
               flux_w1, flux_w2, flux_ivar_w1, flux_ivar_w2,
               mw_transmission_w1, mw_transmission_w2,
               sersic, shape_r, shape_r_ivar,
               dchisq_1, dchisq_2, dchisq_3, dchisq_4, dchisq_5,
               fiberflux_r, fracflux_g, fracflux_r, fracflux_z
        FROM {TABLE}
        WHERE 't' = Q3C_RADIAL_QUERY(
            ra, dec, {float(ra):.10f}, {float(dec):.10f}, {radius_deg:.10f}
        )
    """
    hedge = (lambda: _viewer_fetch(ra, dec, radius_arcmin)) if viewer_usable(ra, dec, radius_arcmin) else None
    run = lambda q: _query_with_retries(lambda: _service().search(q).to_table().to_pandas(), hedge)
    try:
        df = run(query.replace("{extra}", extra))
    except TapTimeout:
        # A second round after three timed-out attempts (~250 s) cannot finish
        # inside the controller's 300 s budget (2.23.0): fail now.
        raise
    except RuntimeError:
        # The astrometric columns are optional: never lose the photometry
        # because a service rejects them.  The status column keeps this
        # result out of the archive cache (archive_cache.cacheable), so a
        # transient failure is not stored for 90 days without astrometry.
        df = run(query.replace("{extra}", ""))
        df["legacy_astrometry_query_status"] = "missing"
    if df.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    df.columns = [str(c).strip() for c in df.columns]
    if "ls_id" not in df.columns or "ra" not in df.columns or "dec" not in df.columns:
        raise KeyError("DESI Legacy TAP result missing ls_id/ra/dec")
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["ls_id"].astype("string"))
    df.insert(2, "object_name", "LS DR10 " + df["catalog_object_id"].astype("string"))
    df["ra"] = pd.to_numeric(df["ra"], errors="coerce")
    df["dec"] = pd.to_numeric(df["dec"], errors="coerce")
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)
