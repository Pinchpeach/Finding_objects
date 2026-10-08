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
    namespaced={c.split("__",1)[0] for c in df.columns if "__" in c}
    def field(prefix,name):
        """Column holding ``name`` from catalog ``prefix`` (see Stage 2)."""
        if prefix in namespaced:
            key=f"{prefix}__{name}"
            return key if key in df.columns else None
        return name if name in df.columns else None
    gaia=lambda n: field("gaia_dr3",n)
    if gaia("parallax") and gaia("parallax_error"):
        plx,eplx=df[gaia("parallax")],df[gaia("parallax_error")]
        derived["parallax_snr"]=safe_div(pd.to_numeric(plx,errors="coerce").abs(),eplx)
        derived["normalized_corrected_parallax"]=safe_div((pd.to_numeric(plx,errors="coerce")+0.017).abs(),eplx)
    pm=[gaia(c) for c in ("pmra","pmra_error","pmdec","pmdec_error")]
    if all(pm):
        a=safe_div(df[pm[0]],df[pm[1]]); d=safe_div(df[pm[2]],df[pm[3]])
        derived["proper_motion_significance"]=np.sqrt(a*a+d*d)
    # Pan-STARRS photometric colours and PSF-Kron morphology proxies.
    # These are continuous measurements only; no class threshold is applied here.
    ps1_bands=("g","r","i","z","y")
    def ps1_col(name):
        return field("pan_starrs1_dr2_meanobject",name)
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
    # Legacy Surveys DR10 dereddened AB colours (Dey+2019): grz Tractor fluxes
    # and unWISE forced W1/W2, in nanomaggies (m = 22.5 - 2.5 log10 f).  Quasars
    # are separated from stars by their mid-IR excess (z-W1, W1-W2) and blue
    # optical colours (Chaussidon+2023).  A band enters a colour only at S/N>=3.
    ls=lambda n: field("desi_legacy_surveys_dr10",n)
    def ls_mag(band):
        f,iv,t=ls(f"flux_{band}"),ls(f"flux_ivar_{band}"),ls(f"mw_transmission_{band}")
        if not f or not iv: return None
        flux=pd.to_numeric(df[f],errors="coerce"); ivar=pd.to_numeric(df[iv],errors="coerce")
        trans=pd.to_numeric(df[t],errors="coerce").where(lambda x:x>0) if t else 1.0
        ok=(flux>0)&(flux*np.sqrt(ivar.clip(lower=0))>=3)
        return (22.5-2.5*np.log10((flux/trans).where(ok))).where(ok)
    ls_mags={b:ls_mag(b) for b in ("g","r","z","w1","w2")}
    for b1,b2 in (("g","r"),("r","z"),("z","w1"),("w1","w2")):
        if ls_mags[b1] is not None and ls_mags[b2] is not None:
            derived[f"ls_{b1}_{b2}_color"]=ls_mags[b1]-ls_mags[b2]

    # WISE Vega colours and propagated errors.
    wise=lambda n: field("allwise",n)
    if wise("W1mag") and wise("W2mag"):
        w1=pd.to_numeric(df[wise("W1mag")],errors="coerce"); w2=pd.to_numeric(df[wise("W2mag")],errors="coerce")
        derived["wise_w1_w2_color"]=w1-w2
        if wise("e_W1mag") and wise("e_W2mag"):
            e1=pd.to_numeric(df[wise("e_W1mag")],errors="coerce"); e2=pd.to_numeric(df[wise("e_W2mag")],errors="coerce")
            derived["wise_w1_w2_color_err"]=np.sqrt(e1*e1+e2*e2)

    # Catalog observation-confidence indices. These are [0,1] project quality
    # indices anchored to published catalog quality diagnostics; they are NOT
    # posterior class probabilities. Missing catalog/quality information stays NaN.
    conf={}
    catalogs=df["catalogs"].fillna("").astype(str) if "catalogs" in df.columns else pd.Series("",index=df.index)
    def ncol(name,prefix):
        col=field(prefix,name)
        return pd.to_numeric(df[col],errors="coerce") if col else pd.Series(np.nan,index=df.index)
    def tcol(name,prefix):
        col=field(prefix,name)
        return df[col] if col else pd.Series(np.nan,index=df.index,dtype=object)
    def hascat(name):
        return catalogs.str.contains(name,regex=False)

    # Gaia: RUWE near unity indicates a good single-source astrometric fit;
    # >1.4 is documented as potentially problematic. Penalize continuously above 1.4.
    if gaia("ruwe"):
        ruwe=ncol("ruwe","gaia_dr3")
        g=np.minimum(1.0,1.4/ruwe.where(ruwe>0))
        conf["catalog_confidence_gaia_astrometry"]=g.where(hascat("Gaia DR3"))
    dsc_cols=["classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star",
              "classprob_dsc_combmod_whitedwarf","classprob_dsc_combmod_binarystar"]
    if any(gaia(x) for x in dsc_cols):
        # DSC probabilities already encode classifier uncertainty; this flag only
        # records whether the catalog probability vector is usable.
        ok=pd.concat([ncol(x,"gaia_dr3") for x in dsc_cols if gaia(x)],axis=1).notna().all(axis=1)
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
    if wise("snr1") and wise("snr2"):
        s1=ncol("snr1","allwise"); s2=ncol("snr2","allwise")
        q=np.minimum(1.0,np.minimum(s1,s2)/10.0).clip(lower=0)
        if wise("nb"):
            nb=ncol("nb","allwise"); q=q.where(nb.isna()|(nb<=2),0.0)  # missing nb is unknown, not blended
        if wise("ccf"):
            cc=df[wise("ccf")].fillna("").astype(str).str.replace(".0","",regex=False).str.zfill(4)
            q=q.where(cc.str[:2].eq("00"),0.0)
        conf["catalog_confidence_allwise"]=q.where(hascat("AllWISE"))

    # 2MASS PSC: ph_qual grades A-D are valid detections of decreasing quality;
    # cc_flg!=000 marks potentially biased/contaminated measurements.
    if field("2mass_psc","Qflg"):
        grade={"A":1.0,"B":0.7,"C":0.5,"D":0.25}
        def q2(s):
            vals=[grade.get(ch,0.0) for ch in str(s)[:3]]
            nz=[v for v in vals if v>0]
            return float(sum(nz)/len(nz)) if nz else 0.0
        q=df[field("2mass_psc","Qflg")].map(q2)
        if field("2mass_psc","Cflg"):
            cc=df[field("2mass_psc","Cflg")].fillna("").astype(str).str.replace(".0","",regex=False).str.zfill(3)
            q=q.where(cc.eq("000"),q*0.5)
        conf["catalog_confidence_2mass"]=q.where(hascat("2MASS PSC"))

    # GALEX: convert magnitude uncertainty to approximate S/N (1.0857/sigma_mag);
    # artifact flags suppress affected bands. Five-sigma reaches index 1.
    if field("galex_ais","NUVmag") or field("galex_ais","FUVmag"):
        qs=[]
        for band,err,af in (("NUVmag","e_NUVmag","Nafl"),("FUVmag","e_FUVmag","Fafl")):
            if field("galex_ais",err):
                e=ncol(err,"galex_ais"); snr=1.0857/e.where(e>0); qb=np.minimum(1.0,snr/5.0)
                if field("galex_ais",af): qb=qb.where(ncol(af,"galex_ais").fillna(0).eq(0),0.0)
                qs.append(qb)
        if qs:
            conf["catalog_confidence_galex"]=pd.concat(qs,axis=1).mean(axis=1).where(hascat("GALEX AIS"))

    # SDSS spectroscopy: ZWARNING=0 means no pipeline warning. Nonzero warnings
    # retain reduced confidence rather than being discarded.
    if field("sdss_dr18_spectroscopy","zwarning"):
        zw=ncol("zwarning","sdss_dr18_spectroscopy")
        conf["catalog_confidence_sdss_spectroscopy"]=pd.Series(np.where(zw.eq(0),1.0,np.where(zw.notna(),0.5,np.nan)),index=df.index).where(hascat("SDSS DR18 spectroscopy"))
    # SDSS imaging: official guidance recommends clean=1 for clean star/galaxy samples.
    if field("sdss_dr18_photoobj","clean"):
        cl=ncol("clean","sdss_dr18_photoobj")
        conf["catalog_confidence_sdss_photometry"]=cl.eq(1).astype(float).where(hascat("SDSS DR18 PhotoObj"))

    # NED/SIMBAD are curated literature databases rather than homogeneous surveys.
    # Their indices are provenance weights, deliberately below direct spectroscopy.
    if field("ned","Type"):
        physical={"G","QSO","*","WD*"}
        conf["catalog_confidence_ned_type"]=tcol("Type","ned").astype(str).isin(physical).astype(float).mul(0.8).where(hascat("NED"))
    if field("simbad","otype"):
        physical={"G","GiG","QSO","AGN","Star","*","WD*"}
        conf["catalog_confidence_simbad_type"]=tcol("otype","simbad").astype(str).isin(physical).astype(float).mul(0.8).where(hascat("SIMBAD"))

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
