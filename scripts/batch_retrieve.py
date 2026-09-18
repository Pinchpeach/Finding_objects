"""Retrieve a reproducible ~1000-object SDSS sample with resumable retries.

Stage 1 intentionally focuses on data acquisition. Classification is downstream.
"""
from __future__ import annotations
import argparse, json, random, time
from pathlib import Path
import requests
from finding_objects.sdss import read_skyserver_csv

BASE="https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"
TIMEOUT=45

def query(sql, retries=5):
    last=None
    for attempt in range(retries+1):
        try:
            r=requests.get(BASE,params={"cmd":sql,"format":"csv"},timeout=TIMEOUT)
            r.raise_for_status()
            return read_skyserver_csv(r.text)
        except requests.RequestException as e:
            last=e
            if attempt<retries: time.sleep(min(30,2**attempt))
    raise RuntimeError("SDSS retrieval exhausted retries") from last

def append(path, rec):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f: f.write(json.dumps(rec)+"\n")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--count",type=int,default=1000); p.add_argument("--seed",type=int,default=2609); p.add_argument("--checkpoint",type=Path,required=True); a=p.parse_args()
    done={}
    if a.checkpoint.exists():
        for line in a.checkpoint.read_text().splitlines():
            if line.strip():
                x=json.loads(line); done[x["window_id"]]=x
    rng=random.Random(a.seed)
    # Many small random windows avoid one expensive global random-sort query.
    windows=[(rng.uniform(120,240),rng.uniform(-2,55)) for _ in range(600)]
    rows=[]; failures=[]
    for wid,(ra,dec) in enumerate(windows,1):
        if wid in done:
            rec=done[wid]
            if rec.get("status")=="ok": rows.extend(rec.get("rows",[]))
            continue
        if len(rows)>=a.count: break
        sql=f"""SELECT TOP 10 p.objid,p.ra,p.dec,p.u,p.g,p.r,p.i,p.z
FROM dbo.fGetNearbyObjEq({ra},{dec},5.0) n
JOIN PhotoObj p ON p.objid=n.objid
WHERE p.clean=1
ORDER BY n.distance"""
        try:
            df=query(sql)
            got=df.to_dict(orient="records")
            append(a.checkpoint,{"window_id":wid,"status":"ok","rows":got})
            rows.extend(got)
        except Exception as e:
            rec={"window_id":wid,"status":"failed","ra":ra,"dec":dec,"error":str(e)}
            append(a.checkpoint,rec); failures.append(rec)
    # de-duplicate exact IDs while preserving retrieval order
    unique=[]; seen=set()
    for r in rows:
        oid=r.get("objid")
        if oid and oid not in seen:
            seen.add(oid); unique.append(r)
        if len(unique)>=a.count: break
    out=a.checkpoint.parent; out.mkdir(parents=True,exist_ok=True)
    import pandas as pd
    pd.DataFrame(unique).to_csv(out/"sample.csv",index=False)
    (out/"summary.json").write_text(json.dumps({"requested":a.count,"retrieved":len(unique),"failed_windows":len(failures),"complete":len(unique)>=a.count},indent=2))
    if len(unique)<a.count:
        raise SystemExit(2)

if __name__=="__main__": main()
