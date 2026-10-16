#!/usr/bin/env python3
"""FastSpecFit measurements of the DESI benchmark galaxies (2.28.0).

The DESI truth sets (desi_external, desi_fusion) give the class and redshift
only.  To check photometric galaxy-activity criteria on faint galaxies (the
regime without SDSS spectra) this fetches, by TARGETID, the FastSpecFit line
fluxes, equivalent widths and the 4000 A break of the same spectra from
``desi_dr1.agngal`` on NOIRLab Data Lab (Moustakas et al. 2023; DESI DR1).
Columns that the table lacks are skipped (printed), so the script also serves
as a schema probe.

Output: v2/benchmark/desi_galaxy_activity/lines.csv.gz
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH.parent / "Get_data"))
import desi_fastspec as df_  # noqa: E402

OUT = BENCH / "desi_galaxy_activity"
WANT = [
    "targetid",
    "z",
    "zcat_primary",
    *[f"{v}_{x}" for v in df_.LINES.values() for x in ("flux", "flux_ivar")],
    "halpha_ew",
    "halpha_ew_ivar",
    "nii_6584_ew",
    "nii_6584_ew_ivar",
    "hbeta_ew",
    "hbeta_ew_ivar",
    "oiii_5007_ew",
    "oiii_5007_ew_ivar",
    "oii_3726_ew",
    "oii_3726_ew_ivar",
    "oii_3729_ew",
    "oii_3729_ew_ivar",
    "oii_3726_flux",
    "oii_3726_flux_ivar",
    "oii_3729_flux",
    "oii_3729_flux_ivar",
    "dn4000",
    "dn4000_ivar",
    "dn4000_model",
    *df_.EXTRA,
]
CHUNK = 300


def main() -> None:
    s = df_._service()
    have = {
        str(c).lower()
        for c in s.search(f"SELECT column_name FROM tap_schema.columns WHERE table_name = '{df_.TABLE}'")
        .to_table()["column_name"]
    }
    print("agngal columns:", sorted(have), flush=True)
    cols = [c for c in WANT if c in have]
    print("missing:", [c for c in WANT if c not in have], flush=True)
    truth = []
    for name in ("desi_external", "desi_fusion"):
        t = pd.read_csv(BENCH / name / "truth.csv", dtype={"desi_targetid": str})
        truth.append(t[t.truth_class.eq("GALAXY")][["benchmark_id", "desi_targetid", "z", "r_mag"]].assign(set=name))
    truth = pd.concat(truth, ignore_index=True)
    ids = sorted(set(truth.desi_targetid.dropna()))
    parts = []
    for i in range(0, len(ids), CHUNK):
        q = f"SELECT {', '.join(cols)} FROM {df_.TABLE} WHERE targetid IN ({', '.join(ids[i : i + CHUNK])})"
        parts.append(df_._query_with_retries(lambda q=q: s.search(q).to_table().to_pandas()))
        print(f"{min(i + CHUNK, len(ids))}/{len(ids)}: {len(parts[-1])} rows", flush=True)
    d = pd.concat(parts, ignore_index=True)
    prim = d.zcat_primary.astype(str).str.lower().isin(["true", "t", "1"])
    d = d[prim].drop_duplicates("targetid")
    d["desi_targetid"] = d.pop("targetid").astype("int64").astype(str)
    out = truth.merge(d.rename(columns={"z": "fsf_z"}), on="desi_targetid", how="left")
    print("galaxies:", len(truth), "with FastSpecFit:", int(out.fsf_z.notna().sum()), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "lines.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()
