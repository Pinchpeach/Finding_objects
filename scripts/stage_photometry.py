"""Stage 3: normalize photometric quantities for SED work.

SDSS ugriz are AB magnitudes. Other survey rows in stage 2 currently contain
presence/separation only, so they are explicitly marked value_not_retrieved
rather than inventing photometry.
"""
from pathlib import Path
import json, math
import pandas as pd

BASE=Path("data/batch1000/sample.csv")
ASSOC=Path("data/stage02/associations.csv")
OUT=Path("results/stages/03_photometry")
EFF_A={"u":3551.0,"g":4686.0,"r":6165.0,"i":7481.0,"z":8931.0}
def ab_jy(m): return 3631.0*10**(-0.4*float(m))
def main():
    base=pd.read_csv(BASE,dtype={"objid":str}); rows=[]
    for _,r in base.iterrows():
        for band,w in EFF_A.items():
            m=r.get(band)
            if pd.isna(m): continue
            jy=ab_jy(m); hz=2.99792458e18/w
            rows.append({"objid":r.objid,"survey":"SDSS","filter":band,"wavelength_angstrom":w,
                         "quantity_kind":"ab_mag","magnitude":float(m),"flux_density_jy":jy,
                         "frequency_hz":hz,"nu_fnu_jy_hz":jy*hz,"status":"normalized"})
    OUT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT/"sdss_normalized.csv",index=False)
    assoc=pd.read_csv(ASSOC,dtype={"objid":str})
    missing=assoc[assoc.status.eq("available")][["objid","survey","separation_arcsec","association_status"]].copy()
    missing["status"]="value_not_retrieved"
    missing.to_csv(OUT/"external_photometry_needed.csv",index=False)
    summary={"sdss_points":len(rows),"objects_with_sdss":int(pd.DataFrame(rows).objid.nunique()),
             "external_catalog_matches_needing_values":len(missing),
             "note":"No external magnitude/flux values were present in stage-2 acquisition; they are queued for a dedicated value retrieval stage."}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
if __name__=="__main__":main()
