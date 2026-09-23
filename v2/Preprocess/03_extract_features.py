"""Stage 3: derive classification features from integrated observations."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def run(objects: Path, out: Path) -> Path:
    df=pd.read_csv(objects); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False); return out
def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser(); p.add_argument("--objects",type=Path,default=root/"integrated_objects.csv"); p.add_argument("--out",type=Path,default=root/"features.csv"); a=p.parse_args(); run(a.objects,a.out)
if __name__=="__main__": main()
