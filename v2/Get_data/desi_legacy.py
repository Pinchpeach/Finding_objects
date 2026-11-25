"""Independent DESI Legacy Surveys DR10 cone-search collector.

Uses the NOIRLab Astro Data Lab TAP service and the combined ls_dr10.tractor
catalog (DR10 South + DR9 North).  No classification/truth labels are queried.

Second path (2.57.0): the Legacy Surveys viewer's catalogue service
(``https://www.legacysurvey.org/viewer/ls-dr10/cat.fits?ralo=&rahi=&declo=&dechi=``,
hosted at NERSC; the URL formats are documented at ``/viewer/urls``) serves the
same Tractor rows.  Checked on NGC 4522 (0.5', 28 rows) and COSMOS (see
WORK_REPORT_2026-11-23b.md): the same ``ls_id`` set, and every column of the
TAP query equal (``ls_id`` = release * 2**40 + brickid * 2**20 + objid, and the
viewer's ``dchisq`` array = dchisq_1..5), for the DR10 South release (10000).
The 2.57.0 review compared both paths with the live TAP
(``benchmark/compare_ls_viewer.py``): identical in DR10 South (NGC 4522 2',
417 rows; Dec 32.30 in the NGC just south of the north/south split, 436; the
SGC at Dec 33.5, 154), but not in the DR9 North part of ``ls_dr10`` (north
Galactic cap, Dec >= 32.375; 2026-11-23, three cones, 178-219 rows each).
There the Data Lab keeps the DR9 ``ls_id`` (brickid shifted by 16, not 20;
fixed below, the ids now match), but the values differ: the TAP has i-band
columns the viewer's DR9 North table lacks (or fills with 0 near the split),
``fracflux_*`` differ (up to 3 % relative near the split, a zero against a
value deep in the north), and fluxes by up to 3e-4 relative.  So the viewer
is asked only for cones wholly in DR10 South (``viewer_usable``).  2.60.10: cones of up to 20' are asked in
tiles (``viewer_tiles``; 12' = one request of ~125 MB, 20' = four of ~78 MB) -- see WORK_REPORT_2026-11-25e.md.  The Data Lab TAP stalled for 300 s in the first
COSMOS search of 2026-11-23 (270 objects instead of 3,582 in the result), and
a TAP outage on 2026-11-17 made every run wait 246-300 s.  The viewer is
asked in addition (request hedging, Dean & Barroso 2013, CACM 56, 74: a second
request after the time a healthy answer takes, the first answer wins) when the
Data Lab has not answered within HEDGE_DELAY_S or an attempt failed; a healthy
day sends it nothing.  It is a visualisation server, not a TAP service: only
cones up to MAX_VIEWER_RADIUS_ARCMIN (a 30' cone in one box is 688 MB and 88 s), wholly
in DR10 South, and not near a pole.
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
VIEWER_LAYER = "ls-dr10"  # DR10 South rows below the split (the layer also serves DR9 North, not used: see above)
# A healthy Data Lab cone takes 5-16 s (controller.py); 30 s is about twice that.
HEDGE_DELAY_S = 30.0
VIEWER_TIMEOUT_S = (15.0, 90.0)  # connect, read
# 10' = 31,845 rows, 78 MB, 14.5 s; 30' = 281,328 rows, 688 MB, 88 s (2026-11-23, 2.57.0).  2.60.10: cones up to
# 20' in tiles (see viewer_tiles): a request is at most VIEWER_TILE_ARCMIN on a side (<= ~25' x 25' = 625 arcmin^2,
# about 1.6 times the 10' cone's box that was measured, so ~125 MB and ~25 s at COSMOS density), at most
# VIEWER_MAX_TILES requests, so a 20' cone is 4 requests of 20' x 20' (the measured 10' size), ~310 MB, ~75 s.
MAX_VIEWER_RADIUS_ARCMIN = 20.0
VIEWER_TILE_ARCMIN = 25.0
# The viewer drops the rows within about one pixel of a box edge (measured 2026-11-25 on the 24' COSMOS box: the 3 rows
# of the cone within 0.6'' of the western edge, 0.00017 deg = box width / 2300, were missing, while the same edge in a
# 0.01 deg box returned them).  Every tile is therefore asked with a margin on all four sides, max(VIEWER_MARGIN_ARCSEC,
# VIEWER_MARGIN_FRACTION x its side): three times the loss measured, and the margins of neighbouring tiles overlap, so
# no row of the cone falls between two boxes.  The cone cut that follows removes the rows the margin brought in.
VIEWER_MARGIN_ARCSEC = 3.0
VIEWER_MARGIN_FRACTION = 0.005
VIEWER_MAX_TILES = 4
VIEWER_MAX_BYTES = 250_000_000  # one answer; a denser field than COSMOS (a Galactic-plane box) is not read to the end
VIEWER_BUDGET_S = 170.0  # all tiles of one cone
VIEWER_JOIN_S = 180.0  # how long a failed TAP waits for the viewer thread (it started a few seconds into the failure)
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


def hedge_delay_s(radius_arcmin: float) -> float:
    """How long a healthy Data Lab answer can take before the viewer is asked as well (2.60.10).  Up to 10' it is
    HEDGE_DELAY_S, about twice the 5-16 s of a 10' cone (2.57.0).  The Data Lab's time grows with the cone's area, and
    a 12' cone was measured at 11-43 s on 2026-11-25 (COSMOS the slowest), so a larger cone waits 1.5 x 30 s x
    (r / 10')^2 (12': 65 s), never longer than one attempt (ATTEMPT_BUDGET_S): none of the nine 12' cones of the
    measurement would have started the viewer, a failed attempt (HTTP 502 at once) still does."""
    r = float(radius_arcmin)
    if r <= 10.0:
        return HEDGE_DELAY_S
    return min(ATTEMPT_BUDGET_S, HEDGE_DELAY_S * 1.5 * (r / 10.0) ** 2)


def retry_budget_s(ra: float, dec: float, radius_arcmin: float) -> float:
    """Budget of a retry, or of a search after a remembered failure (``controller._budget``; 2.60.10 review, Codex).

    RETRY_BUDGET_S (90 s) keeps a retry during an outage from becoming another 5-minute wait, and it is enough for a
    cone of up to 10' (a viewer box answers in ~15 s).  A larger cone that the viewer serves needs the hedge delay of
    the cone plus all its tiles (20': up to 80 s + 170 s; 101 s measured for the four tiles): with 90 s a working
    viewer could never finish during a Data Lab outage.  Cones the viewer does not serve keep 90 s."""
    r = float(radius_arcmin)
    if r <= 10.0 or not viewer_usable(ra, dec, r):
        return RETRY_BUDGET_S
    return max(RETRY_BUDGET_S, hedge_delay_s(r) + VIEWER_BUDGET_S + 10.0)


def _query_with_retries(run, hedge=None, attempts=None, attempt_budget_s=None, hedge_delay=None):
    """Result of ``run()`` (the Data Lab TAP), in up to ATTEMPTS attempts of
    ATTEMPT_BUDGET_S each.  ``hedge`` (2.57.0): a second path to the same rows,
    started once, in its own thread, when an attempt fails or the first one has
    not answered within HEDGE_DELAY_S; the first answer of either is returned
    (the TAP's when both are there)."""
    import threading, time

    delay = HEDGE_DELAY_S if hedge_delay is None else hedge_delay
    attempts = ATTEMPTS if attempts is None else attempts  # a caller may wait less (desi_fastspec.py, 2.59.0)
    budget = ATTEMPT_BUDGET_S if attempt_budget_s is None else attempt_budget_s
    hedged = {}  # {"thread", "value", "error"} once started

    def start_hedge(why):
        if hedge is None or hedged:
            return
        hedged["thread"] = threading.Thread(
            target=_box_target(hedge, hedged), daemon=True, name=throttle.child_name("viewer")
        )
        hedged["thread"].start()
        print(f"[desi_legacy] Data Lab TAP {why}: asking the Legacy Surveys viewer catalogue as well", flush=True)

    def hedge_value():
        return hedged.get("value")

    last = None
    for attempt in range(attempts):
        box = {}
        t0 = time.monotonic()
        t = threading.Thread(target=_box_target(run, box), daemon=True, name=throttle.child_name("tap"))
        t.start()
        while t.is_alive() and time.monotonic() - t0 < budget:
            t.join(0.25)
            if hedge_value() is not None and "value" not in box:
                return hedge_value()
            if time.monotonic() - t0 >= delay:
                start_hedge(f"has not answered in {delay:.0f} s")
        if "value" in box:
            return box["value"]
        last = box.get("error") or TimeoutError(f"Data Lab TAP exceeded {budget:.0f} s")
        start_hedge("attempt failed")
        if hedge_value() is not None:
            return hedge_value()
        if attempt + 1 < attempts:
            time.sleep(2.0 * (attempt + 1))
    if hedged.get("thread") is not None:  # the viewer may still be on its way
        hedged["thread"].join(VIEWER_JOIN_S)
        if hedge_value() is not None:
            return hedge_value()
    err = TapTimeout if isinstance(last, TimeoutError) else RuntimeError
    raise err(f"Legacy Surveys TAP failed after {attempts} attempts: {last!r}")


def _box_target(fn, box):
    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # reported by the caller
            box["error"] = exc

    return target


# ls_dr10.tractor takes the DR9 North (BASS + MzLS) rows in the north Galactic cap at Dec >= 32.375 deg
# and the DR10 South (DECam) rows elsewhere: the Legacy Surveys north/south split (DR9/DR10 documentation,
# "(dec >= 32.375) & (b > 0)" is north).  The viewer path was found identical to the TAP only in DR10 South
# (module docstring: in DR9 North the i band, fracflux_* and fluxes differ).
NORTH_DEC_SPLIT = 32.375


def _wholly_south(ra: float, dec: float, r_deg: float) -> bool:
    """The whole cone is in the DR10 South part of ls_dr10 (south of the split, or in the south Galactic cap)."""
    if float(dec) + r_deg < NORTH_DEC_SPLIT:
        return True
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    return float(SkyCoord(float(ra) * u.deg, float(dec) * u.deg).galactic.b.deg) < -r_deg


def viewer_usable(ra: float, dec: float, radius_arcmin: float) -> bool:
    """The viewer catalogue is a second path for this cone: not larger than MAX_VIEWER_RADIUS_ARCMIN (at most
    VIEWER_MAX_TILES requests), away from a pole, and wholly in DR10 South (2.57.0 review: in the DR9 North part
    the viewer rows differ from the TAP's, see the module docstring)."""
    r = float(radius_arcmin)
    if not (0 < r <= MAX_VIEWER_RADIUS_ARCMIN) or abs(float(dec)) + r / 60.0 >= 89.0:
        return False
    return _wholly_south(ra, dec, r / 60.0) and len(viewer_tiles(ra, dec, r)) <= VIEWER_MAX_TILES


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


def _angle_diff(a: float, b: float) -> float:
    """a - b in degrees, in [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def _tile_reaches_cone(tile, ra: float, dec: float, r_deg: float) -> bool:
    """The (ralo, rahi, declo, dechi) box has a point within r_deg of the cone centre (clamping the centre into the
    box; a margin of 0.5' keeps a tile that the clamp over-estimates, which only costs a request, never a row)."""
    import math

    ralo, rahi, declo, dechi = tile
    d_lo, d_hi = _angle_diff(ralo, ra), _angle_diff(rahi, ra)
    dra = 0.0 if d_lo <= 0.0 <= d_hi else (d_lo if d_lo > 0 else d_hi)
    nd = min(max(float(dec), declo), dechi)
    n_ra = float(ra) + dra
    h = math.sin(math.radians(nd - dec) / 2) ** 2 + math.cos(math.radians(dec)) * math.cos(math.radians(nd)) * (
        math.sin(math.radians(n_ra - ra) / 2) ** 2
    )
    sep = math.degrees(2 * math.asin(min(1.0, math.sqrt(max(0.0, h)))))
    return sep <= r_deg + 0.5 / 60.0


def viewer_tiles(ra: float, dec: float, radius_arcmin: float) -> list[tuple[float, float, float, float]]:
    """The requests that cover the cone (2.60.10): the boxes of viewer_boxes, each cut into n x m tiles whose sides
    are at most VIEWER_TILE_ARCMIN on the sky, every tile widened by its margin (see VIEWER_MARGIN_ARCSEC) and the
    tiles that do not reach the cone dropped (the corner tiles of a large cone).  A cone of up to 12.5' is one
    request, a 20' cone four.  Rows in the overlap of two tiles come twice and are removed by ls_id; the tiles
    together cover the box with a margin, so a cone's rows are neither lost nor doubled."""
    import math

    r_deg = float(radius_arcmin) / 60.0
    out = []
    for ralo, rahi, declo, dechi in viewer_boxes(ra, dec, radius_arcmin):
        cosd = max(math.cos(math.radians(float(dec))), 1e-6)
        nx = max(1, math.ceil((rahi - ralo) * cosd * 60.0 / VIEWER_TILE_ARCMIN - 1e-3))
        ny = max(1, math.ceil((dechi - declo) * 60.0 / VIEWER_TILE_ARCMIN - 1e-3))
        xe = [ralo + (rahi - ralo) * i / nx for i in range(nx + 1)]
        ye = [declo + (dechi - declo) * j / ny for j in range(ny + 1)]
        for i in range(nx):
            for j in range(ny):
                m_dec = max(VIEWER_MARGIN_ARCSEC / 3600.0, VIEWER_MARGIN_FRACTION * (ye[j + 1] - ye[j]))
                m_ra = max(VIEWER_MARGIN_ARCSEC / 3600.0 / cosd, VIEWER_MARGIN_FRACTION * (xe[i + 1] - xe[i]))
                t = (xe[i] - m_ra, xe[i + 1] + m_ra, max(-90.0, ye[j] - m_dec), min(90.0, ye[j + 1] + m_dec))
                if _tile_reaches_cone(t, float(ra), float(dec), r_deg):
                    out.append(t)
    return out


def _edge(x: float, direction: int) -> str:
    """A box edge as the viewer's 8-decimal text, moved outwards by 1e-7 deg (0.36 mas) and rounded outwards: a row
    on the edge of the cone's box is inside the requested box whichever edge rule the viewer has (the cone cut that
    follows removes whatever is not in the cone)."""
    import math

    n = math.floor(float(x) * 1e8) - 10 if direction < 0 else math.ceil(float(x) * 1e8) + 10
    return f"{n / 1e8:.8f}"


def _viewer_read(resp, limit: int = None, deadline: float = None) -> bytes:
    """The body of a viewer answer, at most VIEWER_MAX_BYTES: a box that is that large is not read on (a dense
    field; the hedge fails, which is what happens without a hedge).  ``deadline`` (``time.monotonic()``): the
    cone's VIEWER_BUDGET_S is also kept while a slow answer streams in (2.60.10 review, Codex)."""
    import time

    limit = VIEWER_MAX_BYTES if limit is None else limit
    if hasattr(resp, "iter_content"):
        chunks, n = [], 0
        for c in resp.iter_content(chunk_size=1 << 20):
            n += len(c)
            if n > limit:
                resp.close()
                raise RuntimeError(f"Legacy Surveys viewer: answer larger than {limit / 1e6:.0f} MB, not read")
            if deadline is not None and time.monotonic() > deadline:
                resp.close()
                raise TimeoutError(f"Legacy Surveys viewer: tiles not done in {VIEWER_BUDGET_S:.0f} s (while reading)")
            chunks.append(c)
        return b"".join(chunks)
    if len(resp.content) > limit:
        raise RuntimeError(f"Legacy Surveys viewer: answer larger than {limit / 1e6:.0f} MB, not read")
    return resp.content


def _viewer_fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    """The Tractor rows of the cone from the viewer catalogue, as the TAP query returns them.

    Same columns in the same order (TAP_COLUMNS), the primary (non-duplicate) rows inside the
    cone, ``legacy_query_status`` = HEDGE_STATUS.  A box without catalogue sources is answered
    with a one-line text, i.e. an empty table (outside the footprint: the Galactic-plane field)."""
    import io

    import numpy as np
    import requests
    from astropy.table import Table

    import time

    parts = []
    tiles = viewer_tiles(ra, dec, radius_arcmin)
    t0 = time.monotonic()
    if len(tiles) > 1:
        print(f"[desi_legacy] viewer: {len(tiles)} tiles for the {float(radius_arcmin):g}' cone", flush=True)
    for ralo, rahi, declo, dechi in tiles:
        if time.monotonic() - t0 > VIEWER_BUDGET_S:
            raise TimeoutError(f"Legacy Surveys viewer: {len(tiles)} tiles not done in {VIEWER_BUDGET_S:.0f} s")
        resp = requests.get(
            VIEWER_URL.format(layer=VIEWER_LAYER),
            params={
                "ralo": _edge(ralo, -1),
                "rahi": _edge(rahi, +1),
                "declo": _edge(declo, -1),
                "dechi": _edge(dechi, +1),
            },
            timeout=VIEWER_TIMEOUT_S,
            stream=True,
        )
        resp.raise_for_status()
        body = _viewer_read(resp, deadline=t0 + VIEWER_BUDGET_S)
        if body[:6] != b"SIMPLE":  # "No catalog sources in layer and RA,Dec box"
            if b"No catalog sources" in body[:200]:
                continue
            raise RuntimeError(f"Legacy Surveys viewer: not a FITS table: {body[:100]!r}")
        tab = Table.read(io.BytesIO(body), format="fits")

        def col(name):  # FITS is big-endian; pandas needs native byte order
            a = np.asarray(tab[name])
            return a.astype(a.dtype.newbyteorder("="))

        data = {}
        for name in TAP_COLUMNS:
            if name == "ls_id":
                # The Data Lab ls_dr10 ids: DR10 South rows release<<40 | brickid<<20 | objid, DR9 North rows
                # their DR9 id release<<40 | brickid<<16 | objid (2.57.0 review, compare_ls_viewer.py: the 219
                # rows north of the split had the same release, brickid and objid and only this differed).
                rel = col("release").astype(np.int64)
                shift = np.where(rel < 10000, 2**16, 2**20)
                data[name] = rel * 2**40 + col("brickid").astype(np.int64) * shift + col("objid").astype(np.int64)
            elif name.startswith("dchisq_"):
                data[name] = col("dchisq")[:, int(name[-1]) - 1]
            elif name == "type":
                data[name] = np.char.strip(np.char.decode(col("type").astype("S"), "ascii"))
            elif name not in tab.colnames:  # DR9 North (BASS + MzLS) has no i band
                data[name] = np.full(len(tab), np.nan)
            else:
                data[name] = col(name)
        df = pd.DataFrame(data)
        keep = col("brick_primary").astype(bool) if "brick_primary" in tab.colnames else np.ones(len(df), bool)
        parts.append(df[keep])
    if time.monotonic() - t0 > VIEWER_BUDGET_S:  # the last tile finished late: not accepted (2.60.10 review, Codex)
        raise TimeoutError(f"Legacy Surveys viewer: {len(tiles)} tiles not done in {VIEWER_BUDGET_S:.0f} s")
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
    run = lambda q: _query_with_retries(
        lambda: _service().search(q).to_table().to_pandas(), hedge, hedge_delay=hedge_delay_s(radius_arcmin)
    )
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
