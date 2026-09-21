"""Magellanic Clouds blind end-to-end validation sample.

Builds a reproducible random sample of Gaia DR3 sources in LMC/SMC directions
with significant positive parallax (distance proxy available), hides any
external class labels, derives astrometric features, and runs the decision tree.
This is a pipeline validation field sample, NOT an LMC/SMC membership sample.
"""
from __future__ import annotations
import json, pathlib, time
import numpy as np, pandas as pd
from astroquery.gaia import Gaia
from finding_objects.decision_tree import identity_tree

SEED=26092026
N_LMC=400; N_SMC=400
FIELDS={"LMC":(80.8939,-69.7561,8.0),"SMC":(13.1867,-72.8286,5.0)}

def query(name,ra,dec,radius,n):
    # distance-known proxy: positive parallax with S/N>=5; quality cuts reduce
    # pathological astrometry. Randomness is reproducible via random_index.
    # Avoid ORDER BY over the full cone: Gaia TAP can spend hours sorting it.
    # Deterministic random_index windows provide reproducible pseudo-random sampling.
    span=1800000000
    offset=120000000 if name=="LMC" else 980000000
    q=f"""SELECT TOP {n*3} source_id,ra,dec,parallax,parallax_error,pmra,pmra_error,
    pmdec,pmdec_error,phot_g_mean_mag,bp_rp,ruwe,random_index
    FROM gaiadr3.gaia_source
    WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},{radius}))
      AND parallax>0 AND parallax_over_error>=5 AND ruwe<1.4
      AND visibility_periods_used>=8 AND phot_g_mean_mag IS NOT NULL
      AND random_index BETWEEN {offset} AND {offset+span}"""
    last=None
    for k in range(3):
        try:
            d=Gaia.launch_job_async(q).get_results().to_pandas()
            if len(d)>=n:
                return d.sample(n=n,random_state=SEED+(0 if name=="LMC" else 1)).copy()
            last=RuntimeError(f"{name}: only {len(d)} rows")
        except Exception as e:
            last=e; time.sleep(5*(k+1))
    raise last

def main():
    out=pathlib.Path("results/magellanic_blind800"); out.mkdir(parents=True,exist_ok=True)
    frames=[]; errors=[]
    for name,(ra,dec,r,n) in [(k,(*v,N_LMC if k=="LMC" else N_SMC)) for k,v in FIELDS.items()]:
        try:
            d=query(name,ra,dec,r,n); d["field"]=name; frames.append(d)
        except Exception as e:
            errors.append({"stage":"sample","field":name,"error":repr(e)})

    if not frames: raise RuntimeError("No field sample retrieved")
    df=pd.concat(frames,ignore_index=True)
    rows=[]; paths=[]
    for _,r in df.iterrows():
        pm=np.hypot(float(r.pmra),float(r.pmdec))
        pme=max(float(r.pmra_error),float(r.pmdec_error),1e-9)
        f={"spectrum_verified":False,
           "parallax_snr":float(r.parallax/r.parallax_error),
           "proper_motion_snr":float(pm/pme)}
        res=identity_tree(f)
        rows.append({"source_id":str(r.source_id),"field":r.field,
          "ra":r.ra,"dec":r.dec,"parallax_mas":r.parallax,
          "distance_proxy_pc":1000.0/r.parallax,
          "gmag":r.phot_g_mean_mag,"bp_rp":r.bp_rp,
          "tree_identity":res["identity"]})
        paths.append({"source_id":str(r.source_id),**res})
    pred=pd.DataFrame(rows)
    pred.to_csv(out/"classifications.csv",index=False)
    df.to_csv(out/"blind_input_astrometry.csv",index=False)
    with open(out/"decision_paths.jsonl","w") as h:
        for x in paths: h.write(json.dumps(x)+"\n")
    summary={"requested":800,"retrieved":len(df),"fields":df.field.value_counts().to_dict(),
      "identity_counts":pred.tree_identity.value_counts().to_dict(),
      "selection":"Gaia DR3 field sources, parallax_over_error>=5, positive parallax, RUWE<1.4; labels hidden",
      "critical_note":"Directional field validation only. Positive significant parallax strongly selects foreground Milky Way stars; it does not imply Magellanic membership. Inverse-parallax distance is a validation proxy, not a precision distance estimator.",
      "errors":errors}
    json.dump(summary,open(out/"summary.json","w"),indent=2)
    print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
