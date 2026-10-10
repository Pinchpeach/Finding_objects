"""Independent Galactic-PN emission-line evidence from Acker et al. V/84.

A spatial query against V/84/main identifies a PN designation (PNG).  The
V/84/intens table is then queried by PNG to retrieve measured H/He/[O III]/[N II]/[S II]
line intensities.  This channel is separate from HASH and can support a PN
classification when HASH is unavailable.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
from _catalog_utils import pick, coordinates, add_standard_metadata

CATALOG = "Acker PN Spectroscopy"
MAIN = "V/84/main"
INTENS = "V/84/intens"
LINE_MAP = {
    "I4686": "pn_heii_4686",
    "I4363": "pn_oiii_4363",
    "I5007": "pn_oiii_5007",
    "I6563": "pn_halpha",
    "I6584": "pn_nii_6584",
    "I6717": "pn_sii_6717",
    "I6731": "pn_sii_6731",
}


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    v = Vizier(columns=["**"], row_limit=-1)
    tabs = v.query_region(
        SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs"),
        radius=float(radius_arcmin) * u.arcmin,
        catalog=MAIN,
    )
    if not tabs:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", *LINE_MAP.values()])
    main = tabs[0].to_pandas()
    if main.empty:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", *LINE_MAP.values()])
    pngc = pick(main, ["PNG"])
    if pngc is None:
        raise KeyError(f"V/84 main PNG missing; got {list(main.columns)}")
    raval, decval = coordinates(
        main,
        ["RAJ2000", "RA_ICRS", "_RAJ2000", "_RA.icrs", "RAB1950"],
        ["DEJ2000", "DE_ICRS", "_DEJ2000", "_DE.icrs", "DEB1950"],
    )
    records = []
    for idx, row in main.iterrows():
        png = str(row[pngc]).strip()
        if not png or png.lower() == "nan":
            continue
        try:
            detail = Vizier(columns=["**"], row_limit=-1).query_constraints(catalog=INTENS, PNG=png)
        except Exception:
            detail = []
        spectra = detail[0].to_pandas() if detail else pd.DataFrame()
        if spectra.empty:
            records.append(
                {
                    "catalog_object_id": png,
                    "object_name": "PNG " + png,
                    "ra": raval.loc[idx],
                    "dec": decval.loc[idx],
                    "pn_spectra_count": 0,
                }
            )
            continue
        # Robustly aggregate multiple historical spectra by median intensity.
        rec = {
            "catalog_object_id": png,
            "object_name": "PNG " + png,
            "ra": raval.loc[idx],
            "dec": decval.loc[idx],
            "pn_spectra_count": len(spectra),
        }
        for src, dst in LINE_MAP.items():
            col = pick(spectra, [src])
            if col is not None:
                vals = pd.to_numeric(spectra[col], errors="coerce").dropna()
                rec[dst] = float(vals.median()) if len(vals) else pd.NA
        records.append(rec)
    if not records:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec", *LINE_MAP.values()])
    out = pd.DataFrame(records)
    out.insert(0, "catalog", CATALOG)
    out = add_standard_metadata(
        out, radius_arcmin=radius_arcmin, ref_epoch=2000.0, poserr_arcsec=2.0, entity_kind="persistent_source"
    )
    return out.dropna(subset=["ra", "dec"]).drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)
