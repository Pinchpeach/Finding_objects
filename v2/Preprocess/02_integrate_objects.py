"""Stage 2: build one-row-per-object integrated data.

Consumes the source-association product. The full wide-table merge is implemented
after Stage 1's scientific association model is calibrated.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def run(associations: Path, out: Path) -> Path:
    df=pd.read_csv(associations)
    out.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(out,index=False)
    return out

def main():
    root=Path(__file__).resolve().parent; p=argparse.ArgumentParser(); p.add_argument("--associations",type=Path,default=root/"source_association.csv"); p.add_argument("--out",type=Path,default=root/"integrated_objects.csv"); a=p.parse_args(); run(a.associations,a.out)
if __name__=="__main__": main()
