"""Run all independent preprocessing stages in order.

A failed stage is recorded but does not terminate the controller. Downstream
stages are attempted only when their required input exists.
"""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
STAGES=[
 ("01_source_association.py", ROOT/"source_association.csv"),
 ("02_integrate_objects.py", ROOT/"integrated_objects.csv"),
 ("03_extract_features.py", ROOT/"features.csv"),
 ("04_build_evidence.py", ROOT/"evidence.csv"),
 ("05_likelihood_vectors.py", ROOT/"likelihood_vectors.csv"),
]

def run_all():
    records=[]
    for stage,expected in STAGES:
        start=time.monotonic()
        try:
            proc=subprocess.run([sys.executable,str(ROOT/stage)],cwd=ROOT,text=True,capture_output=True,check=False)
            status="ok" if proc.returncode==0 and expected.exists() else "error"
            records.append({"stage":stage,"status":status,"returncode":proc.returncode,
              "output_exists":expected.exists(),"elapsed_seconds":round(time.monotonic()-start,3),
              "stdout":proc.stdout[-4000:],"stderr":proc.stderr[-4000:]})
        except Exception as exc:
            records.append({"stage":stage,"status":"error","returncode":-1,"output_exists":expected.exists(),
              "elapsed_seconds":round(time.monotonic()-start,3),"stdout":"","stderr":repr(exc)})
        if records[-1]["status"]!="ok":
            print(f"[WARN] {stage} failed; controller remains alive.")
    summary=pd.DataFrame(records); summary.to_csv(ROOT/"preprocess_summary.csv",index=False); return summary

def main():
    argparse.ArgumentParser().parse_args(); s=run_all()
    print(s[["stage","status","output_exists","elapsed_seconds"]].to_string(index=False))
    print("\nController finished; see preprocess_summary.csv for failures.")
if __name__=="__main__": main()
