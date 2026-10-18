"""Galaxy cluster membership (2.32.0).

Clusters from Get_data/galaxy_clusters.py (Wen & Han 2024 from DESI Legacy
Surveys; eRASS1 clusters of Bulbul et al. 2024 with P_cont < 0.5, the
95 %-pure selection of their Table 1).  For every object classified GALAXY
inside a cluster's r500 (angular size from the cluster redshift, flat LCDM
H0 = 70, Om = 0.3):

* with a spectroscopic redshift: MEMBER if the rest-frame velocity offset
  |dv| = c |z - z_cl| / (1 + z_cl) <= 2500 km/s (Wen & Han 2024, Sect. 3,
  the membership window around a spectroscopic cluster redshift), otherwise
  NON_MEMBER (a fore- or background galaxy seen through the cluster);
* without one: IN_CLUSTER_AREA -- membership needs a redshift (photometric
  membership windows are 0.04 (1+z) wide, Wen & Han 2024).
The galaxy within BCG_RADIUS_ARCSEC of a Wen & Han cluster position (their
position is the BCG) is the brightest cluster galaxy.  Where several clusters
overlap, the one with the smallest distance in units of r500 is used.
"""

from __future__ import annotations
from pathlib import Path
import math

import numpy as np
import pandas as pd

C_KMS = 299792.458
MAX_DV_KMS = 2500.0
MAX_PCONT = 0.5
BCG_RADIUS_ARCSEC = 3.0
H0, OM = 70.0, 0.3
Z_COLUMNS = ("std_z_spec", "desi_dr1_spectroscopy__z", "sdss_dr18_spectroscopy__z", "lamost_dr_catalog__z")


def _da_mpc(z: float) -> float:
    """Angular diameter distance, flat LCDM (trapezoidal integral of 1/E(z))."""
    zz = np.linspace(0.0, z, 257)
    f = 1.0 / np.sqrt(OM * (1 + zz) ** 3 + 1 - OM)
    dc = C_KMS / H0 * float(((f[1:] + f[:-1]) / 2 * np.diff(zz)).sum())  # trapezoid (numpy 1.x and 2.x)
    return dc / (1.0 + z)


def _unit(ra, dec):
    ra, dec = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    return np.column_stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


def load_clusters(raw_dir) -> pd.DataFrame:
    files = sorted(Path(raw_dir).glob("galaxy_clusters_*.csv")) if raw_dir else []
    if not files:
        return pd.DataFrame()
    cl = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    if cl.empty:
        return cl
    for c in ("ra", "dec", "cluster_z", "cluster_r500_mpc", "pcont"):
        cl[c] = pd.to_numeric(cl.get(c), errors="coerce")
    cl = cl[cl.cluster_z.gt(0) & cl.cluster_r500_mpc.gt(0) & ~cl.pcont.ge(MAX_PCONT)].copy()
    cl["theta500_arcsec"] = [r / _da_mpc(z) * 206264.806 for r, z in zip(cl.cluster_r500_mpc, cl.cluster_z)]
    return cl.reset_index(drop=True)


def _zspec(row):
    for c in Z_COLUMNS:
        try:
            v = float(row.get(c))
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            return v
    return None


def apply(out: pd.DataFrame, raw_dir) -> pd.DataFrame:
    cl = load_clusters(raw_dir)
    if cl.empty or out.empty:
        return out
    gal = out.index[out.get("primary_class", pd.Series(index=out.index, dtype=object)).astype(str).eq("GALAXY")]
    if not len(gal):
        return out
    sep = (
        np.degrees(np.arccos(np.clip(_unit(out.loc[gal, "ra"], out.loc[gal, "dec"]) @ _unit(cl.ra, cl.dec).T, -1, 1)))
        * 3600
    )
    scaled = sep / cl.theta500_arcsec.to_numpy()[None, :]
    best = scaled.argmin(axis=1)
    inside = scaled[np.arange(len(gal)), best] <= 1.0
    out = out.copy()
    for col in ("cluster_name", "cluster_z", "cluster_membership", "cluster_basis"):
        out[col] = out[col].astype(object) if col in out else pd.Series(None, index=out.index, dtype=object)
    if "subclass_tags" in out:
        out["subclass_tags"] = out["subclass_tags"].astype(object)
    for k, i in enumerate(gal):
        if not inside[k]:
            continue
        c = cl.iloc[best[k]]
        d = sep[k, best[k]]
        ztxt = f"z = {c.cluster_z:.3f}{' (spec)' if str(c.get('cluster_z_spec')) == 'True' else ''}"
        where = f"{d / 60:.1f}' from the centre ({d / c.theta500_arcsec:.2f} r500)"
        z = _zspec(out.loc[i])
        if c.cluster_source == "WH24" and d <= BCG_RADIUS_ARCSEC:
            mem, basis = "BCG", f"brightest cluster galaxy of {c.catalog_object_id} ({ztxt}; Wen & Han 2024)"
        elif z is not None:
            dv = C_KMS * abs(z - c.cluster_z) / (1 + c.cluster_z)
            if dv <= MAX_DV_KMS:
                mem, basis = (
                    "MEMBER",
                    f"member of {c.catalog_object_id} ({ztxt}): |dv| = {dv:.0f} km/s <= 2500, {where}",
                )
            else:
                mem, basis = (
                    "NON_MEMBER",
                    f"seen through {c.catalog_object_id} ({ztxt}) but |dv| = {dv:.0f} km/s, {where}",
                )
        else:
            mem, basis = (
                "IN_CLUSTER_AREA",
                f"inside {c.catalog_object_id} ({ztxt}), {where}; no redshift to test membership",
            )
        out.loc[i, ["cluster_name", "cluster_z", "cluster_membership", "cluster_basis"]] = [
            c.catalog_object_id,
            round(float(c.cluster_z), 4),
            mem,
            basis,
        ]
        if mem in ("MEMBER", "BCG") and "subclass_tags" in out:
            tag = (
                "brightest cluster galaxy" if mem == "BCG" else "galaxy cluster member"
            ) + f" ({c.catalog_object_id})"
            prev = out.loc[i, "subclass_tags"]
            out.loc[i, "subclass_tags"] = f"{prev}; {tag}" if isinstance(prev, str) and prev else tag
    return out
