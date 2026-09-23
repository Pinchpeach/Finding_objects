#!/usr/bin/env python3
"""Stage 2: build one-row-per-object wide records from Stage-1 associations."""
from __future__ import annotations
import argparse,re
from pathlib import Path
import pandas as pd

def prefix(catalog):
    s=re.sub(r"[^a-z0-9]+","_",str(catalog).lower()).strip("_")
    return s[:32] or "catalog"
def run(associations,raw_dir,out):
    assoc=pd.read_csv(associations); raw_cache={}
    rows=[]
    for oid,g in assoc.groupby("object_id",sort=False):
        rec={"object_id":oid,"ra":g["ra"].mean(),"dec":g["dec"].mean(),
             "association_members":len(g),"association_ambiguous":int((g["association_status"]=="ambiguous_new").any()),
             "association_confidence_min":pd.to_numeric(g.get("association_confidence"),errors="coerce").min(),
             "association_confidence_mean":pd.to_numeric(g.get("association_confidence"),errors="coerce").mean()}
        catalogs=[]
        for _,a in g.iterrows():
            fn=a["input_file"]
            if fn not in raw_cache:
                try: raw_cache[fn]=pd.read_csv(raw_dir/fn)
                except Exception: continue
            src=raw_cache[fn]
            idx=int(a["source_row"])
            if idx>=len(src): continue
            r=src.iloc[idx]; cat=str(a["catalog"]); catalogs.append(cat); pre=prefix(cat)
            rec[f"{pre}__catalog_object_id"]=a["catalog_object_id"]
            for col,val in r.items():
                if col in {"catalog","catalog_object_id","object_name","ra","dec"}: continue
                key=col if col not in rec else f"{pre}__{col}"
                if key not in rec or pd.isna(rec[key]): rec[key]=val
            # Preserve common rule columns unprefixed when available.
            for col in ("parallax","parallax_error","pmra","pmra_error","pmdec","pmdec_error","class","zwarning",
                        "classprob_dsc_combmod_quasar","classprob_dsc_combmod_galaxy","classprob_dsc_combmod_star",
                        "classprob_dsc_combmod_whitedwarf","classprob_dsc_combmod_binarystar","best_class_name","best_class_score"):
                if col in r and pd.notna(r[col]) and (col not in rec or pd.isna(rec[col])): rec[col]=r[col]
        rec["catalogs"]="|".join(sorted(set(catalogs))); rows.append(rec)
    df=pd.DataFrame(rows); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False)
    print(f"[OK] objects={len(df)} columns={len(df.columns)} -> {out}"); return out
def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--associations",type=Path,default=root/"source_association.csv")
    p.add_argument("--raw-dir",type=Path,default=root.parent/"rawdata")
    p.add_argument("--out",type=Path,default=root/"integrated_objects.csv")
    a=p.parse_args(); run(a.associations,a.raw_dir,a.out)
if __name__=="__main__": main()
