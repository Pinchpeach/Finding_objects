"""Fetch reference tables and column lists for the 2.22.0 target additions.

Run from GitHub Actions (the development container has no archive access).
Writes into the directory given by --out:
  simbad_otypedef.csv   full SIMBAD object-type table (code hierarchy)
  probe.txt             VizieR table / column lists of the truth catalogues
                        and the Gaia DR3 ESP-UCD columns
"""

from __future__ import annotations
import argparse, sys, traceback
from pathlib import Path

CATALOGS = {
    "J/A+A/662/A40": "Culpan+2022 hot subluminous stars (EDR3) + known hot subdwarfs",
    "J/A+A/621/A38": "Geier+2019 hot subluminous star candidates (DR2)",
    "VII/274": "Roma-BZCAT 5th edition (Massaro+2015)",
    "J/ApJS/263/24": "4LAC-DR3 (Ajello+2022)",
    "J/ApJS/242/4": "WIBRaLS2 / KDEBLLACS (D'Abrusco+2019)",
    "J/ApJS/254/33": "SPICY YSO candidates (Kuhn+2021)",
    "J/MNRAS/487/2522": "Marton+2019 Gaia DR2 x AllWISE YSO probabilities",
    "J/ApJS/234/1": "Best+2018 PS1 M/L/T dwarfs",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "probe.txt", "w", encoding="utf-8")

    def say(*x):
        print(*x, file=log, flush=True)
        print(*x, flush=True)

    try:
        from astroquery.simbad import Simbad

        od = Simbad().query_tap("SELECT * FROM otypedef").to_pandas()
        od.to_csv(out / "simbad_otypedef.csv", index=False)
        say("otypedef", od.shape, list(od.columns))
    except Exception:
        say("otypedef ERROR", traceback.format_exc())

    from astroquery.vizier import Vizier

    for cat, desc in CATALOGS.items():
        say(f"\n=== {cat}  {desc}")
        try:
            meta = Vizier(columns=["**"], row_limit=3).get_catalogs(cat)
            for name in meta.keys():
                t = meta[name]
                say(f"  table {name}  rows(sample)={len(t)}")
                for c in t.colnames:
                    say(f"    {c:24s} | {str(t[c].unit):10s} | {(t[c].description or '')[:90]}")
                say("   sample:", [dict(zip(t.colnames, map(str, r))) for r in t[:2]])
        except Exception:
            say("  ERROR", traceback.format_exc()[-800:])
        try:
            cats = Vizier.find_catalogs(cat.split("/")[-1] if cat.startswith("J/") else cat)
            say("  find:", [(k, (v.description or "")[:70]) for k, v in list(cats.items())[:5]])
        except Exception as exc:
            say("  find ERROR", repr(exc))

    try:
        from astroquery.gaia import Gaia

        t = Gaia.load_table("gaiadr3.astrophysical_parameters")
        cols = [c.name for c in t.columns]
        say("\n=== gaiadr3.astrophysical_parameters ESP-UCD columns:", [c for c in cols if "ucd" in c.lower()])
        j = Gaia.launch_job(
            "SELECT TOP 5 source_id, teff_espucd, flags_espucd FROM gaiadr3.astrophysical_parameters WHERE teff_espucd IS NOT NULL"
        )
        say(j.get_results())
    except Exception:
        say("gaia ERROR", traceback.format_exc()[-800:])
    log.close()


if __name__ == "__main__":
    sys.exit(main())
