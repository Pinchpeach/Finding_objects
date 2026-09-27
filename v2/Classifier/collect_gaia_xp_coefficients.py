#!/usr/bin/env python3
"""Download Gaia DR3 XP continuous spectral coefficients for classifier truth rows.

Uses the public ESA Gaia DataLink service through astroquery.gaia.Gaia.load_data.
The continuous representation provides 55 BP + 55 RP Hermite coefficients.
"""
from __future__ import annotations
import argparse, time
from pathlib import Path
import numpy as np
import pandas as pd

def _col(table,*names):
    low={str(c).lower():c for c in table.colnames}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None

def _arr(v,n=55):
    try:
        a=np.asarray(v,dtype=float).reshape(-1)
    except Exception:
        return None
    if len(a)<n:
        return None
    return a[:n]

def run(features:Path,out:Path,batch_size:int=40):
    from astroquery.gaia import Gaia

    src=pd.read_csv(features)
    if "source_id" not in src:
        raise KeyError("source_id required from Gaia crossmatch")
    ids=pd.to_numeric(src["source_id"],errors="coerce").dropna().astype("int64").astype(str).tolist()
    wanted=set(ids)
    rows=[]
    errors=0

    for start in range(0,len(ids),batch_size):
        batch=ids[start:start+batch_size]
        result=None
        last=None
        for attempt in range(4):
            try:
                result=Gaia.load_data(
                    ids=batch,
                    data_release="Gaia DR3",
                    retrieval_type="XP_CONTINUOUS",
                    data_structure="RAW",
                    format="votable",
                    verbose=False,
                )
                last=None
                break
            except Exception as e:
                last=e
                if attempt<3:
                    time.sleep(2**attempt*2)
        if last is not None:
            errors+=1
            print(f"[XP] batch {start//batch_size+1} failed: {last!r}",flush=True)
            continue

        for key,tables in (result or {}).items():
            for table in tables:
                sidc=_col(table,"source_id","SOURCE_ID")
                bpc=_col(table,"bp_coefficients","BP_COEFFICIENTS")
                rpc=_col(table,"rp_coefficients","RP_COEFFICIENTS")
                bpr=_col(table,"bp_n_relevant_bases","BP_N_RELEVANT_BASES")
                rpr=_col(table,"rp_n_relevant_bases","RP_N_RELEVANT_BASES")
                if not sidc or not bpc or not rpc:
                    continue
                for row in table:
                    sid=str(int(row[sidc]))
                    if sid not in wanted:
                        continue
                    bp=_arr(row[bpc]); rp=_arr(row[rpc])
                    if bp is None or rp is None:
                        continue
                    rec={"source_id":sid}
                    for i,v in enumerate(bp):
                        rec[f"xp_bp_{i:02d}"]=float(v)
                    for i,v in enumerate(rp):
                        rec[f"xp_rp_{i:02d}"]=float(v)
                    if bpr:
                        try: rec["xp_bp_n_relevant_bases"]=int(row[bpr])
                        except Exception: pass
                    if rpr:
                        try: rec["xp_rp_n_relevant_bases"]=int(row[rpr])
                        except Exception: pass
                    rows.append(rec)
        print(f"[XP] requested={min(start+batch_size,len(ids))}/{len(ids)} collected_unique={len({r['source_id'] for r in rows})}",flush=True)

    xp=pd.DataFrame(rows)
    if xp.empty:
        raise RuntimeError(f"No Gaia XP continuous spectra retrieved; failed_batches={errors}")
    xp=xp.drop_duplicates("source_id")
    meta=src.copy()
    meta["source_id"]=pd.to_numeric(meta["source_id"],errors="coerce").astype("Int64").astype(str)
    merged=meta.merge(xp,on="source_id",how="inner")
    out.parent.mkdir(parents=True,exist_ok=True)
    merged.to_csv(out,index=False)
    print(f"[OK] Gaia XP matched={len(merged)}/{len(src)} ({len(merged)/len(src):.3f}) batches_failed={errors} -> {out}")
    print(merged.star_truth_class.value_counts().to_string())
    if len(merged)<100:
        raise RuntimeError(f"XP coverage too low for prototype: {len(merged)} rows")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--features",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--batch-size",type=int,default=40)
    a=p.parse_args(); run(a.features,a.out,a.batch_size)

if __name__=="__main__": main()
