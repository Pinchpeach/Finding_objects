"""Independent Galactic-PN emission-line evidence from Acker et al. V/84.

A spatial query against V/84/main identifies a PN designation (PNG).  The
V/84/intens table is then queried by PNG to retrieve measured H/He/[O III]/[N II]/[S II]
line intensities.  This channel is separate from HASH and can support a PN
classification when HASH is unavailable.
"""

from __future__ import annotations
import pandas as pd
from _catalog_utils import add_standard_metadata, coordinates, empty_frame, pick, save_csv, vizier_cone

save = save_csv  # collector API: save(df, path)

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

    main = vizier_cone(MAIN, ra, dec, radius_arcmin)
    if main is None or main.empty:
        return empty_frame(*LINE_MAP.values())
    pngc = pick(main, ["PNG"])
    if pngc is None:
        raise KeyError(f"V/84 main PNG missing; got {list(main.columns)}")
    # coordinates() reads every candidate as ICRS/J2000, so the B1950 columns
    # (RAB1950/DEB1950, FK4) are not candidates: a fallback to them would put
    # the PN about 0.7 deg off (50 years of precession).
    raval, decval = coordinates(
        main, ["RAJ2000", "RA_ICRS", "_RAJ2000", "_RA.icrs"], ["DEJ2000", "DE_ICRS", "_DEJ2000", "_DE.icrs"]
    )
    records = []
    for idx, row in main.iterrows():
        png = str(row[pngc]).strip()
        if not png or png.lower() == "nan":
            continue
        rec = {"catalog_object_id": png, "object_name": "PNG " + png, "ra": raval.loc[idx], "dec": decval.loc[idx]}
        records.append(rec)
        try:
            detail = Vizier(columns=["**"], row_limit=-1).query_constraints(catalog=INTENS, PNG=png)
        except Exception as exc:
            # Unknown, not "no spectra": a failed query must not read as zero (2.23.0).
            rec.update(pn_spectra_count=pd.NA, pn_query_status=f"error:{type(exc).__name__}")
            continue
        spectra = detail[0].to_pandas() if detail else pd.DataFrame()
        rec["pn_spectra_count"] = len(spectra)
        if spectra.empty:
            continue
        # Robustly aggregate multiple historical spectra by median intensity.
        for src, dst in LINE_MAP.items():
            col = pick(spectra, [src])
            if col is not None:
                vals = pd.to_numeric(spectra[col], errors="coerce").dropna()
                rec[dst] = float(vals.median()) if len(vals) else pd.NA
    if not records:
        return empty_frame(*LINE_MAP.values())
    out = pd.DataFrame(records)
    out.insert(0, "catalog", CATALOG)
    out = add_standard_metadata(
        out, radius_arcmin=radius_arcmin, ref_epoch=2000.0, poserr_arcsec=2.0, entity_kind="persistent_source"
    )
    return out.dropna(subset=["ra", "dec"]).drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)
