"""Print the columns of the spectroscopic catalogue products the classifier
could use (run in GitHub Actions; the archives are not reachable from every
environment).  Output goes to the job log only."""
from astroquery.vizier import Vizier

for cat in ("V/164/dr5", "V/164/stellar5", "V/164/mstars5", "V/164/astars5",
            "I/355/paramp", "I/355/paramsup", "I/358/vlpv", "V/161/zcatdr1"):
    try:
        res = Vizier(columns=["**"], row_limit=2, timeout=300).get_catalogs(cat)
        for t in res:
            print(f"== {cat} -> {t.meta.get('name', '')}: {len(t.colnames)} columns")
            print("   " + " ".join(t.colnames))
    except Exception as exc:
        print(f"== {cat}: {type(exc).__name__}: {str(exc)[:200]}")
try:
    for k, v in Vizier.find_catalogs("LAMOST DR").items():
        print("LAMOST catalogue:", k, "|", v.description[:100])
except Exception as exc:
    print("find_catalogs failed", exc)
try:
    from astroquery.gaia import Gaia
    t = Gaia.load_table("gaiadr3.astrophysical_parameters")
    names = [c.name for c in t.columns]
    print("gaiadr3.astrophysical_parameters:", len(names), "columns")
    print("   " + " ".join(n for n in names if any(k in n for k in ("espels", "gspspec", "esphs", "spectraltype", "classlabel", "flags"))))
except Exception as exc:
    print("Gaia table metadata failed", exc)
