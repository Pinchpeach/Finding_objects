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
Z_COLUMNS = ("sdss_dr18_spectroscopy__z", "desi_dr1_spectroscopy__z", "lamost_dr10_spectroscopy__z",
             "ned__Redshift", "simbad__rvz_redshift")
SPEC_Z_COLUMNS = Z_COLUMNS[:3]


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


def _foreground_star(row) -> bool:
    try:
        ev = json.loads(row.get("evidence_json") or "[]")
    except (TypeError, json.JSONDecodeError):
        return False
    return any(e.get("rule_id") in FOREGROUND_RULES and (_num(e.get("raw_score")) or 0) >= 0.5 for e in ev)


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
        out["parent_object_id"] = parent; out["component_role"] = role; out["n_components"] = 0
        return out
    rows = out.to_dict("records")
    host_index = {}
    for i, r in enumerate(rows):
        k = _num(r.get("sga_2020__catalog_object_id"))
        if k is not None:
            host_index[int(k)] = i
    named = {i: {_norm_name(x) for x in str(rows[i].get("catalog_designations") or rows[i].get("designation", "")).split("; ") if x}
             for i in host_index.values()}
    # Host redshift: own value, else from an identity member (pass 1).
    members: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        hk = _num(r.get("host_large_galaxy")); q = _num(r.get("host_elliptical_radius"))
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
            if _foreground_star(r) or any(c in cats for c in EVENT_CATALOGS):
                continue
            zi = _redshift(r, SPEC_Z_COLUMNS) or _redshift(r)
            if zi is not None and host_z[h] is not None and abs(zi - host_z[h]) * C_KMS > DV_MAX_KMS:
                continue
            parent[i] = rows[h]["object_id"]
            role[i] = "identity" if identity(h, i) else "nucleus" if near_centre(h, i) else "component"
    out["parent_object_id"] = parent
    out["component_role"] = role
    counts = pd.Series([p for p in parent if p]).value_counts()
    out["n_components"] = out.object_id.map(counts).fillna(0).astype(int)
    out["host_redshift"] = [host_z.get(i) for i in range(n)]
    _attach_identity(out, priority)
    return out


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
    for i in out.index[out.component_role.eq("identity")]:
        host = out.index[out.object_id.eq(out.at[i, "parent_object_id"])]
        if len(host) and out.at[i, "designation"] == out.at[host[0], "designation"]:
            out.at[i, "designation"] = f"{out.at[i, 'designation']} ({out.at[i, 'designation_catalog']} entry)"
