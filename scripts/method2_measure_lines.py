"""Method 2 stage 3: measure expected spectral features and build per-object spectroscopy labels."""
from pathlib import Path
import json, numpy as np, pandas as pd

ROOT=Path("data/method2spec"); OUT=Path("results/method2_300_lines")
def measure(w,f,iv,center):
    side=((w>center-60)&(w<center-20))|((w>center+20)&(w<center+60)); core=(w>center-12)&(w<center+12)
    if core.sum()<4 or side.sum()<8:return None
    cont=np.nanmedian(f[side]); noise=np.nanmedian(np.where(iv[core]>0,1/np.sqrt(iv[core]),np.nan))
    if not np.isfinite(noise) or noise<=0: noise=np.nanstd(f[side]-cont)
    resid=f[core]-cont; j=np.nanargmax(np.abs(resid)); amp=resid[j]; sig=amp/noise if noise>0 else np.nan
    ew=np.trapz(1-f[core]/cont,w[core]) if np.isfinite(cont) and cont!=0 else np.nan
    return float(w[core][j]),float(amp),float(sig),float(ew),("emission" if amp>0 else "absorption")
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pos=pd.read_csv(ROOT/"line_positions.csv",dtype={"objid":str}); rows=[]
    for oid,g in pos.groupby("objid"):
        p=ROOT/"spectra"/f"{oid}.csv"
        if not p.exists(): continue
        s=pd.read_csv(p); w=s.wavelength_observed_angstrom.to_numpy(float); f=s.flux_1e-17_erg_s_cm2_A.to_numpy(float); iv=s.ivar.to_numpy(float)
        for _,r in g.iterrows():
            base=r.to_dict()
            if not bool(r.covered_by_spectrum): base.update(detection_status="not_covered")
            else:
                m=measure(w,f,iv,float(r.expected_observed_wavelength_angstrom))
                if m is None: base.update(detection_status="unmeasurable")
                else:
                    ow,amp,snr,ew,kind=m; base.update(measured_peak_wavelength_angstrom=ow,peak_amplitude=amp,line_snr=snr,equivalent_width_angstrom=ew,line_kind=kind,detection_status="detected" if abs(snr)>=4 else "not_significant")
            rows.append(base)
    d=pd.DataFrame(rows); d.to_csv(OUT/"measured_lines.csv",index=False)
    labs=[]
    for oid,g in d.groupby("objid"):
        det=g[g.detection_status=="detected"]; metals=det[det.is_metal_line.astype(str).str.lower().isin(["true","1"])]
        labs.append({"objid":oid,"detected_lines":"|".join(det.line.astype(str)),"detected_metal_lines":"|".join(metals.line.astype(str)),"n_detected_lines":len(det),"n_detected_metal_lines":len(metals)})
    pd.DataFrame(labs).to_csv(OUT/"spectroscopic_labels.csv",index=False)
    (OUT/"summary.json").write_text(json.dumps({"objects":int(d.objid.nunique()),"line_rows":len(d),"detected":int((d.detection_status=="detected").sum()),"metal_detected":int(((d.detection_status=="detected") & d.is_metal_line.astype(str).str.lower().isin(["true","1"])).sum()),"threshold":"|peak amplitude/noise| >= 4; automated pilot measurement, requires validation for precision science"},indent=2))
if __name__=="__main__":main()
