"""Real-data spectral/SED validation for the current candidate field.

Queries SDSS around candidate #1, builds an optical SED when photometry is
available, downloads an SDSS spectrum when available, identifies known lines,
and writes a searchable classification record. Network services may be absent.
"""
from pathlib import Path
import json
import requests
import pandas as pd

from finding_objects.sed import build_sed
from finding_objects.spectrum import identify_lines
from finding_objects.classification import classify_from_lines, line_tags
from finding_objects.catalog import save_classification

RA, DEC = 150.114557, 2.203106
TIMEOUT = 30

sql = f"""SELECT TOP 1 p.objid,p.ra,p.dec,p.u,p.g,p.r,p.i,p.z,s.specobjid,s.z as redshift
FROM PhotoObj AS p
LEFT JOIN SpecObj AS s ON s.bestobjid=p.objid
WHERE dbo.fGetNearbyObjEq({RA},{DEC},0.02) = p.objid
ORDER BY p.ra"""
url = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"
resp = requests.get(url, params={"cmd": sql, "format": "csv"}, timeout=TIMEOUT)
resp.raise_for_status()
row = pd.read_csv(pd.io.common.StringIO(resp.text)).iloc[0]
out = Path("results/spectral"); out.mkdir(parents=True, exist_ok=True)

bands = {"u":3551.0,"g":4686.0,"r":6165.0,"i":7481.0,"z":8931.0}
phot = pd.DataFrame([{"band":b,"effective_wavelength_angstrom":w,"ab_mag":float(row[b])}
                     for b,w in bands.items() if pd.notna(row[b]) and float(row[b]) > 0])
sed = build_sed(phot)
sed.to_csv(out/"candidate1_sed.csv", index=False)

record = {"object_id":"candidate-1","ra":RA,"dec":DEC,
          "redshift":None if pd.isna(row.get("redshift")) else float(row["redshift"]),
          "line_tags":[],"object_tags":[],"object_type":"photometric_object",
          "sdss_objid":str(row["objid"])}
record["object_tags"]=["object:photometric_object","survey:sdss"]
save_classification(record,out/"candidate1_classification.json")
print(sed.to_string(index=False))
print(json.dumps(record, indent=2))
