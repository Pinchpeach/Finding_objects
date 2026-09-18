from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import numpy as np
import pandas as pd
import requests
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astroquery.gaia import Gaia
from astroquery.vizier import Vizier
from photutils.detection import DAOStarFinder

LEGACY_FITS_URL = "https://www.legacysurvey.org/viewer/fits-cutout"


@dataclass
class RunConfig:
    ra: float
    dec: float
    size: int = 256
    pixscale: float = 0.262
    band: str = "r"
    detection_sigma: float = 5.0
    gaia_match_arcsec: float = 1.0
    high_snr: float = 10.0
    data_dir: Path = Path("data")
    network_timeout: float = 30.0


def download_legacy_cutout(cfg: RunConfig, run_id: str) -> Path:
    out = cfg.data_dir / "raw"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run_id}_legacy_{cfg.band}.fits"
    params = {"ra": cfg.ra, "dec": cfg.dec, "size": cfg.size,
              "pixscale": cfg.pixscale, "bands": cfg.band}
    response = requests.get(LEGACY_FITS_URL, params=params, timeout=cfg.network_timeout)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def detect_sources(path: Path, cfg: RunConfig) -> pd.DataFrame:
    with fits.open(path) as hdul:
        data = np.squeeze(np.asarray(hdul[0].data, dtype=float))
        header = hdul[0].header
    if data.ndim != 2:
        raise ValueError(f"Expected 2-D FITS image; got {data.shape}")
    finite = np.isfinite(data)
    if not finite.any():
        raise ValueError("FITS image has no finite pixels")
    _, median, std = sigma_clipped_stats(data[finite], sigma=3.0)
    if not np.isfinite(std) or std <= 0:
        raise ValueError("Could not estimate a positive background noise")
    clean = np.where(finite, data, median)
    table = DAOStarFinder(fwhm=3.0, threshold=cfg.detection_sigma * std)(clean - median)
    cols = ["source_id", "x", "y", "flux", "snr", "sharpness",
            "roundness1", "ra", "dec"]
    if table is None or len(table) == 0:
        return pd.DataFrame(columns=cols)

    from astropy.wcs import WCS
    sky = WCS(header).celestial.pixel_to_world(
        np.asarray(table["xcentroid"], dtype=float),
        np.asarray(table["ycentroid"], dtype=float),
    )
    flux = np.asarray(table["flux"], dtype=float)
    # Approximate detection S/N for triage, not calibrated survey photometry.
    npix_eff = np.pi * (3.0 / 2.355) ** 2
    snr = flux / (std * np.sqrt(npix_eff))
    return pd.DataFrame({
        "source_id": np.arange(1, len(table) + 1),
        "x": np.asarray(table["xcentroid"], dtype=float),
        "y": np.asarray(table["ycentroid"], dtype=float),
        "flux": flux, "snr": snr,
        "sharpness": np.asarray(table["sharpness"], dtype=float),
        "roundness1": np.asarray(table["roundness1"], dtype=float),
        "ra": sky.ra.deg, "dec": sky.dec.deg,
    })


def crossmatch_gaia(sources: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    Gaia.TIMEOUT = cfg.network_timeout
    result = sources.copy()
    result["gaia_source_id"] = pd.Series(index=result.index, dtype="string")
    result["gaia_sep_arcsec"] = np.nan
    if result.empty:
        return result
    center = SkyCoord(cfg.ra * u.deg, cfg.dec * u.deg)
    radius = (cfg.size * cfg.pixscale / 2 + 5) * u.arcsec
    gaia = Gaia.cone_search_async(center, radius=radius).get_results()
    if len(gaia) == 0:
        return result
    detected = SkyCoord(result.ra.to_numpy() * u.deg, result.dec.to_numpy() * u.deg)
    catalog = SkyCoord(np.asarray(gaia["ra"]) * u.deg, np.asarray(gaia["dec"]) * u.deg)
    idx, sep, _ = detected.match_to_catalog_sky(catalog)
    matched = sep <= cfg.gaia_match_arcsec * u.arcsec
    result.loc[matched, "gaia_source_id"] = [str(gaia["source_id"][i]) for i in idx[matched]]
    result.loc[matched, "gaia_sep_arcsec"] = sep[matched].arcsec
    return result


def crossmatch_vizier(sources: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    """Cross-match against selected non-Gaia catalogues for candidate triage."""
    result = sources.copy()
    result["vizier_catalog"] = pd.Series(index=result.index, dtype="string")
    result["vizier_sep_arcsec"] = np.nan
    if result.empty:
        return result

    catalogs = {
        "Pan-STARRS_DR1": "II/349/ps1",
        "SDSS_DR16": "V/154/sdss16",
        "AllWISE": "II/328/allwise",
    }
    Vizier.TIMEOUT = cfg.network_timeout
    vizier = Vizier(columns=["*", "+_r"], row_limit=50)
    for i, row in result.iterrows():
        coord = SkyCoord(float(row.ra) * u.deg, float(row.dec) * u.deg)
        for name, catalog in catalogs.items():
            try:
                tables = vizier.query_region(
                    coord, radius=cfg.gaia_match_arcsec * u.arcsec,
                    catalog=catalog,
                )
            except Exception:
                continue
            if not tables or len(tables[0]) == 0:
                continue
            table = tables[0]
            if "_r" in table.colnames:
                j = int(np.nanargmin(np.asarray(table["_r"], dtype=float)))
                sep = float(table["_r"][j])
            else:
                j, sep = 0, np.nan
            result.at[i, "vizier_catalog"] = name
            result.at[i, "vizier_sep_arcsec"] = sep
            break
    return result


def label_candidates(sources: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    result = sources.copy()
    matched = result["gaia_sep_arcsec"].notna()
    result["candidate_label"] = np.where(matched, "gaia_matched", "unmatched_source")
    result.loc[(~matched) & (result["snr"] >= cfg.high_snr), "candidate_label"] = "high_snr_unmatched"
    result["survey"] = "DESI Legacy Surveys"
    result["band"] = cfg.band
    return result


def run_pipeline(cfg: RunConfig) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}_ra{cfg.ra:.5f}_dec{cfg.dec:+.5f}"
    sources = detect_sources(download_legacy_cutout(cfg, run_id), cfg)
    sources = crossmatch_gaia(sources, cfg)
    sources = crossmatch_vizier(sources, cfg)
    sources = label_candidates(sources, cfg)
    sources.insert(0, "run_id", run_id)
    out = cfg.data_dir / "candidates"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run_id}_candidates.csv"
    sources.to_csv(path, index=False)
    return path
