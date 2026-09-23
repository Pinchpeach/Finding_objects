#!/usr/bin/env python3
"""Stage 3: derive rule-required classification features.

Preserves all integrated columns and adds deterministic derived features used by
classification_rules.csv. It does not classify objects.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def safe_div(a,b):
    a=pd.to_numeric(a,errors="coerce"); b=pd.to_numeric(b,errors="coerce")
    return a.div(b.where(b.ne(0)))

def run(objects:Path,rules_path:Path,out:Path)->Path:
    df=pd.read_csv(objects); rules=pd.read_csv(rules_path,keep_default_na=False)
    required=set()
    for cell in rules["feature_columns"]:
        required.update(x for x in str(cell).split("|") if x)
    # Build all derived columns together, then concatenate once. This avoids
    # repeated DataFrame.insert calls and fragmentation as feature count grows.
    derived={}
    if {"parallax","parallax_error"}.issubset(df.columns):
        derived["parallax_snr"]=safe_div(df["parallax"].abs(),df["parallax_error"])
        derived["normalized_corrected_parallax"]=safe_div((pd.to_numeric(df["parallax"],errors="coerce")+0.017).abs(),df["parallax_error"])
    pm={"pmra","pmra_error","pmdec","pmdec_error"}
    if pm.issubset(df.columns):
        a=safe_div(df["pmra"],df["pmra_error"]); d=safe_div(df["pmdec"],df["pmdec_error"])
        derived["proper_motion_significance"]=np.sqrt(a*a+d*d)
    # Pan-STARRS photometric colours and PSF-Kron morphology proxies.
    # These are continuous measurements only; no class threshold is applied here.
    ps1_bands=("g","r","i","z","y")
    def ps1_col(name):
        if name in df.columns:
            return name
        pref=f"pan_starrs1_dr2_meanobject__{name}"
        return pref if pref in df.columns else None
    psf={b:ps1_col(f"{b}MeanPSFMag") for b in ps1_bands}
    kron={b:ps1_col(f"{b}MeanKronMag") for b in ps1_bands}
    def valid_ps1_mag(col):
        s=pd.to_numeric(df[col],errors="coerce")
        # PS1 uses sentinel/non-physical values (notably -999) for missing photometry.
        return s.where((s>0)&(s<40))
    psf_mag={b:(valid_ps1_mag(psf[b]) if psf[b] else None) for b in ps1_bands}
    kron_mag={b:(valid_ps1_mag(kron[b]) if kron[b] else None) for b in ps1_bands}
    for b1,b2 in zip(ps1_bands,ps1_bands[1:]):
        if psf_mag[b1] is not None and psf_mag[b2] is not None:
            derived[f"ps1_{b1}_{b2}_color"]=psf_mag[b1]-psf_mag[b2]
    for b in ps1_bands:
        if psf_mag[b] is not None and kron_mag[b] is not None:
            derived[f"ps1_{b}_psf_minus_kron"]=psf_mag[b]-kron_mag[b]
    # Preserve uncertainty and per-band detection counts so later evidence
    # rules can gate on measurement quality rather than colour alone.
    for b in ps1_bands:
        err_col=ps1_col(f"{b}MeanPSFMagErr")
        kron_err_col=ps1_col(f"{b}MeanKronMagErr")
        n_col=ps1_col(f"n{b}")
        if err_col:
            err=pd.to_numeric(df[err_col],errors="coerce")
            derived[f"ps1_{b}_psf_mag_err"]=err.where((err>0)&(err<5))
        if kron_err_col:
            kerr=pd.to_numeric(df[kron_err_col],errors="coerce")
            derived[f"ps1_{b}_kron_mag_err"]=kerr.where((kerr>0)&(kerr<5))
        if n_col:
            n=pd.to_numeric(df[n_col],errors="coerce")
            derived[f"ps1_n_{b}"]=n.where(n>=0)

    ndet=ps1_col("nDetections")
    if ndet:
        n=pd.to_numeric(df[ndet],errors="coerce")
        derived["ps1_n_detections"]=n.where(n>=0)

    # Data-quality flags only. These do not imply an astronomical class.
    # A band is usable when it has a physical PSF magnitude, a finite positive
    # uncertainty, and at least one contributing detection.
    for b in ps1_bands:
        if psf_mag[b] is None: continue
        err=derived.get(f"ps1_{b}_psf_mag_err")
        n=derived.get(f"ps1_n_{b}")
        if err is not None and n is not None:
            derived[f"ps1_{b}_photometry_valid"]=(psf_mag[b].notna()&err.notna()&(n>0)).astype("Int64")

    # Colour uncertainties/significances.  These preserve the measurement
    # uncertainty so colour-selection rules can demand statistically meaningful
    # separation from their literature boundaries.
    for b1,b2 in zip(ps1_bands,ps1_bands[1:]):
        e1=derived.get(f"ps1_{b1}_psf_mag_err"); e2=derived.get(f"ps1_{b2}_psf_mag_err")
        col=derived.get(f"ps1_{b1}_{b2}_color")
        if e1 is not None and e2 is not None and col is not None:
            ce=np.sqrt(e1*e1+e2*e2)
            derived[f"ps1_{b1}_{b2}_color_err"]=ce
    # WISE Vega colours and propagated errors.
    if "W1mag" in df.columns and "W2mag" in df.columns:
        w1=pd.to_numeric(df["W1mag"],errors="coerce"); w2=pd.to_numeric(df["W2mag"],errors="coerce")
        derived["wise_w1_w2_color"]=w1-w2
        if "e_W1mag" in df.columns and "e_W2mag" in df.columns:
            e1=pd.to_numeric(df["e_W1mag"],errors="coerce"); e2=pd.to_numeric(df["e_W2mag"],errors="coerce")
            derived["wise_w1_w2_color_err"]=np.sqrt(e1*e1+e2*e2)

    # Catalog observation-confidence indices. These are [0,1] project quality
    # indices anchored to published catalog quality diagnostics; they are NOT
    # posterior class probabilities. Missing catalog/quality information stays NaN.
    conf={}
    catalogs=df["catalogs"].fillna("").astype(str) if "catalogs" in df.columns else pd.Series("",index=df.index)
    def ncol(name):
        return pd.to_numeric(df[name],errors="coerce") if name in df.columns else pd.Series(np.nan,index=df.index)
    def hascat(name):
        return catalogs.str.contains(name,regex=False)

    # Gaia: RUWE near unity indicates a good single-source astrometric fit;
    # >1.4 is documented as potentially problematic. Penalize continuously above 1.4.
    if "ruwe" in df.columns:
        ruwe=ncol("ruwe")
        g=np.minimum(1.0,1.4/ruwe.where(ruwe>0))
        conf["catalog_confidence_gaia_astrometry"]=g.where(hascat("Gaia DR3"))
    dsc_cols=["classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star",
              "classprob_dsc_combmod_whitedwarf","classprob_dsc_combmod_binarystar"]
    if any(x in df.columns for x in dsc_cols):
        # DSC probabilities already encode classifier uncertainty; this flag only
        # records whether the catalog probability vector is usable.
        ok=pd.concat([ncol(x) for x in dsc_cols if x in df.columns],axis=1).notna().all(axis=1)
        conf["catalog_confidence_gaia_dsc"]=ok.astype(float).where(hascat("Gaia DR3"))

    # PS1 morphology: propagate PSF and Kron magnitude errors into the separator
    # and use distance from the documented 0.05-mag boundary in sigma units.
    if derived:
        delta=derived.get("ps1_i_psf_minus_kron"); pe=derived.get("ps1_i_psf_mag_err"); ke=derived.get("ps1_i_kron_mag_err")
        imag=psf_mag.get("i")
        if delta is not None and pe is not None and ke is not None and imag is not None:
            sig=np.sqrt(pe*pe+ke*ke)
            z=(delta-0.05).abs()/sig.where(sig>0)
            q=(z/(z+1)).where((imag>=14)&(imag<=21))
            conf["catalog_confidence_ps1_morphology"]=q.where(hascat("Pan-STARRS1"))

    # AllWISE: Stern et al. AGN selection used W1/W2 SNR>=10, isolated sources
    # (nb<=2), and artifact-free W1/W2 photometry. The index measures how fully
    # a source satisfies that measurement-quality envelope.
    if "snr1" in df.columns and "snr2" in df.columns:
        s1=ncol("snr1"); s2=ncol("snr2")
        q=np.minimum(1.0,np.minimum(s1,s2)/10.0).clip(lower=0)
        if "nb" in df.columns: q=q.where(ncol("nb")<=2,0.0)
        if "ccf" in df.columns:
            cc=df["ccf"].fillna("").astype(str).str.replace(".0","",regex=False).str.zfill(4)
            q=q.where(cc.str[:2].eq("00"),0.0)
        conf["catalog_confidence_allwise"]=q.where(hascat("AllWISE"))

    # 2MASS PSC: ph_qual grades A-D are valid detections of decreasing quality;
    # cc_flg!=000 marks potentially biased/contaminated measurements.
    if "Qflg" in df.columns:
        grade={"A":1.0,"B":0.7,"C":0.5,"D":0.25}
        def q2(s):
            vals=[grade.get(ch,0.0) for ch in str(s)[:3]]
            nz=[v for v in vals if v>0]
            return float(sum(nz)/len(nz)) if nz else 0.0
        q=df["Qflg"].map(q2)
        if "Cflg" in df.columns:
            cc=df["Cflg"].fillna("").astype(str).str.replace(".0","",regex=False).str.zfill(3)
            q=q.where(cc.eq("000"),q*0.5)
        conf["catalog_confidence_2mass"]=q.where(hascat("2MASS PSC"))

    # GALEX: convert magnitude uncertainty to approximate S/N (1.0857/sigma_mag);
    # artifact flags suppress affected bands. Five-sigma reaches index 1.
    if "NUVmag" in df.columns or "FUVmag" in df.columns:
        qs=[]
        for band,err,af in (("NUVmag","e_NUVmag","Nafl"),("FUVmag","e_FUVmag","Fafl")):
            if err in df.columns:
                e=ncol(err); snr=1.0857/e.where(e>0); qb=np.minimum(1.0,snr/5.0)
                if af in df.columns: qb=qb.where(ncol(af).fillna(0).eq(0),0.0)
                qs.append(qb)
        if qs:
            conf["catalog_confidence_galex"]=pd.concat(qs,axis=1).mean(axis=1).where(hascat("GALEX AIS"))

    # SDSS spectroscopy: ZWARNING=0 means no pipeline warning. Nonzero warnings
    # retain reduced confidence rather than being discarded.
    if "zwarning" in df.columns:
        zw=ncol("zwarning")
        conf["catalog_confidence_sdss_spectroscopy"]=pd.Series(np.where(zw.eq(0),1.0,np.where(zw.notna(),0.5,np.nan)),index=df.index).where(hascat("SDSS DR18 spectroscopy"))
    # SDSS imaging: official guidance recommends clean=1 for clean star/galaxy samples.
    if "clean" in df.columns:
        cl=ncol("clean")
        conf["catalog_confidence_sdss_photometry"]=cl.eq(1).astype(float).where(hascat("SDSS DR18 PhotoObj"))

    # NED/SIMBAD are curated literature databases rather than homogeneous surveys.
    # Their indices are provenance weights, deliberately below direct spectroscopy.
    if "Type" in df.columns:
        physical={"G","QSO","*","WD*"}
        conf["catalog_confidence_ned_type"]=df["Type"].astype(str).isin(physical).astype(float).mul(0.8).where(hascat("NED"))
    if "otype" in df.columns:
        physical={"G","GiG","QSO","AGN","Star","*","WD*"}
        conf["catalog_confidence_simbad_type"]=df["otype"].astype(str).isin(physical).astype(float).mul(0.8).where(hascat("SIMBAD"))

    if derived:
        df=pd.concat([df,pd.DataFrame(derived,index=df.index)],axis=1)
    if conf:
        df=pd.concat([df,pd.DataFrame(conf,index=df.index)],axis=1)

    available=[c for c in required if c in df.columns]
    coverage=df[available].notna().sum(axis=1) if available else pd.Series(0,index=df.index)
    metadata=pd.DataFrame({
        "rule_feature_coverage":coverage.astype(int),
        "rule_feature_total":len(required),
    },index=df.index)
    df=pd.concat([df,metadata],axis=1)

    out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] required_features={len(required)} objects={len(df)} -> {out}"); return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--objects",type=Path,default=root/"integrated_objects.csv")
    p.add_argument("--rules",type=Path,default=root/"classification_rules.csv")
    p.add_argument("--out",type=Path,default=root/"features.csv")
    a=p.parse_args(); run(a.objects,a.rules,a.out)
if __name__=="__main__": main()
