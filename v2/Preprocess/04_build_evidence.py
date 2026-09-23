"""Stage 4: convert measured features into traceable per-feature evidence.

No arbitrary probabilities are generated: calibration-backed evidence models will
be added here, with missing measurements remaining masked/neutral.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def run(features: Path, out: Path) -> Path:
    df=pd.read_csv(features); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False); return out
def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser(); p.add_argument("--features",type=Path,default=root/"features.csv"); p.add_argument("--out",type=Path,default=root/"evidence.csv"); a=p.parse_args(); run(a.features,a.out)
if __name__=="__main__": main()
