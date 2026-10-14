"""Small normalization helpers shared by VizieR-backed collectors."""
from __future__ import annotations
import math
import pandas as pd


def pick(df: pd.DataFrame, names):
    low={str(c).lower():c for c in df.columns}
    for name in names:
        if name in df.columns:return name
        if str(name).lower() in low:return low[str(name).lower()]
    return None


def numeric(series):
    return pd.to_numeric(series,errors="coerce")


def coordinates(df: pd.DataFrame, ra_names, dec_names):
    """Return decimal-degree coordinates, accepting numeric or sexagesimal columns."""
    rac=pick(df,ra_names); decc=pick(df,dec_names)
    if rac is None or decc is None:
        raise KeyError(f"coordinate columns missing; got {list(df.columns)}")
    ra=numeric(df[rac]); dec=numeric(df[decc])
    missing=ra.isna()|dec.isna()
    if missing.any():
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        for idx in df.index[missing]:
            rv,dv=df.at[idx,rac],df.at[idx,decc]
            if pd.isna(rv) or pd.isna(dv):continue
            try:
                text_ra=str(rv).strip(); text_dec=str(dv).strip()
                # RA strings containing separators are normally hour angle in VizieR.
                unit_ra=u.hourangle if any(x in text_ra for x in (":"," ")) else u.deg
                c=SkyCoord(text_ra,text_dec,unit=(unit_ra,u.deg),frame="icrs")
                ra.at[idx]=float(c.ra.deg); dec.at[idx]=float(c.dec.deg)
            except Exception:
                pass
    return ra,dec


def add_standard_metadata(df:pd.DataFrame, *, radius_arcmin:float, ref_epoch=None,
                          poserr_arcsec=None, psf_fwhm_arcsec=None,
                          entity_kind="persistent_source"):
    out=df.copy()
    out["query_radius_arcmin"]=float(radius_arcmin)
    if ref_epoch is not None:out["ref_epoch"]=ref_epoch
    if poserr_arcsec is not None:out["poserr_arcsec"]=poserr_arcsec
    if psf_fwhm_arcsec is not None:out["psf_fwhm_arcsec"]=psf_fwhm_arcsec
    out["entity_kind"]=entity_kind
    return out


def julian_year_from_mjd(value):
    try:
        x=float(value)
        if not math.isfinite(x):return None
        return 2000.0+(x-51544.5)/365.25
    except Exception:return None


SDSS_MAX_CONE_ARCMIN = 3.0


def sdss_region(ra: float, dec: float, radius_arcmin: float, **kwargs):
    """``SDSS.query_region`` for any radius (2.23.0).

    astroquery's SDSS cone (cross-ID) mode refuses radii above 3 arcmin, so
    every larger field lost all SDSS photometry and spectra.  Above that, a
    rectangle covering the cone is queried (RA width widened by 1/cos(dec);
    astroquery's rectangle does not) and the rows are cut back to the cone.
    """
    import math

    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.sdss import SDSS

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
