"""Retrieve Gaia DR3 SOS variability products as independent evidence.

The general ``vari_classifier_result`` table is useful for broad variable-star
families.  This collector preserves the more specific results from Gaia's
Specific Object Study (SOS) tables without inventing labels from colour or
temperature thresholds:

* RR Lyrae: published RRab/RRc/RRd classification and fitted time-series data;
* Cepheids: published type, subclass, and pulsation-mode classification;
* LPVs: period/amplitude measurements and the published C-star-candidate flag.

Mira is deliberately not inferred from LPV period or amplitude.  Gaia DR3
publishes LPV candidates and their measurements, but not a validated Mira leaf
label in this product.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from _catalog_utils import add_standard_metadata, coordinates, pick

CATALOG = "Gaia DR3 variability SOS"
TABLES = {
    "rr": ("I/358/vrrlyr", ["Source", "Class", "PF", "P1O", "ptpG", "RA_ICRS", "DE_ICRS"]),
    "cep": ("I/358/vcep", ["Source", "Class", "SubClass", "ModeClass", "PF", "P1O", "ptpG", "RA_ICRS", "DE_ICRS"]),
    "lpv": ("I/358/vlpv", ["Source", "Freq", "Amp", "isCstar", "RA_ICRS", "DE_ICRS"]),
}


def _number(df: pd.DataFrame, column: str | None) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce") if column else pd.Series(pd.NA, index=df.index, dtype="Float64")


def _text(df: pd.DataFrame, column: str | None) -> pd.Series:
    return df[column].astype("string") if column else pd.Series(pd.NA, index=df.index, dtype="string")


def _source_id(df: pd.DataFrame) -> pd.Series:
    source = pick(df, ["Source", "source_id"])
    if source is None:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    return pd.to_numeric(df[source], errors="coerce").astype("Int64").astype("string")


def _standard(df: pd.DataFrame, kind: str, radius_arcmin: float) -> pd.DataFrame:
    source = _source_id(df)
    ra, dec = coordinates(df, ["RA_ICRS", "RAJ2000", "_RAJ2000"], ["DE_ICRS", "DEJ2000", "_DEJ2000"])
    out = pd.DataFrame(
        {
            "catalog": CATALOG,
            "catalog_object_id": source,
            "object_name": "Gaia DR3 " + source,
            "ra": ra,
            "dec": dec,
            "gaia_variability_sos_kind": kind,
        }
    )
    return add_standard_metadata(
        out, radius_arcmin=radius_arcmin, ref_epoch=2016.0, poserr_arcsec=0.1, psf_fwhm_arcsec=0.18
    )


def _rr(df: pd.DataFrame, radius_arcmin: float) -> pd.DataFrame:
    out = _standard(df, "RR_LYRAE", radius_arcmin)
    out["gaia_rrlyrae_best_classification"] = _text(df, pick(df, ["Class", "best_classification"]))
    out["gaia_rrlyrae_pf"] = _number(df, pick(df, ["PF", "pf"]))
    out["gaia_rrlyrae_p1_o"] = _number(df, pick(df, ["P1O", "p1_o"]))
    out["gaia_rrlyrae_peak_to_peak_g"] = _number(df, pick(df, ["ptpG", "peak_to_peak_g"]))
    return out


def _cep(df: pd.DataFrame, radius_arcmin: float) -> pd.DataFrame:
    out = _standard(df, "CEPHEID", radius_arcmin)
    out["gaia_cepheid_best_classification"] = _text(df, pick(df, ["Class", "type_best_classification"]))
    out["gaia_cepheid_subclassification"] = _text(df, pick(df, ["SubClass", "type2_best_sub_classification"]))
    out["gaia_cepheid_mode_classification"] = _text(df, pick(df, ["ModeClass", "mode_best_classification"]))
    out["gaia_cepheid_pf"] = _number(df, pick(df, ["PF", "pf"]))
    out["gaia_cepheid_p1_o"] = _number(df, pick(df, ["P1O", "p1_o"]))
    out["gaia_cepheid_peak_to_peak_g"] = _number(df, pick(df, ["ptpG", "peak_to_peak_g"]))
    return out


def _lpv(df: pd.DataFrame, radius_arcmin: float) -> pd.DataFrame:
    out = _standard(df, "LPV", radius_arcmin)
    out["gaia_lpv_frequency"] = _number(df, pick(df, ["Freq", "frequency"]))
    out["gaia_lpv_amplitude"] = _number(df, pick(df, ["Amp", "amplitude"]))
    out["gaia_lpv_is_cstar"] = _number(df, pick(df, ["isCstar", "is_cstar"]))
    return out


PARSERS = {"rr": _rr, "cep": _cep, "lpv": _lpv}


def fetch(ra: float, dec: float, radius_arcmin: float, kinds: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Fetch the requested SOS products.

    ``kinds`` is an internal efficiency option for validation jobs.  Normal
    collection omits it and gathers all three products; a class-specific
    validation query can request only its relevant SOS table.
    """
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    centre = SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs")
    pieces: list[pd.DataFrame] = []
    requested = TABLES.keys() if kinds is None else tuple(kinds)
    unknown = set(requested) - set(TABLES)
    if unknown:
        raise ValueError(f"unknown Gaia SOS product(s): {sorted(unknown)}")
    for key in requested:
        table, columns = TABLES[key]
        tabs = Vizier(columns=columns, row_limit=-1).query_region(
            centre, radius=float(radius_arcmin) * u.arcmin, catalog=table
        )
        if tabs:
            frame = tabs[0].to_pandas()
            if not frame.empty:
                pieces.append(PARSERS[key](frame, radius_arcmin))
    if not pieces:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    out = pd.concat(pieces, ignore_index=True, sort=False)
    return (
        out.dropna(subset=["catalog_object_id", "ra", "dec"])
        .drop_duplicates(["catalog_object_id", "gaia_variability_sos_kind"], keep="last")
        .reset_index(drop=True)
    )


def save(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
