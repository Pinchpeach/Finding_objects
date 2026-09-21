"""Detailed stellar characterization for the Magellanic Blind-800 field sample.
Photometric/astrometric subtype is deliberately conservative: without spectra,
MK spectral types are candidates, not spectroscopic classifications.
"""
from __future__ import annotations
import json, pathlib, pandas as pd, numpy as np

def subtype(bp_rp):
    if pd.isna(bp_rp): return ("UNKNOWN","missing BP-RP")
    x=float(bp_rp)
    # Broad Gaia-color candidate bins for triage only; extinction/metallicity can shift them.
    if x < -0.15: return ("O_B_CANDIDATE","very blue Gaia BP-RP")
    if x < 0.20: return ("A_CANDIDATE","blue Gaia BP-RP")
    if x < 0.55: return ("F_CANDIDATE","blue-yellow Gaia BP-RP")
    if x < 0.90: return ("G_CANDIDATE","solar-like Gaia BP-RP")
    if x < 1.45: return ("K_CANDIDATE","orange Gaia BP-RP")
    return ("M_CANDIDATE","red Gaia BP-RP")

def main():
    src=pathlib.Path("results/magellanic_blind800/blind_input_astrometry.csv")
    out=pathlib.Path("results/magellanic_blind800_stellar"); out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(src,dtype={"source_id":str})
    rows=[]
    for _,r in d.iterrows():
        st,ev=subtype(r.get("bp_rp"))
        par=float(r.parallax); dist=1000/par
        # Approximate absolute G from inverse parallax; no extinction correction.
        MG=float(r.phot_g_mean_mag)-5*np.log10(dist/10)
        # Luminosity morphology is intentionally broad and flagged provisional.
        if MG < -1: lum="LUMINOUS_STAR_CANDIDATE"
        elif MG > 8 and st in {"O_B_CANDIDATE","A_CANDIDATE","F_CANDIDATE"}: lum="COMPACT_BLUE_CANDIDATE"
        else: lum="MAIN_SEQUENCE_OR_GIANT_UNRESOLVED"
        rows.append({"source_id":str(r.source_id),"field":r.field,"bp_rp":r.bp_rp,
          "gmag":r.phot_g_mean_mag,"parallax_mas":par,"distance_proxy_pc":dist,
          "absolute_g_proxy":MG,"stellar_subtype_candidate":st,
          "luminosity_candidate":lum,"evidence":ev,
          "counter_evidence":"No spectrum; extinction and metallicity not corrected",
          "confidence":"LOW_TO_MODERATE_PHOTOMETRIC",
          "missing_decisive_data":"stellar spectrum; extinction; calibrated absolute magnitude"})
    z=pd.DataFrame(rows); z.to_csv(out/"stellar_characterization.csv",index=False)
    summary={"objects":len(z),"subtype_counts":z.stellar_subtype_candidate.value_counts().to_dict(),
      "luminosity_counts":z.luminosity_candidate.value_counts().to_dict(),
      "warning":"These are photometric subtype candidates, not MK spectroscopic classifications. BP-RP is affected by extinction/metallicity; inverse-parallax distances and absolute G are proxies."}
    json.dump(summary,open(out/"summary.json","w"),indent=2); print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
