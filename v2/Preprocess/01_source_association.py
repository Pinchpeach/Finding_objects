"""Stage 1: associate raw catalog detections with physical source candidates.

Initial scaffold. Scientific association scoring (positional uncertainty, PSF/FWHM,
footprint and chance-coincidence terms) is intentionally kept in this stage.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def run(raw_dir: Path, out: Path) -> Path:
    rows=[]
    for path in sorted(raw_dir.glob("*.csv")):
        if path.name.startswith(("collection_summary_", "ngc4522_")): continue
        try:
            df=pd.read_csv(path)
        except Exception as exc:
            rows.append({"input_file":path.name,"status":"read_error","rows":0,"error":repr(exc)})
            continue
        rows.append({"input_file":path.name,"status":"loaded","rows":len(df),"error":""})
    out.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out,index=False)
    return out

def main():
    p=argparse.ArgumentParser(); p.add_argument("--raw-dir",type=Path,default=Path(__file__).resolve().parents[1]/"rawdata"); p.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"source_association.csv")
    a=p.parse_args(); run(a.raw_dir,a.out)
if __name__=="__main__": main()
