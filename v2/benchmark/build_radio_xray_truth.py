#!/usr/bin/env python3
"""Build a ~1000-object radio/X-ray-selected spectroscopic truth benchmark.

Radio: SDSS DR18 clean spectra joined to FIRST.
X-ray: SDSS DR20 DL1_eROSITA_eRASS3 (SPIDERS/eROSITA VAC), which contains
       SDSS optical spectral classifications for eROSITA-selected targets.

This is intentionally a separate benchmark from the general 9999-object set:
selection by radio/X-ray detection changes the population prior.
"""
from __future__ import annotations
import argparse, io, time, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd

DR18="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"
DR20="https://skyserver.sdss.org/dr20/SkyServerWS/SearchTools/SqlSearch"
VALID={"STAR","GALAXY","QSO"}

def fetch(url,sql,retries=5,timeout=180):
    q=url+"?"+urllib.parse.urlencode({"cmd":sql,"format":"csv"})
    last=None
    for i in range(retries):
        try:
            with urllib.request.urlopen(q,timeout=timeout) as r: raw=r.read()
            d=pd.read_csv(io.BytesIO(raw),comment="#")
            d.columns=[str(c).strip().lower() for c in d.columns]
            return d
        except Exception as e:
            last=e
            if i+1<retries: time.sleep(min(30,2**i*2))
    raise RuntimeError(f"SkyServer query failed: {last}")

def radio_truth(limit=650):
    # Over-fetch then stratify so rare STAR radio detections are preserved
    # without fabricating a balanced distribution.
    sql=f"""SELECT TOP {limit*4}
      s.specObjID,s.bestObjID,s.ra,s.dec,s.class,s.subClass,s.z,s.zErr,
      s.zWarning,s.plate,s.mjd,s.fiberID,f.peak AS rx_radio_peak,f.integr AS rx_radio_integr
      FROM SpecObj AS s
      JOIN First AS f ON f.objID=s.bestObjID
      WHERE s.zWarning=0 AND s.sciencePrimary=1
        AND s.class IN ('STAR','GALAXY','QSO')
        AND s.ra IS NOT NULL AND s.dec IS NOT NULL
      ORDER BY s.specObjID"""
    d=fetch(DR18,sql)
    d=d[d["class"].str.upper().isin(VALID)].copy()
    d["truth_class"]=d["class"].str.upper()
    d["truth_selection"]="RADIO_FIRST"
    d["truth_detection_catalog"]="FIRST"
    d["truth_source"]="SDSS_DR18_SPECTROSCOPY"
    d["truth_quality"]="ZWARNING_0_SCIENCEPRIMARY"
    # Keep all rare classes, then fill from the larger classes.
    parts=[]
    per=max(1,limit//3)
    for c in ("STAR","GALAXY","QSO"):
        parts.append(d[d.truth_class.eq(c)].head(per))
    out=pd.concat(parts,ignore_index=True).drop_duplicates("specobjid")
    if len(out)<limit:
        rest=d[~d.specobjid.isin(out.specobjid)].head(limit-len(out))
        out=pd.concat([out,rest],ignore_index=True)
    return out.head(limit)

def _pick(d,names):
    for n in names:
        if n in d.columns: return n
    return None

def xray_truth(limit=650):
    """Build X-ray-selected truth by bulk CDS crossmatch of clean SDSS spectra."""
    from astroquery.xmatch import XMatch
    from astropy.table import Table
    import astropy.units as u

    # Build a much larger clean spectroscopy pool than the final benchmark.
    # The query remains class-stratified; X-ray detection is then determined
    # independently by external X-ray catalogs.
    pools=[]
    per_pool=10000
    for cls in ("STAR","GALAXY","QSO"):
        sql=f"""SELECT TOP {per_pool} s.specObjID,s.bestObjID,s.ra,s.dec,
        s.class,s.subClass,s.z,s.zErr,s.zWarning,s.plate,s.mjd,s.fiberID
        FROM SpecObj AS s
        WHERE s.class='{cls}' AND s.zWarning=0 AND s.sciencePrimary=1
          AND s.ra IS NOT NULL AND s.dec IS NOT NULL
        ORDER BY s.specObjID"""
        d=fetch(DR18,sql)
        d["truth_class"]=cls
        pools.append(d)
    pool=pd.concat(pools,ignore_index=True).drop_duplicates("specobjid")
    upload=Table.from_pandas(pool[["specobjid","ra","dec"]].rename(columns={"ra":"truth_ra","dec":"truth_dec"}))

    matches=[]
    xcats=[
      ("eROSITA","vizier:J/A+A/682/A34",10.0),
      ("XMM","vizier:IX/74/4xmmdr13s",8.0),
      ("Chandra","vizier:IX/57/csc2master",5.0),
    ]
    for label,cat,rad in xcats:
        try:
            xm=XMatch.query(cat1=upload,cat2=cat,max_distance=rad*u.arcsec,
                            colRA1="truth_ra",colDec1="truth_dec").to_pandas()
        except Exception as e:
            print(f"[xray] {label} XMatch failed: {e!r}",flush=True)
            continue
        if xm.empty: continue
        xm.columns=[str(x).strip() for x in xm.columns]
        if "angDist" in xm.columns:
            xm["_sep_arcsec"]=pd.to_numeric(xm["angDist"],errors="coerce")
            xm=xm[xm["_sep_arcsec"]<=rad]
        xm["truth_detection_catalog"]=label
        # Preserve catalog-native numeric high-energy measurements discovered
        # at selection time. Keep only scientifically relevant flux/rate/
        # hardness/likelihood/count-like quantities; prefix by catalog so units
        # from different X-ray surveys are never silently mixed.
        keep=["specobjid","truth_detection_catalog"]
        numeric=[]
        for col in xm.columns:
            low=str(col).lower()
            if any(k in low for k in ("flux","rate","hard","hr","lik","count")):
                s=pd.to_numeric(xm[col],errors="coerce")
                if s.notna().any():
                    safe="".join(ch if ch.isalnum() else "_" for ch in low).strip("_")
                    new=f"rx_{label.lower()}_{safe}"
                    xm[new]=s
                    numeric.append(new)
        xm[f"rx_has_{label.lower()}"]=1.0
        numeric.append(f"rx_has_{label.lower()}")
        if "_sep_arcsec" in xm.columns:
            xm[f"rx_{label.lower()}_sep_arcsec"]=pd.to_numeric(xm["_sep_arcsec"],errors="coerce")
            numeric.append(f"rx_{label.lower()}_sep_arcsec")
        matches.append(xm[keep+numeric].drop_duplicates("specobjid"))
        print(f"[xray] {label} matched spectra={xm['specobjid'].nunique()} native_features={len(numeric)}",flush=True)

    if not matches:
        return pd.DataFrame(columns=list(pool.columns)+["truth_selection","truth_detection_catalog","truth_source","truth_quality"])
    # Outer-merge per-catalog X-ray measurements by spectrum id.
    hit=matches[0]
    for q in matches[1:]:
        q=q.drop(columns=["truth_detection_catalog"],errors="ignore")
        hit=hit.merge(q,on="specobjid",how="outer")
    # Record all detection catalogs contributing to each selected source.
    det=pd.concat([m[["specobjid","truth_detection_catalog"]] for m in matches],ignore_index=True)
    det=det.groupby("specobjid")["truth_detection_catalog"].agg(lambda s:"|".join(sorted(set(map(str,s))))).reset_index()
    hit=hit.drop(columns=["truth_detection_catalog"],errors="ignore").merge(det,on="specobjid",how="left")
    out=pool.merge(hit,on="specobjid",how="inner")
    out["truth_selection"]="XRAY_CATALOG"
    out["truth_source"]="SDSS_DR18_SPECTROSCOPY"
    out["truth_quality"]="ZWARNING_0_SCIENCEPRIMARY"
    # Keep all available classes without fabricating balance; cap domination.
    pieces=[]; cap=max(50,int(limit*0.7))
    for cls in ("STAR","GALAXY","QSO"):
        pieces.append(out[out.truth_class.eq(cls)].head(cap))
    out=pd.concat(pieces,ignore_index=True).drop_duplicates("specobjid")
    return out.head(limit)

def run(out_dir:Path,total=1000):
    radio=radio_truth(max(550,total//2+100))
    xray=xray_truth(max(550,total//2+100))
    # Start with half from each detection regime, then fill shortages from either.
    nr=min(len(radio),total//2); nx=min(len(xray),total-nr)
    truth=pd.concat([radio.head(nr),xray.head(nx)],ignore_index=True)
    if len(truth)<total:
        extra=pd.concat([radio.iloc[nr:],xray.iloc[nx:]],ignore_index=True)
        truth=pd.concat([truth,extra.head(total-len(truth))],ignore_index=True)
    truth=truth.drop_duplicates(["ra","dec"]).head(total).reset_index(drop=True)
    if len(truth)<min(800,total):
        raise RuntimeError(f"Only {len(truth)} usable radio/X-ray spectroscopic truth objects; refusing to fabricate rows")
    truth["benchmark_id"]=[f"RXTRD{i+1:06d}" for i in range(len(truth))]
    out_dir.mkdir(parents=True,exist_ok=True)
    truth.to_csv(out_dir/"ground_truth.csv",index=False)
    truth.groupby(["truth_selection","truth_class"]).size().rename("count").reset_index().to_csv(out_dir/"truth_summary.csv",index=False)
    print(truth.groupby(["truth_selection","truth_class"]).size().to_string())
    print(f"[OK] radio/xray truth rows={len(truth)}")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,default=Path(__file__).resolve().parent/"radio_xray_truth")
    p.add_argument("--total",type=int,default=1000)
    a=p.parse_args(); run(a.out_dir,a.total)
if __name__=="__main__": main()
