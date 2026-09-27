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
      s.zWarning,s.plate,s.mjd,s.fiberID
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
    # DR20 SPIDERS/eROSITA VAC. SELECT * makes the builder resilient to
    # VAC column additions; required fields are identified from documented
    # semantic names below.
    d=fetch(DR20,f"SELECT TOP {limit*5} * FROM DL1_eROSITA_eRASS3")
    class_col=_pick(d,["class","spec_class","class_best","class_sdss","class_boss"])
    ra_col=_pick(d,["ra","fiber_ra","target_ra","ra_sdss","plug_ra"])
    dec_col=_pick(d,["dec","fiber_dec","target_dec","dec_sdss","plug_dec"])
    zw_col=_pick(d,["zwarning","z_warning","zwarn","zwarning_noqso"])
    z_col=_pick(d,["z","z_best","redshift"])
    ze_col=_pick(d,["zerr","z_err","redshift_err"])
    id_col=_pick(d,["catalogid","catalog_id","sdss_id","specobjid","specobj_id"])
    if not class_col or not ra_col or not dec_col:
        raise KeyError(f"Cannot identify required SPIDERS columns. columns={list(d.columns)}")
    cls=d[class_col].astype(str).str.upper().replace({"QUASAR":"QSO"})
    good=cls.isin(VALID)
    if zw_col:
        good &= pd.to_numeric(d[zw_col],errors="coerce").fillna(0).eq(0)
    out=pd.DataFrame({
        "specobjid":d[id_col].astype(str) if id_col else ["XRAY_"+str(i) for i in range(len(d))],
        "bestobjid":"",
        "ra":pd.to_numeric(d[ra_col],errors="coerce"),
        "dec":pd.to_numeric(d[dec_col],errors="coerce"),
        "class":cls,
        "subclass":"",
        "z":pd.to_numeric(d[z_col],errors="coerce") if z_col else pd.NA,
        "zerr":pd.to_numeric(d[ze_col],errors="coerce") if ze_col else pd.NA,
        "zwarning":pd.to_numeric(d[zw_col],errors="coerce") if zw_col else 0,
        "plate":pd.NA,"mjd":pd.NA,"fiberid":pd.NA,
    })
    out=out[good & out.ra.notna() & out.dec.notna()].copy()
    out["truth_class"]=out["class"]
    out["truth_selection"]="XRAY_EROSITA"
    out["truth_detection_catalog"]="eROSITA"
    out["truth_source"]="SDSS_DR20_SPIDERS_EROSITA"
    out["truth_quality"]="SPIDERS_SPECTROSCOPY"
    # Keep the observed class mixture but cap extreme domination.
    pieces=[]; cap=max(50,int(limit*0.65))
    for c in ("STAR","GALAXY","QSO"):
        pieces.append(out[out.truth_class.eq(c)].head(cap))
    out=pd.concat(pieces,ignore_index=True).drop_duplicates(["ra","dec"])
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
