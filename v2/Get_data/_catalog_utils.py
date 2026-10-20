"""Small normalization helpers shared by VizieR-backed collectors."""

from __future__ import annotations
import math
from pathlib import Path
import pandas as pd

import throttle

throttle.install()  # 3-5 s before every archive request (2.33.0), also for scripts that import the collectors directly

# Leading columns of every collector's output, in this order.
BASE = ["catalog", "catalog_object_id", "object_name", "ra", "dec"]


def empty_frame(*extra) -> pd.DataFrame:
    """No rows: the base columns plus a collector's own ``extra`` columns."""
    return pd.DataFrame(columns=[*BASE, *extra])


def vizier_query(catalog: str, ra: float, dec: float, radius_arcmin: float, columns=("**",)):
    """VizieR cone search of ``catalog`` with every row (``row_limit=-1``); the TableList."""
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    return Vizier(columns=list(columns), row_limit=-1).query_region(
        SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs"),
        radius=float(radius_arcmin) * u.arcmin,
        catalog=catalog,
    )


def vizier_cone(catalog: str, ra: float, dec: float, radius_arcmin: float, columns=("**",)):
    """First table of :func:`vizier_query` as a DataFrame, or None when VizieR returns nothing."""
    tables = vizier_query(catalog, ra, dec, radius_arcmin, columns)
    return tables[0].to_pandas() if tables else None


def with_base(df: pd.DataFrame, catalog, ident, name, ra, dec) -> pd.DataFrame:
    """Insert the BASE columns in front of ``df`` (in place) and keep the last
    row of each ``catalog_object_id``."""
    for i, (col, value) in enumerate(zip(BASE, (catalog, ident, name, ra, dec))):
        df.insert(i, col, value)
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def id_cone(
    catalog: str, vizier_catalog: str, id_columns, ra_columns, dec_columns, ra: float, dec: float, radius_arcmin: float
) -> pd.DataFrame:
    """Cone search whose identifier and coordinates are picked from candidate
    column lists; the identifier is also the object name."""
    df = vizier_cone(vizier_catalog, ra, dec, radius_arcmin)
    if df is None:
        return empty_frame()
    idc = pick(df, id_columns)
    if idc is None:
        raise KeyError(f"identifier column missing (tried {id_columns}); got {list(df.columns)[:20]}")
    rv, dv = coordinates(df, ra_columns, dec_columns)
    ident = df[idc].astype("string").str.strip()
    return with_base(df, catalog, ident, ident, numeric(rv), numeric(dv))


def save_csv(df: pd.DataFrame, path, label: str | None = None, required=BASE) -> None:
    """Write one row per ``catalog_object_id``; with ``label``, first check
    that the ``required`` columns are present."""
    if label is not None and not set(required).issubset(df.columns):
        raise ValueError(f"invalid {label} output")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)


def pick(df: pd.DataFrame, names):
    low = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name in df.columns:
            return name
        if str(name).lower() in low:
            return low[str(name).lower()]
    return None


def unique_positions(df: pd.DataFrame, radius_arcsec: float, quality=None) -> pd.DataFrame:
    """Keep one row per position: rows are taken best ``quality`` first and a
    row within ``radius_arcsec`` of a kept row is dropped.  (A rounded-grid
    key splits pairs that straddle a cell edge.)"""
    import numpy as np

    if len(df) < 2:
        return df
    q = pd.Series(0.0, index=df.index) if quality is None else pd.to_numeric(quality, errors="coerce").fillna(-np.inf)
    d = df.loc[q.sort_values(ascending=False, kind="stable").index]
    ra, dec = np.radians(d["ra"].to_numpy(float)), np.radians(d["dec"].to_numpy(float))
    xyz = np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], axis=1)
    lim = math.cos(math.radians(radius_arcsec / 3600.0))
    kept = []
    for i in range(len(d)):
        if not np.isfinite(xyz[i]).all() or not kept or (xyz[kept] @ xyz[i]).max() < lim:
            kept.append(i)
    return d.iloc[sorted(kept)]


def numeric(series):
    return pd.to_numeric(series, errors="coerce")


def coordinates(df: pd.DataFrame, ra_names, dec_names):
    """Return decimal-degree coordinates, accepting numeric or sexagesimal columns."""
    rac = pick(df, ra_names)
    decc = pick(df, dec_names)
    if rac is None or decc is None:
        raise KeyError(f"coordinate columns missing; got {list(df.columns)}")
    ra = numeric(df[rac])
    dec = numeric(df[decc])
    missing = ra.isna() | dec.isna()
    if missing.any():
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        for idx in df.index[missing]:
            rv, dv = df.at[idx, rac], df.at[idx, decc]
            if pd.isna(rv) or pd.isna(dv):
                continue
            try:
                text_ra = str(rv).strip()
                text_dec = str(dv).strip()
                # RA strings containing separators are normally hour angle in VizieR.
                unit_ra = u.hourangle if any(x in text_ra for x in (":", " ")) else u.deg
                c = SkyCoord(text_ra, text_dec, unit=(unit_ra, u.deg), frame="icrs")
                ra.at[idx] = float(c.ra.deg)
                dec.at[idx] = float(c.dec.deg)
            except Exception:
                pass
    return ra, dec


def add_standard_metadata(
    df: pd.DataFrame,
    *,
    radius_arcmin: float,
    ref_epoch=None,
    poserr_arcsec=None,
    psf_fwhm_arcsec=None,
    entity_kind="persistent_source",
):
    out = df.copy()
    out["query_radius_arcmin"] = float(radius_arcmin)
    if ref_epoch is not None:
        out["ref_epoch"] = ref_epoch
    if poserr_arcsec is not None:
        out["poserr_arcsec"] = poserr_arcsec
    if psf_fwhm_arcsec is not None:
        out["psf_fwhm_arcsec"] = psf_fwhm_arcsec
    out["entity_kind"] = entity_kind
    return out


def j2000_degrees(df: pd.DataFrame):
    """VizieR gives the NVSS / FIRST RAJ2000/DEJ2000 as sexagesimal strings
    ("00 34 08.71"); pd.to_numeric made them NaN and every source was dropped
    before association.  Use VizieR's computed decimal _RAJ2000/_DEJ2000, else
    parse the sexagesimal columns."""
    if "_RAJ2000" in df and "_DEJ2000" in df:
        ra = pd.to_numeric(df["_RAJ2000"], errors="coerce")
        dec = pd.to_numeric(df["_DEJ2000"], errors="coerce")
        if ra.notna().all() and dec.notna().all():
            return ra, dec
    ra = pd.to_numeric(df["RAJ2000"], errors="coerce")
    dec = pd.to_numeric(df["DEJ2000"], errors="coerce")
    if len(df) and (ra.isna().any() or dec.isna().any()):
        # Row by row (2.23.0): one empty or malformed value made the bulk
        # SkyCoord parse raise and the whole collector fail.
        ra, dec = coordinates(df, ["RAJ2000"], ["DEJ2000"])
    return ra, dec


SDSS_MAX_CONE_ARCMIN = 3.0


def _sdss():
    """astroquery's SDSS client with full-precision rectangle bounds (2.33.0).

    astroquery writes the rectangle's RA/Dec limits with ``{:g}`` (six
    significant digits): at RA 245 a limit moves by up to 0.0005 deg (1.8"),
    and a limit near 0 is written in exponent notation.  Same SQL, written to
    1e-8 deg.
    """
    from astroquery.sdss.core import SDSSClass

    class FullPrecisionSDSS(SDSSClass):
        def _rectangle_sql(self, ra, dec, width, height=None):
            height = width if height is None else height
            d0, d1 = max(dec - height / 2.0, -90.0), min(dec + height / 2.0, 90.0)
            r0, r1 = ra - width / 2.0, ra + width / 2.0
            wrap = r0 < 0 or r1 > 360.0
            r0, r1 = (r0 + 360.0 if r0 < 0 else r0), (r1 - 360.0 if r1 > 360.0 else r1)
            ra_sql = f"((p.ra >= {r0:.8f}) OR (p.ra <= {r1:.8f}))" if wrap else f"(p.ra BETWEEN {r0:.8f} AND {r1:.8f})"
            return f"({ra_sql} AND (p.dec BETWEEN {d0:.8f} AND {d1:.8f}))"

    return FullPrecisionSDSS()


def sdss_region(ra: float, dec: float, radius_arcmin: float, **kwargs):
    """``SDSS.query_region`` for any radius (2.23.0).

    astroquery's SDSS cone (cross-ID) mode refuses radii above 3 arcmin, so
    every larger field lost all SDSS photometry and spectra.  Above that, a
    rectangle covering the cone is queried (RA width widened by 1/cos(dec);
    astroquery's rectangle does not) and the rows are cut back to the cone.
    """
    import astropy.units as u
    from astropy.coordinates import SkyCoord

    SDSS = _sdss()
    pos = SkyCoord(ra=float(ra) * u.deg, dec=float(dec) * u.deg, frame="icrs")
    if radius_arcmin <= SDSS_MAX_CONE_ARCMIN:
        return SDSS.query_region(pos, radius=radius_arcmin * u.arcmin, **kwargs)
    r_deg = radius_arcmin / 60.0
    cosd = math.cos(math.radians(min(abs(dec) + r_deg, 89.999)))
    width = min(2 * r_deg / cosd, 360.0)
    t = SDSS.query_region(pos, width=width * u.deg, height=2 * r_deg * u.deg, **kwargs)
    if t is None or len(t) == 0:
        return t
    sep = pos.separation(SkyCoord(ra=t["ra"], dec=t["dec"], unit="deg", frame="icrs")).arcmin
    return t[sep <= radius_arcmin]
