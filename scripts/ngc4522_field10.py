"""NGC 4522 +/-10 arcmin field census and conservative final tree classification.
Primary optical census: SDSS DR18 PhotoObj in a 10' radius-equivalent rectangular field,
augmented by Gaia DR3 astrometry and SDSS spectroscopy when available.
All classifications retain UNKNOWN rather than inventing missing evidence.
"""
from __future__ import annotations
import io,json,math,pathlib,time,requests
import numpy as np,pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.gaia import Gaia
from finding_objects.decision_tree import identity_tree

OUT=pathlib.Path("results/ngc4522_field10"); OUT.mkdir(parents=True,exist_ok=True)
# NGC 4522 J2000 center; field is +/-10 arcmin in Dec and RA projected on sky.
RA0=188.4155; DEC0=9.1751; HALF=10/60
COS=math.cos(math.radians(DEC0)); RA_HALF=HALF/COS
SDSS="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

def sql(q,tries=4):
    # SkyServerWS is returning '#Table1' instead of a usable CSV for this query.
    # Use CasJobs-compatible JSON output first; parse table payload defensively.
    params={"cmd":q,"format":"json"}
    last=None
    for k in range(tries):
        try:
            r=requests.get(SDSS,params=params,headers={"User-Agent":"Finding_objects/1.0"},timeout=120)
            r.raise_for_status(); last=r
            obj=r.json()
            if isinstance(obj,list):
                # SkyServer JSON commonly returns table descriptors with Rows.
                if obj and isinstance(obj[0],dict) and "Rows" in obj[0]:
                    return pd.DataFrame(obj[0]["Rows"])
                return pd.DataFrame(obj)
            if isinstance(obj,dict):
                for key in ("Rows","rows","data","Data"):
                    if key in obj: return pd.DataFrame(obj[key])
            raise ValueError(f"Unrecognized SkyServer JSON schema: {type(obj).__name__}")
        except Exception:
            if k==tries-1: break
            time.sleep(5*(k+1))
    # Final fallback: use SDSS public CSV endpoint and strip metadata/comment lines.
    r=requests.get(SDSS,params={"cmd":q,"format":"csv"},headers={"User-Agent":"Finding_objects/1.0"},timeout=120)
    r.raise_for_status()
    lines=[ln for ln in r.text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if len(lines)<2: raise RuntimeError("SDSS SkyServer returned no parseable tabular rows")
    df=pd.read_csv(io.StringIO("\\n".join(lines)))
    if not {"ra","dec"}.issubset({str(x).lower() for x in df.columns}):
        raise RuntimeError(f"SDSS response lacks coordinates: {list(df.columns)}")
    return df

