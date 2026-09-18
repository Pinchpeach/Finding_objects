"""Real-data SDSS SED validation with independent, retryable queries."""
from pathlib import Path
from io import StringIO
import json
import time
import requests
import pandas as pd

from finding_objects.sed import build_sed
from finding_objects.catalog import save_classification

RA, DEC = 150.114557, 2.203106
TIMEOUT = 30
# Previous SDSS real-data attempt failed, so adaptive budget is 5 retries.
RETRIES = 5
BACKOFF = 1.0
BASE = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"


def sdss_sql(sql: str, retries: int = RETRIES) -> pd.DataFrame:
    """Run one SDSS query with bounded exponential backoff."""
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(BASE, params={"cmd": sql, "format": "csv"}, timeout=TIMEOUT)
            r.raise_for_status()
            return pd.read_csv(StringIO(r.text))
        except (requests.RequestException, pd.errors.ParserError) as exc:
            last = exc
            if attempt >= retries:
                break
            time.sleep(BACKOFF * (2 ** attempt))
    raise RuntimeError(f"SDSS query failed after {retries + 1} attempts") from last


out = Path("results/spectral")
out.mkdir(parents=True, exist_ok=True)

# 1) Photometry is deliberately independent of spectroscopy.
photo_sql = f"""SELECT TOP 1 p.objid,p.ra,p.dec,p.u,p.g,p.r,p.i,p.z
FROM dbo.fGetNearbyObjEq({RA},{DEC},0.02) AS n
JOIN PhotoObj AS p ON p.objid=n.objid
ORDER BY n.distance"""
photo = sdss_sql(photo_sql)
if photo.empty:
    raise RuntimeError("No SDSS photometric counterpart found")
row = photo.iloc[0]

bands = {"u":3551.0,"g":4686.0,"r":6165.0,"i":7481.0,"z":8931.0}
phot = pd.DataFrame([
    {"band": b, "effective_wavelength_angstrom": w, "ab_mag": float(row[b])}
    for b, w in bands.items() if pd.notna(row[b]) and float(row[b]) > 0
])
sed = build_sed(phot)
sed.to_csv(out / "candidate1_sed.csv", index=False)

# 2) Spectroscopy is optional. Its failure must not destroy a valid SED result.
spec = pd.DataFrame()
spec_error = None
try:
    spec_sql = f"""SELECT TOP 1 s.specobjid,s.z as redshift,s.class,s.subclass
FROM SpecObj AS s
WHERE s.bestobjid={int(row['objid'])}"""
    spec = sdss_sql(spec_sql)
except Exception as exc:
    spec_error = str(exc)

has_spec = not spec.empty
record = {
    "object_id": "candidate-1",
    "ra": RA, "dec": DEC,
    "sdss_objid": str(row["objid"]),
    "object_type": "sdss_spectroscopic_object" if has_spec else "photometry_only",
    "redshift": float(spec.iloc[0]["redshift"]) if has_spec and pd.notna(spec.iloc[0]["redshift"]) else None,
    "line_tags": [],
    "object_tags": ["survey:sdss", "object:sdss_spectroscopic_object" if has_spec else "object:photometry_only"],
    "spectrum_status": "available" if has_spec else ("no_response" if spec_error else "not_observed"),
}
if has_spec:
    record["sdss_class"] = str(spec.iloc[0]["class"])
    record["sdss_subclass"] = str(spec.iloc[0]["subclass"])
if spec_error:
    record["spectrum_error"] = spec_error

save_classification(record, out / "candidate1_classification.json")
print(sed.to_string(index=False))
print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
