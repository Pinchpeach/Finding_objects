"""Stage 5: fuse calibrated evidence into object likelihood vectors."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def run(evidence: Path, out: Path) -> Path:
    df=pd.read_csv(evidence); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False); return out
def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser(); p.add_argument("--evidence",type=Path,default=root/"evidence.csv"); p.add_argument("--out",type=Path,default=root/"likelihood_vectors.csv"); a=p.parse_args(); run(a.evidence,a.out)
if __name__=="__main__": main()
