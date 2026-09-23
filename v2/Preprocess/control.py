"""Run the independent preprocessing stages in order without hiding failures."""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
STAGES=["01_source_association.py","02_integrate_objects.py","03_extract_features.py","04_build_evidence.py","05_likelihood_vectors.py"]

def run_all() -> pd.DataFrame:
    records=[]
    for stage in STAGES:
        start=time.monotonic()
        proc=subprocess.run([sys.executable,str(ROOT/stage)],cwd=ROOT,text=True,capture_output=True)
        records.append({"stage":stage,"status":"ok" if proc.returncode==0 else "error","returncode":proc.returncode,"elapsed_seconds":round(time.monotonic()-start,3),"stdout":proc.stdout[-4000:],"stderr":proc.stderr[-4000:]})
        if proc.returncode != 0:
            break
    summary=pd.DataFrame(records); summary.to_csv(ROOT/"preprocess_summary.csv",index=False); return summary

def main():
    p=argparse.ArgumentParser(); p.parse_args(); s=run_all(); print(s[["stage","status","elapsed_seconds"]].to_string(index=False)); raise SystemExit(0 if len(s)==len(STAGES) and (s.status=="ok").all() else 1)
if __name__=="__main__": main()
