"""Analyze Blind-800 stellar characterization: HR proxy, contradictions, follow-up ranking."""
import json, pathlib, pandas as pd, numpy as np
import matplotlib.pyplot as plt
IN=pathlib.Path("results/magellanic_blind800_stellar/stellar_characterization.csv")
OUT=pathlib.Path("results/magellanic_blind800_stellar_analysis"); OUT.mkdir(parents=True,exist_ok=True)
d=pd.read_csv(IN,dtype={"source_id":str})
# Photometric consistency flags. These are triage rules, not astrophysical truth labels.
def flag(r):
    c=r.bp_rp; M=r.absolute_g_proxy
    f=[]
    if pd.isna(c): f.append("missing_color")
    else:
        if c < 0.2 and M > 8: f.append("blue_faint_compact_candidate")
        if c > 1.45 and M < 0: f.append("red_luminous_candidate")
        if c < -0.15 and M > 5: f.append("OB_color_but_faint")
    return ";".join(f) or "none"
d["hr_flags"]=d.apply(flag,axis=1)
d["followup_score"]=0
d.loc[d.hr_flags!="none","followup_score"]+=3
d.loc[d.stellar_subtype_candidate.isin(["O_B_CANDIDATE","A_CANDIDATE"]),"followup_score"]+=2
d.loc[d.luminosity_candidate!="MAIN_SEQUENCE_OR_GIANT_UNRESOLVED","followup_score"]+=2
d.loc[d.stellar_subtype_candidate=="UNKNOWN","followup_score"]+=1
d["likely_object_type"]=np.where(d.hr_flags.str.contains("blue_faint"),"compact blue star / white-dwarf candidate",
 np.where(d.hr_flags.str.contains("red_luminous"),"red luminous star candidate",
 np.where(d.stellar_subtype_candidate=="UNKNOWN","star; subtype unresolved",d.stellar_subtype_candidate.str.replace("_CANDIDATE","",regex=False)+"-like star candidate")))
d["classification_caution"]="Photometric candidate only; spectrum/extinction/metallicity needed for MK subtype."
d.sort_values(["followup_score","absolute_g_proxy"],ascending=[False,True]).to_csv(OUT/"ranked_stellar_followup.csv",index=False)
# HR proxy diagram
p=d.dropna(subset=["bp_rp","absolute_g_proxy"])
plt.figure(figsize=(8,7)); plt.scatter(p.bp_rp,p.absolute_g_proxy,s=8,alpha=.55)
plt.gca().invert_yaxis(); plt.xlabel("Gaia BP-RP"); plt.ylabel("Absolute G proxy (mag)")
plt.title("Magellanic-direction Blind-800: Gaia color–magnitude proxy")
plt.grid(alpha=.2); plt.tight_layout(); plt.savefig(OUT/"hr_proxy.png",dpi=180); plt.close()
summary={"objects":len(d),"subtype_counts":d.stellar_subtype_candidate.value_counts().to_dict(),
"luminosity_counts":d.luminosity_candidate.value_counts().to_dict(),
"hr_flag_counts":d.hr_flags.value_counts().to_dict(),
"followup_score_counts":d.followup_score.value_counts().sort_index(ascending=False).to_dict(),
"top_followup":d.sort_values(["followup_score","absolute_g_proxy"],ascending=[False,True])[["source_id","field","stellar_subtype_candidate","luminosity_candidate","bp_rp","absolute_g_proxy","hr_flags","followup_score","likely_object_type"]].head(25).to_dict("records"),
"interpretation":"Foreground-star dominated Gaia parallax-selected field sample. HR positions are proxies: no extinction correction; inverse-parallax distance; no spectra."}
json.dump(summary,open(OUT/"analysis_summary.json","w"),indent=2); print(json.dumps(summary,indent=2))
