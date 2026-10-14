"""Catalogue designations for associated objects.

The pipeline's ``object_id`` (OBJ000001, ...) is an internal join key that
changes from run to run. For display and export every object also gets the
designation it carries in a real catalogue, chosen by a fixed priority:

1. SIMBAD main identifier: the reference name of the object in the
   literature (Wenger et al. 2000, A&AS 143, 9).
2. NED preferred name, then the Siena Galaxy Atlas name (Moustakas et al.
   2023, ApJS 269, 3): for galaxies these are the names used in the literature.
3. Survey designations, ordered roughly by sky coverage and astrometric
   precision: Gaia DR3 (Gaia Collaboration 2023), SDSS, Pan-STARRS1
   (Flewelling et al. 2020), Legacy Surveys DR10, 2MASS, AllWISE, DESI,
   GALEX, then the rest alphabetically.

Each name is the ``object_name`` the collector built from the catalogue's own
identifier columns (e.g. ``Gaia DR3 <source_id>``, ``PSO J188.4154+09.1750``).
When a catalogue contributes several detections to one object, the one with
the highest association confidence is used.
"""

from __future__ import annotations
import re
import numpy as np
import pandas as pd

PRIORITY = (
    "SIMBAD",
    "NED",
    "SGA-2020",
    "Gaia DR3",
    "SDSS DR18 PhotoObj",
    "Pan-STARRS1 DR2 MeanObject",
    "DESI Legacy Surveys DR10",
    "2MASS PSC",
    "AllWISE",
    "DESI DR1 spectroscopy",
    "SDSS DR18 spectroscopy",
    "GALEX AIS",
)


def clean_name(name: str, catalog: str = "") -> str:
    s = re.sub(r"\s+", " ", str(name)).strip()
    if catalog == "SIMBAD" and s.startswith("NAME "):
        s = s[5:]  # SIMBAD prefix for common names ("NAME Virgo Cluster")
    return s


def _rank(catalog: str) -> tuple[int, str]:
    try:
        return PRIORITY.index(catalog), catalog
    except ValueError:
        return len(PRIORITY), catalog


def designations(association: pd.DataFrame) -> pd.DataFrame:
    """One row per object_id: designation, designation_catalog, catalog_designations."""
    a = association[["object_id", "catalog", "catalog_object_id", "object_name", "association_confidence"]].copy()
    name = a.object_name.where(
        a.object_name.notna() & a.object_name.astype(str).str.strip().ne("") & a.object_name.astype(str).ne("nan"),
        a.catalog.astype(str) + " " + a.catalog_object_id.astype(str),
    )
    a["name"] = [clean_name(n, c) for n, c in zip(name, a.catalog.astype(str))]
    a["rank"] = [_rank(c)[0] for c in a.catalog.astype(str)]
    a["conf"] = pd.to_numeric(a.association_confidence, errors="coerce").fillna(0.0)
    a = a.sort_values(["object_id", "rank", "catalog", "conf"], ascending=[True, True, True, False], kind="stable")
    best = a.drop_duplicates("object_id")
    every = a.drop_duplicates(["object_id", "name"]).groupby("object_id", sort=False).name.agg("; ".join)
    out = pd.DataFrame(
        {
            "object_id": best.object_id.to_numpy(),
            "designation": best.name.to_numpy(),
            "designation_catalog": best.catalog.to_numpy(),
        }
    )
    out["catalog_designations"] = out.object_id.map(every)
    # Two objects can share a name when a catalogue entry is split (rare); keep labels unique.
    dup = out.designation.duplicated(keep=False)
    if dup.any():
        n = out[dup].groupby("designation").cumcount() + 1
        out.loc[dup, "designation"] = out.loc[dup, "designation"] + " [" + n.astype(str) + "]"
    return out


def angular_sep_arcmin(ra, dec, ra0: float, dec0: float) -> np.ndarray:
    """Great-circle separation (haversine) in arcmin."""
    r1, d1 = np.radians(np.asarray(ra, float)), np.radians(np.asarray(dec, float))
    r0, d0 = np.radians(ra0), np.radians(dec0)
    h = np.sin((d1 - d0) / 2) ** 2 + np.cos(d0) * np.cos(d1) * np.sin((r1 - r0) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))) * 60.0


def annotate(
    classified: pd.DataFrame,
    association: pd.DataFrame,
    center: tuple[float, float] | None = None,
    radius_arcmin: float | None = None,
) -> pd.DataFrame:
    """Add designation columns; with a centre, add separation_arcmin, keep only
    objects inside the radius (if given) and sort by distance from the centre.
    A kept component keeps its host galaxy (``parent_object_id``) even when
    the host centre lies outside the cone."""
    if "designation" in classified.columns and "catalog_designations" in classified.columns:
        out = classified.copy()  # already named (e.g. host-consolidated)
    else:
        out = classified.drop(
            columns=[
                c for c in ("designation", "designation_catalog", "catalog_designations") if c in classified.columns
            ]
        )
        out = out.merge(designations(association), on="object_id", how="left").copy()
        out["designation"] = out.designation.fillna(out.object_id)
    if center is not None:
        out["separation_arcmin"] = angular_sep_arcmin(out.ra, out.dec, *center)
        if radius_arcmin is not None:
            inside = out.separation_arcmin <= radius_arcmin
            if "parent_object_id" in out:
                hosts = set(out.loc[inside, "parent_object_id"].dropna())
                inside |= out.object_id.isin(hosts)
            out = out[inside]
        out = out.sort_values("separation_arcmin", kind="stable").reset_index(drop=True)
    return out
