#!/usr/bin/env python3
"""Build a conservative LAMOST WD subtype truth set for initial DA vs DB work."""

from __future__ import annotations
import argparse, time
from pathlib import Path
import numpy as np, pandas as pd

CAT = "J/MNRAS/509/2674/table3"


def pick(cols, names):
    return next((n for n in names if n in cols), None)


def run(out: Path, per_class=150):
    from astroquery.vizier import Vizier

    tabs = None
    last = None
    servers = ["vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.nao.ac.jp"]
    for server in servers:
        for attempt in range(3):
            try:
                q = Vizier(columns=["**"], row_limit=-1)
                q.VIZIER_SERVER = server
                tabs = q.get_catalogs(CAT)
                if tabs:
                    break
            except Exception as e:
                last = e
                print(f"[VizieR] server={server} attempt={attempt+1} failed: {e!r}", flush=True)
                time.sleep(2**attempt)
        if tabs:
            break
    if not tabs:
        raise RuntimeError(f"LAMOST WD table3 unavailable after mirrors: {last!r}")
    d = tabs[0].to_pandas()
    d.columns = [str(c).strip() for c in d.columns]
    tcol = pick(d.columns, ["SpType", "NType", "Type", "Sp", "Class", "SubClass"])
    racol = pick(d.columns, ["RAJ2000", "RAdeg", "RA_ICRS", "RA"])
    deccol = pick(d.columns, ["DEJ2000", "DEdeg", "DE_ICRS", "DE", "DEC"])
    idcol = pick(d.columns, ["Name", "ObsID", "GroupID"])
    if not all((tcol, racol, deccol, idcol)):
        raise KeyError(
            f"required columns missing; type={tcol} ra={racol} dec={deccol} id={idcol}; columns={list(d.columns)}"
        )
    raw = d[tcol].fillna("").astype(str).str.upper().str.strip()
    # Use only unambiguous pure primary labels for first benchmark.
    keep = raw.isin(["DA", "DB"])
    q = d.loc[keep].copy()
    q["wd_subtype"] = raw.loc[keep].to_numpy()
    q["ra"] = pd.to_numeric(q[racol], errors="coerce")
    q["dec"] = pd.to_numeric(q[deccol], errors="coerce")
    q["external_id"] = q[idcol].astype(str)
    q = q.dropna(subset=["ra", "dec"]).drop_duplicates("external_id")
    parts = []
    for cls in ("DA", "DB"):
        z = q[q.wd_subtype.eq(cls)].sort_values("external_id").head(per_class)
        if len(z) < 80:
            raise RuntimeError(f"insufficient {cls} truth: {len(z)}")
        parts.append(z)
    outdf = pd.concat(parts, ignore_index=True)[["external_id", "ra", "dec", "wd_subtype"]]
    outdf["star_truth_class"] = outdf["wd_subtype"]
    outdf["benchmark_id"] = [f"WDSUB{i+1:05d}" for i in range(len(outdf))]
    outdf["truth_source"] = "LAMOST_DR5_GUO2022_VISUAL_WD_TYPE"
    outdf["truth_quality"] = "PURE_DA_DB_LABEL"
    out.parent.mkdir(parents=True, exist_ok=True)
    outdf.to_csv(out, index=False)
    print(outdf.wd_subtype.value_counts().to_string())
    print(f"[OK] WD subtype truth rows={len(outdf)} -> {out}")
    return out


def main():
    p = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent
    p.add_argument("--out", type=Path, default=root / "wd_subtype_truth.csv")
    p.add_argument("--per-class", type=int, default=150)
    a = p.parse_args()
    run(a.out, a.per_class)


if __name__ == "__main__":
    main()
