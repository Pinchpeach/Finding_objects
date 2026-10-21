"""Consolidate detections of one large galaxy into a single host object.

Survey source extractors split ("shred") nearby, well-resolved galaxies into
many detections: HII regions, spiral-arm knots, dust lanes and the nucleus
each become separate catalogue entries (SDSS: Blanton et al. 2005, AJ 129,
2562, NYU-VAGC; Pan-STARRS1: Flewelling et al. 2020; Legacy Surveys handle
the galaxies of the Siena Galaxy Atlas specially for this reason, Moustakas
et al. 2023, ApJS 269, 3). Name-based catalogues (SIMBAD, NED) and spectra of
the nucleus add further entries at slightly different positions. Treated as
independent objects they produce several partial copies of one galaxy.

Rule, applied after classification (``pipeline.py``):

* The host is the object carrying the SGA-2020 entry. A member is any other
  object inside that galaxy's D26 ellipse (``host_elliptical_radius`` < 1,
  Stage 2).
* A member stays an independent object when there is evidence that it is
  NOT part of the galaxy:
    - a significant Gaia parallax or proper motion (Stage-4 rules
      AST-GAL-001/002; foreground Milky Way star);
    - a spectroscopic redshift inconsistent with the host's
      (|c dz| > DV_MAX_KMS; background QSO/galaxy or foreground star);
    - its own SGA entry (a separate catalogued galaxy);
    - a transient-event catalogue entry (supernovae belong to the event,
      not to the persistent host).
* Every other member becomes a component of the host
  (``parent_object_id``) with a role: ``identity`` (a SIMBAD/NED entry with
  the galaxy's own name, or a name-catalogue entry at the centre), ``nucleus``
  (within NUCLEUS_ARCSEC of the SGA centre, e.g. a fibre spectrum of the
  nucleus) or ``component`` (the rest: HII regions, arm knots, shreds).
  Identity names are attached to the host, which is then named by the usual
  designation priority (SIMBAD first); the host redshift comes from the host,
  an identity entry or a nucleus spectrum, in that order.
* Independent objects inside the ellipse are kept as top-level objects with
  ``component_role`` foreground_star / background_source /
  foreground_source / transient, so the reason they were not merged stays
  visible.

DV_MAX_KMS = 1500 km/s is wider than the rotation/velocity dispersion of
any single galaxy (<~ 600 km/s even for massive ellipticals and the widest
rotation curves) yet much smaller than the separation of physically
unrelated background sources; it is the same order as the linking velocity
used for galaxy groups (e.g. Tago et al. 2010 use ~ 250-1000 km/s), so
it errs on the side of keeping the host together.
"""

from __future__ import annotations
import json
import math
import re
import numpy as np
import pandas as pd

C_KMS = 299792.458
DV_MAX_KMS = 1500.0
NUCLEUS_ARCSEC = 5.0
FOREGROUND_RULES = {"AST-GAL-001", "AST-GAL-002"}
NAME_CATALOGS = ("SIMBAD", "NED")
EVENT_CATALOGS = ("ASAS-SN Supernova Catalog", "Asiago Supernova Catalog")
# Spectroscopic surveys first, then the NED / SIMBAD compilations.
Z_COLUMNS = (
    "sdss_dr18_spectroscopy__z",
    "desi_dr1_spectroscopy__z",
    "lamost_dr_catalog__z",
    "ned__Redshift",
    "simbad__rvz_redshift",
)


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _norm_name(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _redshift(row, cols=Z_COLUMNS):
    for c in cols:
        z = _num(row.get(c))
        if z is not None:
            return z
    return None


CSTAR_MAX_SIGMA = 5.0


def _foreground_star(row) -> bool:
    try:
        ev = json.loads(row.get("evidence_json") or "[]")
    except (TypeError, json.JSONDecodeError):
        return False
    # Extended / blended Gaia sources (C* > 5 sigma, Stage 4 ``cstar_sigma``)
    # have spurious motions: not a foreground star (same gate as Stage 5).
    return any(
        e.get("rule_id") in FOREGROUND_RULES
        and (_num(e.get("raw_score")) or 0) >= 0.5
        and not ((_num(e.get("cstar_sigma")) or 0) > CSTAR_MAX_SIGMA)
        for e in ev
    )


def _sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    dra = ((ra1 - ra2 + 180.0) % 360.0 - 180.0) * math.cos(math.radians(dec2))
    return math.hypot(dra, dec1 - dec2) * 3600.0


def consolidate(df: pd.DataFrame, priority=()) -> pd.DataFrame:
    """Add parent_object_id / component_role / n_components and attach the
    identity entries (names, redshift) of each SGA host to that host."""
    out = df.copy()
    n = len(out)
    parent = [None] * n
    role = [""] * n
    if n == 0 or "host_large_galaxy" not in out:
        out["parent_object_id"] = parent
        out["component_role"] = role
        out["n_components"] = 0
        return out
    rows = out.to_dict("records")
    host_index = {}
    for i, r in enumerate(rows):
        k = _num(r.get("sga_2020__catalog_object_id"))
        if k is not None:
            host_index[int(k)] = i
    named = {
        i: {
            _norm_name(x)
            for x in str(rows[i].get("catalog_designations") or rows[i].get("designation", "")).split("; ")
            if x
        }
        for i in host_index.values()
    }
    # Host redshift: own value, else from an identity member (pass 1).
    members: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        hk = _num(r.get("host_large_galaxy"))
        q = _num(r.get("host_elliptical_radius"))
        if hk is None or q is None or q >= 1.0 or int(hk) not in host_index:
            continue
        h = host_index[int(hk)]
        if h == i or _num(r.get("sga_2020__catalog_object_id")) is not None:
            continue
        members.setdefault(h, []).append(i)

    def near_centre(h, i):
        r, hr = rows[i], rows[h]
        ra, dec, ra0, dec0 = (_num(r.get("ra")), _num(r.get("dec")), _num(hr.get("ra")), _num(hr.get("dec")))
        return None not in (ra, dec, ra0, dec0) and _sep_arcsec(ra, dec, ra0, dec0) <= NUCLEUS_ARCSEC

    def identity(h, i):
        """A SIMBAD/NED entry for the galaxy itself: same name as the host, or
        a name-catalogue entry at the galaxy centre."""
        r = rows[i]
        if str(r.get("designation_catalog")) not in NAME_CATALOGS:
            return False
        return _norm_name(r.get("designation")) in named.get(h, set()) or near_centre(h, i)

    host_z = {}
    for h, ms in members.items():
        z = _redshift(rows[h])
        for test in (identity, near_centre):
            for i in ms:
                if z is None and test(h, i):
                    z = _redshift(rows[i])
        host_z[h] = z

    for h, ms in members.items():
        for i in ms:
            r = rows[i]
            cats = str(r.get("catalogs", ""))
            # Independent objects seen through the galaxy keep a role that says why.
            if _foreground_star(r):
                role[i] = "foreground_star"
                continue
            if any(c in cats for c in EVENT_CATALOGS):
                role[i] = "transient"
                continue
            zi = _redshift(r)
            if zi is not None and host_z[h] is not None and abs(zi - host_z[h]) * C_KMS > DV_MAX_KMS:
                role[i] = "background_source" if zi > host_z[h] else "foreground_source"
                continue
            parent[i] = rows[h]["object_id"]
            role[i] = "identity" if identity(h, i) else "nucleus" if near_centre(h, i) else "component"
    out["parent_object_id"] = parent
    out["component_role"] = role
    counts = pd.Series([p for p in parent if p]).value_counts()
    out["n_components"] = out.object_id.map(counts).fillna(0).astype(int)
    out["host_redshift"] = [host_z.get(i) for i in range(n)]
    _inherit(out)
    _attach_identity(out, priority)
    return out


# Spectroscopic/curated fields a host inherits from its identity and nucleus
# entries when it has none of its own (the nucleus fibre measures the galaxy).
INHERITED = (
    "sdss_dr18_spectroscopy__subclass",
    "sdss_dr18_spectroscopy__class",
    "sdss_dr18_spectroscopy__z",
    "desi_dr1_spectroscopy__z",
    "simbad__otype",
    "ned__Type",
)


def _inherit(out: pd.DataFrame) -> None:
    cols = [c for c in INHERITED if c in out]
    if not cols:
        return
    src = out[out.component_role.isin(["identity", "nucleus"])]
    for host_id, g in src.groupby("parent_object_id"):
        h = out.index[out.object_id.eq(host_id)]
        if not len(h):
            continue
        for c in cols:
            if pd.isna(out.at[h[0], c]):
                vals = g[c].dropna()
                if len(vals):
                    out.at[h[0], c] = vals.iloc[0]


def _attach_identity(out: pd.DataFrame, priority) -> None:
    """Give each host the names of its nucleus/identity components and pick
    its designation again by catalogue priority (SIMBAD/NED name first)."""
    if "catalog_designations" not in out:
        return
    nuc = out[out.component_role.eq("identity")]
    if nuc.empty:
        return
    rank = {c: k for k, c in enumerate(priority)}
    for host_id, g in nuc.groupby("parent_object_id"):
        h = out.index[out.object_id.eq(host_id)]
        if not len(h):
            continue
        h = h[0]
        cands = [(out.at[h, "designation_catalog"], out.at[h, "designation"])]
        cands += list(zip(g.designation_catalog, g.designation))
        names = [out.at[h, "catalog_designations"]] + g.catalog_designations.astype(str).tolist()
        merged = []
        for block in names:
            for x in str(block).split("; "):
                if x and x != "nan" and x not in merged:
                    merged.append(x)
        best = min(cands, key=lambda t: rank.get(str(t[0]), len(rank)))
        if best[1] != out.at[h, "designation"]:
            out.at[h, "designation"], out.at[h, "designation_catalog"] = best[1], best[0]
        out.at[h, "catalog_designations"] = "; ".join([best[1]] + [m for m in merged if m != best[1]])
        cats = set(str(out.at[h, "catalogs"]).split("|"))
        for c in g.catalogs.astype(str):
            cats.update(c.split("|"))
        out.at[h, "catalogs"] = "|".join(sorted(x for x in cats if x and x != "nan"))
    # An identity entry that lent its name to the host keeps a distinct label.
    # Designations were numbered for uniqueness before consolidation ("NGC
    # 4522 [1]" / "[2]" when a nucleus entry and the host both carry the
    # name); once the entry is a part of the host, the host takes the plain
    # name back unless another top-level object still shares it (2.20.0).
    base = lambda v: re.sub(r" \[\d+\]$", "", str(v))
    top = out.parent_object_id.isna()
    for i in out.index[out.component_role.eq("identity")]:
        host = out.index[out.object_id.eq(out.at[i, "parent_object_id"])]
        if not len(host):
            continue
        h = host[0]
        b = base(out.at[h, "designation"])
        if base(out.at[i, "designation"]) != b:
            continue
        others = top & out.designation.astype(str).map(base).eq(b) & (out.index != h)
        if not others.any():
            out.at[h, "designation"] = b
        out.at[i, "designation"] = f"{b} ({out.at[i, 'designation_catalog']} entry)"


# --- Pan-STARRS1 duplicates and fragments of small galaxies (2.34.0) ---------
# PS1 builds MeanObjects by linking single-epoch detections within 1"
# (Chambers et al. 2016, sec. 4.2).  On a resolved galaxy the per-epoch
# centroid wanders, and one galaxy becomes two or three MeanObjects: in the
# 2026-10-20 review (WORK_REPORT_2026-10-20.md; 4 fields, 76 cases) every one
# lay on a single galaxy in the Legacy Surveys image, none had a Gaia source
# within 0.5", and where both rows had a Kron magnitude each held the whole
# galaxy's flux (Kron r - LS r ~ 0 to +0.4), i.e. repeated measurements of
# one galaxy, not separate objects.  Others are knots along large discs.  The
# association left them as separate objects (only one PS1 row per object, or
# an ambiguous match), so a galaxy was counted two or three times.
#
# Rule: a top-level object measured only by PS1 becomes a component of an
# extended Legacy Surveys galaxy when
#   * it lies within PS1_HOST_RADII half-light radii of the galaxy centre
#     (Tractor shape_r along the major axis, so the bound is generous on the
#     minor axis; host-galaxy association uses directional light radius
#     d_DLR < 4, Sullivan et al. 2006; Gupta et al. 2016), at least
#     PS1_HOST_MIN_ARCSEC (PS1 centroid scatter at ~1.2" seeing);
#   * no other Legacy Surveys source lies within LS_RESOLVED_ARCSEC of it
#     (LS would have resolved a separate source there);
#   * no Gaia or SDSS source of another object lies within SEPARATE_ARCSEC
#     (an independent detection: a star on the galaxy, or a neighbour that
#     SDSS deblends and LS merged, field RA 245).  The one exception is an
#     SDSS source that is the only SDSS source on the galaxy: that is SDSS's
#     measurement of the galaxy itself, which the association often joined to
#     one of the PS1 rows rather than to the LS galaxy (an object measured by
#     PS1 and SDSS only is then also a candidate);
#   * it is not brighter than the galaxy by more than BRIGHTER_MAG (a brighter
#     PS1 source is another object).
# The PS1 measurement is kept as a component (role ``ps1_duplicate`` when its
# Kron flux is the whole galaxy's, else ``component``), as Gaia's external
# cross-match keeps the extra entries of one source (number_of_mates,
# Marrese et al. 2019).
PS1 = "Pan-STARRS1 DR2 MeanObject"
LS = "DESI Legacy Surveys DR10"
LITERATURE = {"SIMBAD", "NED"}
EXTENDED_TYPES = {"REX", "EXP", "DEV", "SER", "COMP"}
PS1_HOST_RADII = 2.0
PS1_HOST_MIN_ARCSEC = 1.0
LS_RESOLVED_ARCSEC = 1.0
SEPARATE_ARCSEC = 0.7
BRIGHTER_MAG = 0.75
WHOLE_GALAXY_MAG = 0.5


SDSS = "SDSS DR18 PhotoObj"
SDSS_ON_GALAXY_MIN_ARCSEC = 1.5


def attach_ps1_fragments(out: pd.DataFrame, assoc: pd.DataFrame, explain: dict | None = None) -> pd.DataFrame:
    """Group PS1 duplicates/fragments under their galaxy; ``explain`` (optional
    dict) receives object_id -> reason for every candidate left independent."""
    why = explain if explain is not None else {}
    if out.empty or assoc is None or assoc.empty or "catalogs" not in out:
        return out
    out = out.copy()
    for c, default in (("parent_object_id", None), ("component_role", ""), ("n_components", 0)):
        if c not in out:
            out[c] = default
    for c in ("parent_object_id", "component_role", "unknown_reason"):  # read back from CSV as all-NaN floats
        if c in out:
            out[c] = out[c].astype(object)
    top = out.parent_object_id.isna()
    cats = out.catalogs.astype(str).map(lambda s: frozenset(c for c in s.split("|") if c) - LITERATURE)
    cand = out.index[top & cats.map(lambda c: PS1 in c and c <= {PS1, SDSS})]
    typ = out.get("desi_legacy_surveys_dr10__type", pd.Series("", index=out.index)).astype(str).str.strip().str.upper()
    shape = pd.to_numeric(out.get("desi_legacy_surveys_dr10__shape_r", pd.Series(np.nan, index=out.index)), errors="coerce")
    hosts = out.index[top & typ.isin(EXTENDED_TYPES) & shape.gt(0)]
    if not len(cand) or not len(hosts):
        return out

    def positions(catalog):
        a = assoc[assoc.catalog.eq(catalog)]
        return a.object_id.to_numpy(), a.ra.to_numpy(float), a.dec.to_numpy(float)

    ls_oid, ls_ra, ls_dec = positions(LS)
    ps_oid, ps_ra, ps_dec = positions(PS1)
    others = assoc[assoc.catalog.isin(["Gaia DR3", SDSS])]
    sd = assoc[assoc.catalog.eq(SDSS)]
    oid_index = dict(zip(out.object_id, out.index))
    ls_pos = {o: (r, d) for o, r, d in zip(ls_oid, ls_ra, ls_dec)}
    ps_pos = {o: (r, d) for o, r, d in zip(ps_oid, ps_ra, ps_dec)}
    host_oids = [out.at[h, "object_id"] for h in hosts if out.at[h, "object_id"] in ls_pos]
    if not host_oids:
        return out
    h_ra = np.array([ls_pos[o][0] for o in host_oids])
    h_dec = np.array([ls_pos[o][1] for o in host_oids])
    h_re = np.array([shape[oid_index[o]] for o in host_oids])
    kron = pd.to_numeric(out.get("pan_starrs1_dr2_meanobject__rMeanKronMag", pd.Series(np.nan, index=out.index)), errors="coerce")
    ls_r = pd.to_numeric(out.get("std_mag__ls_r", pd.Series(np.nan, index=out.index)), errors="coerce")

    def sep(ra, dec, ras, decs):
        return np.hypot(((ras - ra + 180.0) % 360.0 - 180.0) * math.cos(math.radians(dec)), decs - dec) * 3600.0

    for i in cand:
        oid = out.at[i, "object_id"]
        if oid not in ps_pos:
            continue
        ra, dec = ps_pos[oid]
        d = sep(ra, dec, h_ra, h_dec)
        ok = d <= np.maximum(PS1_HOST_RADII * h_re, PS1_HOST_MIN_ARCSEC)
        if not ok.any():
            why[oid] = "not inside an extended LS galaxy"
            continue
        k = int(np.argmin(np.where(ok, d / h_re, np.inf)))
        host = host_oids[k]
        ls_d = sep(ra, dec, ls_ra, ls_dec)
        if ((ls_d <= LS_RESOLVED_ARCSEC) & (ls_oid != host)).any():
            why[oid] = "another LS source within 1 arcsec"
            continue
        # SDSS sources on the galaxy: exactly one = SDSS's measurement of the galaxy.
        on = sep(h_ra[k], h_dec[k], sd.ra.to_numpy(float), sd.dec.to_numpy(float)) <= max(
            PS1_HOST_RADII * h_re[k], SDSS_ON_GALAXY_MIN_ARCSEC
        )
        galaxy_sdss = set(sd.object_id.to_numpy()[on]) if on.sum() == 1 else set()
        if SDSS in cats[i] and oid not in galaxy_sdss:
            why[oid] = "its SDSS source is one of several SDSS sources on the galaxy"
            continue
        if len(others):
            od = sep(ra, dec, others.ra.to_numpy(float), others.dec.to_numpy(float))
            oo = others.object_id.to_numpy()
            near = (od <= SEPARATE_ARCSEC) & (oo != host) & (oo != oid)
            near &= ~(others.catalog.eq(SDSS).to_numpy() & np.isin(oo, list(galaxy_sdss)))
            if near.any():
                why[oid] = "Gaia or SDSS source of another object within 0.7 arcsec"
                continue
        h = oid_index[host]
        dm = kron[i] - ls_r[h] if 10 < kron[i] < 30 and np.isfinite(ls_r[h]) else np.nan
        if np.isfinite(dm) and dm < -BRIGHTER_MAG:
            why[oid] = "brighter than the galaxy"
            continue
        out.at[i, "parent_object_id"] = host
        out.at[i, "component_role"] = "ps1_duplicate" if np.isfinite(dm) and abs(dm) <= WHOLE_GALAXY_MAG else "component"
        if "unknown_reason" in out:
            name = out.at[h, "designation"] if "designation" in out else host
            out.at[i, "unknown_reason"] = f"Pan-STARRS1 measurement of the galaxy {name} (grouped under it)"
    counts = out.parent_object_id.dropna().value_counts()
    out["n_components"] = out.object_id.map(counts).fillna(0).astype(int)
    return out


# Bright-star halo artefacts (2.35.0).  Saturated stars break into extra
# catalogue rows: PSPHOT splits bright stars and their diffraction spikes into
# several detections, so PS1 analyses mask around them (Metcalfe et al. 2013,
# arXiv:1310.6368; PS1 saturates near r ~ 13-15, Chambers et al. 2016), and a WISE/GALEX row that the
# association could not tie to the saturated star stays alone.  In the
# 2026-10-21 independent fields single-catalogue PS1 rows were 40-100 times
# more frequent than the background within 2" of G < 13 stars, 5-10 times
# within 1-5" of G = 13-15 stars, and still 4 times at 20-30" of G < 11 stars;
# 214 such objects around 96 stars, 51 of them classified (mostly GALAXY).
# Radius: the Legacy Surveys BRIGHT-star mask, half the radius-magnitude locus
# R(G) = 1630" x 1.396^-G of legacypipe (mask_radius_for_mag; LS DR9/DR10
# bitmask documentation: MEDIUM = R, BRIGHT = R/2), applied to Gaia stars
# brighter than the MEDIUM-mask limit G = 16.  Only rows seen by a single
# survey qualify: a real neighbour in the halo is also measured by the deeper
# Legacy Surveys or by Gaia.  That premise needs Legacy Surveys imaging: where
# a star has no LS source within LS_COVER_ARCSEC (Kepler field, M31 area,
# Galactic plane), a PS1-only row is often a real faint star, so only the
# inner quarter of the locus, where the measured excess was >= 4-9 times the
# background (>= 75-90 % artefacts), is used.
HALO_G_MAX = 16.0
HALO_MIN_ARCSEC = 2.0
HALO_CATALOGS = {PS1, "AllWISE", "GALEX AIS", SDSS, "2MASS PSC"}
LS_COVER_ARCSEC = 60.0


def halo_radius_arcsec(g, ls_imaging=True):
    """Legacy Surveys BRIGHT-mask radius (arcsec) of a star of Gaia magnitude
    ``g``; half of it outside the Legacy Surveys footprint."""
    return max((0.5 if ls_imaging else 0.25) * 1630.0 * 1.396 ** (-float(g)), HALO_MIN_ARCSEC)


def attach_bright_star_artifacts(out: pd.DataFrame) -> pd.DataFrame:
    """Group single-survey rows in the halo of a bright Gaia star under the star."""
    need = {"catalogs", "ra", "dec", "primary_class", "gaia_dr3__phot_g_mean_mag"}
    if out.empty or not need <= set(out.columns):
        return out
    out = out.copy()
    for c, default in (("parent_object_id", None), ("component_role", ""), ("n_components", 0)):
        if c not in out:
            out[c] = default
    for c in ("parent_object_id", "component_role", "unknown_reason"):
        if c in out:
            out[c] = out[c].astype(object)
    top = out.parent_object_id.isna()
    g = pd.to_numeric(out.gaia_dr3__phot_g_mean_mag, errors="coerce")
    stars = out.index[top & out.primary_class.eq("STAR") & g.lt(HALO_G_MAX)]
    cats = out.catalogs.astype(str).map(lambda s: frozenset(c for c in s.split("|") if c) - LITERATURE)
    cand = out.index[top & cats.map(lambda c: len(c) == 1 and c <= HALO_CATALOGS)]
    if not len(stars) or not len(cand):
        return out
    s_ra, s_dec = out.loc[stars, "ra"].to_numpy(float), out.loc[stars, "dec"].to_numpy(float)
    has_ls = out.catalogs.astype(str).str.contains(LS, regex=False)
    l_ra, l_dec = out.loc[has_ls, "ra"].to_numpy(float), out.loc[has_ls, "dec"].to_numpy(float)

    def covered(ra, dec):
        d = np.hypot(((l_ra - ra + 180.0) % 360.0 - 180.0) * math.cos(math.radians(dec)), l_dec - dec) * 3600.0
        return bool((d <= LS_COVER_ARCSEC).any())

    s_r = np.array([halo_radius_arcsec(x, covered(a, b)) for x, a, b in zip(g[stars], s_ra, s_dec)])
    for i in cand:
        ra, dec = float(out.at[i, "ra"]), float(out.at[i, "dec"])
        d = np.hypot(((s_ra - ra + 180.0) % 360.0 - 180.0) * math.cos(math.radians(dec)), s_dec - dec) * 3600.0
        ok = d <= s_r
        if not ok.any():
            continue
        k = int(np.argmin(np.where(ok, d / s_r, np.inf)))
        h = stars[k]
        out.at[i, "parent_object_id"] = out.at[h, "object_id"]
        out.at[i, "component_role"] = "bright_star_halo"
        if "unknown_reason" in out:
            name = out.at[h, "designation"] if "designation" in out else out.at[h, "object_id"]
            out.at[i, "unknown_reason"] = (
                f"{next(iter(cats[i]))} row {d[k]:.1f}\" from the bright star {name} (G {g[h]:.1f}): "
                "a saturation/halo artefact or the star's own unmatched measurement (grouped under it)"
            )
    counts = out.parent_object_id.dropna().value_counts()
    out["n_components"] = out.object_id.map(counts).fillna(0).astype(int)
    return out
