#!/usr/bin/env python3
"""Stage 1: deduplicate raw detections and conservatively associate counterparts."""
from __future__ import annotations
import argparse,math
from pathlib import Path
import pandas as pd
FLOOR_ARCSEC=0.15; MAX_RADIUS_ARCSEC=2.0; SIGMA_LIMIT=5.0; AMBIG_RATIO=1.5
def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None
def sep_arcsec(ra1,de1,ra2,de2):
    dra=math.radians(ra2-ra1); d1=math.radians(de1); d2=math.radians(de2)
    a=math.sin((d2-d1)/2)**2+math.cos(d1)*math.cos(d2)*math.sin(dra/2)**2
    return math.degrees(2*math.asin(min(1,math.sqrt(a))))*3600
def poserr(row):
    vals=[]
    for a,b in (("ra_error","dec_error"),("raMeanErr","decMeanErr"),("errMaj","errMin")):
        x,y=f(row.get(a)),f(row.get(b))
        if x is not None and y is not None:
            vals.append(max(x,y)*(.001 if a=="ra_error" else 1.0))
    return max(vals) if vals else None
def load(raw):
    rows=[]; seen=set(); skipped=0
    for path in sorted(raw.glob("*.csv")):
        if path.name.startswith(("collection_summary_","ngc4522_")): continue
        try: df=pd.read_csv(path)
        except Exception: continue
        if not {"ra","dec"}.issubset(df.columns): continue
        for i,r in df.iterrows():
            ra,de=f(r.get("ra")),f(r.get("dec"))
            if ra is None or de is None: continue
            cat=str(r.get("catalog",path.stem)); cid=str(r.get("catalog_object_id","")).strip()
            # Prefer stable catalog identity; fall back to catalog + rounded coordinates.
            key=(cat,"id",cid) if cid and cid.lower() not in {"nan","none"} else (cat,"sky",round(ra,7),round(de,7))
            if key in seen: skipped+=1; continue
            seen.add(key)
            rows.append({"detection_id":f"{path.stem}:{i}","input_file":path.name,"catalog":cat,
              "catalog_object_id":cid or str(i),"object_name":str(r.get("object_name","")),
              "ra":ra,"dec":de,"poserr_arcsec":poserr(r),"source_row":int(i)})
    return rows,skipped
def run(raw_dir,out):
    det,skipped=load(raw_dir); groups=[]; records=[]
    for d in det:
        candidates=[]
        for gi,g in enumerate(groups):
            if d["catalog"] in g["catalogs"]: continue
            s=sep_arcsec(d["ra"],d["dec"],g["ra"],g["dec"])
            sigma=math.sqrt((d["poserr_arcsec"] or FLOOR_ARCSEC)**2+(g["err"] or FLOOR_ARCSEC)**2)
            radius=min(MAX_RADIUS_ARCSEC,max(FLOOR_ARCSEC,SIGMA_LIMIT*sigma))
            if s<=radius: candidates.append((s/sigma,s,gi))
        candidates.sort(); ambiguous=len(candidates)>1 and candidates[1][0]<=candidates[0][0]*AMBIG_RATIO
        if candidates and not ambiguous:
            norm,s,gi=candidates[0]; g=groups[gi]; oid=g["id"]; n=g["n"]
            g["ra"]=(g["ra"]*n+d["ra"])/(n+1); g["dec"]=(g["dec"]*n+d["dec"])/(n+1)
            g["n"]+=1; g["catalogs"].add(d["catalog"]); g["err"]=min(g["err"],d["poserr_arcsec"] or FLOOR_ARCSEC)
            status="matched"; sep=s; score=norm
        else:
            oid=f"OBJ{len(groups)+1:06d}"; groups.append({"id":oid,"ra":d["ra"],"dec":d["dec"],"n":1,
              "catalogs":{d["catalog"]},"err":d["poserr_arcsec"] or FLOOR_ARCSEC})
            status="ambiguous_new" if ambiguous else "new"; sep=candidates[0][1] if candidates else None
            score=candidates[0][0] if candidates else None
        records.append({**d,"object_id":oid,"association_status":status,"match_separation_arcsec":sep,
          "normalized_separation":score,"candidate_count":len(candidates)})
    out.parent.mkdir(parents=True,exist_ok=True); pd.DataFrame(records).to_csv(out,index=False)
    print(f"[OK] detections={len(records)} deduplicated={skipped} groups={len(groups)} -> {out}"); return out
def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser()
    p.add_argument("--raw-dir",type=Path,default=root.parent/"rawdata"); p.add_argument("--out",type=Path,default=root/"source_association.csv")
    a=p.parse_args(); run(a.raw_dir,a.out)
if __name__=="__main__": main()
