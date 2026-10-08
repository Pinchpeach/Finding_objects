#!/usr/bin/env python3
"""Stage 2: build one-row-per-object records from Stage-1 associations."""
from __future__ import annotations
import argparse, math, re
from pathlib import Path
import pandas as pd


def prefix(catalog):
    s = re.sub(r"[^a-z0-9]+", "_", str(catalog).lower()).strip("_")
    return s[:32] or "catalog"


def _first_valid(series):
    values = series.dropna()
    return values.iloc[0] if len(values) else pd.NA


def elliptical_radius(ra, dec, ra0, dec0, d26_arcmin, pa_deg=None, ba=None):
    """Distance from a galaxy centre in units of its D26 semi-major axis.

    PA is measured from North through East (SGA-2020 convention); a missing
    PA or axis ratio falls back to a circle.
    """
    dx = ((ra - ra0 + 180.0) % 360.0 - 180.0) * math.cos(math.radians(dec0)) * 60.0  # arcmin, East
    dy = (dec - dec0) * 60.0  # arcmin, North
    a = d26_arcmin / 2.0
    if a <= 0:
        return float("inf")
    if pa_deg is None or ba is None or not (0 < ba <= 1):
        return math.hypot(dx, dy) / a
    t = math.radians(pa_deg)
    major = dx * math.sin(t) + dy * math.cos(t)
    minor = dx * math.cos(t) - dy * math.sin(t)
    return math.hypot(major / a, minor / (a * ba))


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def flag_large_galaxy_hosts(rows):
    """Mark objects inside an SGA-2020 D26 ellipse that are not that galaxy."""
    hosts = [(r["object_id"], r["ra"], r["dec"], _num(r.get("sga_d26_arcmin")), _num(r.get("sga_pa_deg")),
              _num(r.get("sga_ba")), r.get("sga_2020__catalog_object_id"))
             for r in rows if "SGA-2020" in str(r.get("catalogs", "")).split("|")]
    for r in rows:
        best = (None, None)
        for oid, ra0, dec0, d26, pa, ba, name in hosts:
            if oid == r["object_id"] or d26 is None or _num(r["ra"]) is None:
                continue
            q = elliptical_radius(float(r["ra"]), float(r["dec"]), float(ra0), float(dec0), d26, pa, ba)
            if best[1] is None or q < best[1]:
                best = (name, q)
        r["host_large_galaxy"], r["host_elliptical_radius"] = best


def run(associations, raw_dir, out):
    assoc = pd.read_csv(associations, dtype={"catalog_object_id": "string"}, low_memory=False)
    raw_cache = {}
    rows = []
    for oid, g in assoc.groupby("object_id", sort=False):
        rec = {
            "object_id": oid,
            "ra": _first_valid(g["object_ra"]) if "object_ra" in g else g["ra"].mean(),
            "dec": _first_valid(g["object_dec"]) if "object_dec" in g else g["dec"].mean(),
            "ref_epoch": _first_valid(g["object_ref_epoch"]) if "object_ref_epoch" in g else pd.NA,
            "anchor_catalog": _first_valid(g["object_anchor_catalog"]) if "object_anchor_catalog" in g else pd.NA,
            "entity_kind": _first_valid(g["object_entity_kind"]) if "object_entity_kind" in g else "persistent_source",
            "association_members": len(g),
            "association_ambiguous": int((g["association_status"] == "ambiguous_new").any()),
            "association_confidence_min": pd.to_numeric(g.get("association_confidence"), errors="coerce").min(),
            "association_confidence_mean": pd.to_numeric(g.get("association_confidence"), errors="coerce").mean(),
            "association_probability_calibrated": False,
            "proper_motion_propagated_any": bool(g.get("proper_motion_propagated", pd.Series(False, index=g.index)).astype(bool).any()),
        }
        catalogs = []
        for _, a in g.iterrows():
            fn = a["input_file"]
            if fn not in raw_cache:
                try:
                    raw_cache[fn] = pd.read_csv(raw_dir / fn, dtype={"catalog_object_id": "string"}, low_memory=False)
                except Exception:
                    continue
            src = raw_cache[fn]
            idx = int(a["source_row"])
            if idx >= len(src):
                continue
            r = src.iloc[idx]
            cat = str(a["catalog"])
            catalogs.append(cat)
            pre = prefix(cat)
            rec[f"{pre}__catalog_object_id"] = a["catalog_object_id"]
            rec[f"association_confidence__{pre}"] = pd.to_numeric(pd.Series([a.get("association_confidence")]), errors="coerce").iloc[0]
            rec[f"association_separation_arcsec__{pre}"] = pd.to_numeric(pd.Series([a.get("match_separation_arcsec")]), errors="coerce").iloc[0]
            rec[f"association_chance_probability__{pre}"] = pd.to_numeric(pd.Series([a.get("chance_probability")]), errors="coerce").iloc[0]
            for col, val in r.items():
                if col in {"catalog", "catalog_object_id", "object_name", "ra", "dec"}:
                    continue
                # Every field is kept under its catalog namespace so rules can
                # read the value of the catalog they are about.  The bare name
                # is a legacy first-valid convenience shared by many catalogs
                # (e.g. ``type`` exists in both SDSS PhotoObj and DESI Legacy).
                rec[f"{pre}__{col}"] = val
                if col not in rec or pd.isna(rec[col]):
                    rec[col] = val
            for col in (
                "parallax", "parallax_error", "pmra", "pmra_error", "pmdec", "pmdec_error", "class", "zwarning",
                "classprob_dsc_combmod_quasar", "classprob_dsc_combmod_galaxy", "classprob_dsc_combmod_star",
                "classprob_dsc_combmod_whitedwarf", "classprob_dsc_combmod_binarystar", "best_class_name", "best_class_score",
                "event_mjd", "event_discovery_date", "sn_subtype", "pn_spectroscopic_score", "pn_spectroscopic_basis",
            ):
                if col in r and pd.notna(r[col]) and (col not in rec or pd.isna(rec[col])):
                    rec[col] = r[col]
        rec["catalogs"] = "|".join(sorted(set(catalogs)))
        rows.append(rec)
    flag_large_galaxy_hosts(rows)
    df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[OK] objects={len(df)} columns={len(df.columns)} -> {out}")
    return out


def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("--associations", type=Path, default=root / "source_association.csv")
    p.add_argument("--raw-dir", type=Path, default=root.parent / "rawdata")
    p.add_argument("--out", type=Path, default=root / "integrated_objects.csv")
    a = p.parse_args()
    run(a.associations, a.raw_dir, a.out)


if __name__ == "__main__":
    main()
