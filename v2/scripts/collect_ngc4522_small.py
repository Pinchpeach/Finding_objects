"""Small NGC 4522 integration collection test."""
from pathlib import Path
import importlib.util
import traceback

import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u

RA = 188.4155
DEC = 9.1751
RADIUS_ARCMIN = 0.5

ROOT = Path(__file__).resolve().parents[1]
GET = ROOT / "Get_data"
OUT = ROOT / "rawdata"
OUT.mkdir(exist_ok=True)

modules = [
    "gaia_dr3", "sdss_dr18", "panstarrs1", "desi_legacy", "galex",
    "twomass", "allwise", "lotss", "first", "nvss", "vlass", "xmm",
    "chandra", "erosita", "sdss_spectroscopy", "desi_spectroscopy",
    "lamost_spectroscopy", "simbad", "ned",
]

summary = []
center = SkyCoord(RA * u.deg, DEC * u.deg)

for name in modules:
    try:
        spec = importlib.util.spec_from_file_location(name, GET / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        df = module.fetch(RA, DEC, RADIUS_ARCMIN)
        path = OUT / f"{name}_ngc4522_r0p5arcmin.csv"
        module.save(df, path)

        maxsep = None
        if len(df) and {"ra", "dec"}.issubset(df.columns):
            ra = pd.to_numeric(df["ra"], errors="coerce")
            dec = pd.to_numeric(df["dec"], errors="coerce")
            valid = ra.notna() & dec.notna()
            if valid.any():
                coords = SkyCoord(
                    ra.loc[valid].to_numpy() * u.deg,
                    dec.loc[valid].to_numpy() * u.deg,
                )
                maxsep = float(center.separation(coords).arcmin.max())

        status = (
            "ok"
            if maxsep is None or maxsep <= RADIUS_ARCMIN + 1e-6
            else "radius_error"
        )
        summary.append({
            "collector": name,
            "status": status,
            "rows": len(df),
            "max_sep_arcmin": maxsep,
            "file": str(path.relative_to(ROOT)),
            "error": "",
        })
    except Exception as exc:
        summary.append({
            "collector": name,
            "status": "error",
            "rows": 0,
            "max_sep_arcmin": None,
            "file": "",
            "error": repr(exc),
        })
        traceback.print_exc()

summary_df = pd.DataFrame(summary)
summary_df.to_csv(OUT / "ngc4522_r0p5arcmin_summary.csv", index=False)
print(summary_df.to_string(index=False))
