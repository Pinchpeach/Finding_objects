#!/usr/bin/env python3
"""Galaxies with both a DESI DR1 and an SDSS spectrum (2.7.0), to check the
DESI FastSpecFit emission-line route against the established SDSS one.

* DESI: desi_dr1.agngal (FastSpecFit lines) on NOIRLab Data Lab, joined with
  the Data Lab 1.5" crossmatch desi_dr1.x1p5__zpix__sdss_dr17__specobj;
  GALAXY spectra with z < 0.3 (H-alpha inside both spectrographs),
  random subsample (random_id), primary spectrum only.
* SDSS: Portsmouth, else MPA-JHU lines for the matched specobjid, fetched with
  the production collector code (Get_data/sdss_spectroscopy.py: _lines).

Output: v2/benchmark/desi_lines_truth/overlap.csv.gz
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH.parent / "Get_data"))
import desi_fastspec as df_  # noqa: E402
import sdss_spectroscopy as ss  # noqa: E402

OUT = BENCH / "desi_lines_truth"
XM = "desi_dr1.x1p5__zpix__sdss_dr17__specobj"


def xmatch_key(s) -> tuple[str, str, str]:
    """The Data Lab crossmatch stores zpix's own row key in id1 (not TARGETID):
    find which zpix column holds it."""
    c = s.search(f"SELECT column_name FROM tap_schema.columns WHERE table_name = '{XM}'").to_table()
    names = [str(x) for x in c["column_name"]]
    print("crossmatch columns:", names, flush=True)
    sample = s.search(f"SELECT TOP 3 id1, id2 FROM {XM}").to_table()
    print(sample, flush=True)
    v = sample["id1"][0]
    zc = [
        str(x)
        for x in s.search("SELECT column_name FROM tap_schema.columns WHERE table_name = 'desi_dr1.zpix'").to_table()[
            "column_name"
        ]
    ]
    cand = [n for n in zc if "id" in n.lower() and n.lower() != "targetid"] + ["targetid"]
    print("zpix id-like columns:", cand, flush=True)
    lit = f"'{v}'" if isinstance(v, str) else str(int(v))
    for n in cand:
        try:
            t = s.search(f"SELECT TOP 1 targetid FROM desi_dr1.zpix WHERE {n} = {lit}").to_table()
        except Exception as exc:
            print(n, "->", str(exc)[:100], flush=True)
            continue
        print(n, "->", len(t), flush=True)
        if len(t):
            return "id1", "id2", n
    raise SystemExit("no zpix column matches the crossmatch id1")


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Get_data"))
    import throttle

    throttle.install()  # 3-5 s before every archive request (2.33.0)
    import pyvo

    p = argparse.ArgumentParser()
    p.add_argument("--random-max", type=float, default=3.0, help="random_id cut (0-100) on agngal")
    p.add_argument("--limit", type=int, default=4000)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    s = pyvo.dal.TAPService(df_.TAP_URL)
    tid, sid, zkey = xmatch_key(s)
    cols = [
        "targetid",
        "target_ra",
        "target_dec",
        "z",
        "spectype",
        "zcat_primary",
        *[f"{v}_{x}" for v in df_.LINES.values() for x in ("flux", "flux_ivar")],
        "halpha_ew",
        "halpha_ew_ivar",
        *df_.EXTRA,
    ]
    q = (
        f"SELECT TOP {a.limit} " + ", ".join("a." + c for c in cols) + f", x.{sid} AS specobjid "
        f"FROM desi_dr1.agngal AS a JOIN desi_dr1.zpix AS zp ON zp.targetid = a.targetid "
        f"JOIN {XM} AS x ON x.{tid} = zp.{zkey} "
        f"WHERE a.spectype = 'GALAXY' AND a.z < 0.3 AND a.random_id < {a.random_max}"
    )
    print(q, flush=True)
    d = s.search(q).to_table().to_pandas()
    print("DESI x SDSS galaxies:", len(d), flush=True)
    if d.empty:
        raise SystemExit("empty DESI x SDSS sample")
    prim = d.zcat_primary.astype(str).str.lower().isin(["true", "t", "1"])
    d = d[prim].drop_duplicates("targetid")
    d = df_.standardise(d)
    d = d.rename(columns={c: "desi_" + c for c in d.columns if c.startswith("line_")})
    print("specobjid dtype:", d.specobjid.dtype, d.specobjid.head(3).tolist(), flush=True)
    # SDSS specObjID is unsigned 64-bit; a signed bigint column wraps above 2**63.
    d["specobjid"] = d.specobjid.map(lambda v: str(int(v) % 2**64))
    sd = ss._lines(d.specobjid.tolist())
    sd = sd.rename(columns={c: "sdss_" + c for c in sd.columns if c != "specobjid"})
    out = d.merge(sd, on="specobjid", how="left")
    print("with SDSS lines:", int(out["sdss_line_ha_flux"].notna().sum()), flush=True)
    out.to_csv(OUT / "overlap.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()
