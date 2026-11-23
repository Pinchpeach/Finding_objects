#!/usr/bin/env python3
"""Does the WHAN error rule (2.53.0) act on SDSS galaxies?  (2.56.0)

2.53.0 added the Portsmouth / MPA-JHU equivalent-width errors to the SDSS
collector, and measured the rule (retired only if EW(Ha) + 2 sigma < 3 A,
undecided within 2 sigma of 3 A) on DESI lines only.  The 2.55.0 evaluation
saw the SDSS query with the error columns fail and fall back to the query
without them, so whether the rule ever acts on SDSS lines was unknown.

This asks the collector (``sdss_spectroscopy._lines``, the code the pipeline
runs) for the lines of the SDSS spectra of the SDSS x DESI overlap benchmark
(``desi_lines_truth/overlap.csv.gz``), stores the two error columns, and
counts the line verdicts with and without them.

    python v2/benchmark/measure_sdss_ew_errors.py            # query SkyServer, then count
    python v2/benchmark/measure_sdss_ew_errors.py --offline  # count from the stored errors
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(BENCH.parent / "Get_data"))
import evaluate_subclass as ev  # noqa: E402

OVERLAP = BENCH / "desi_lines_truth" / "overlap.csv.gz"
ERRORS = BENCH / "desi_lines_truth" / "sdss_ew_errors.csv.gz"
OUT = BENCH / "desi_lines_truth" / "sdss_ew_error_metrics.json"
P = "sdss_dr18_spectroscopy__"
COLS = [
    "line_ha_flux",
    "line_ha_flux_err",
    "line_hb_flux",
    "line_hb_flux_err",
    "line_oiii5007_flux",
    "line_oiii5007_flux_err",
    "line_nii6584_flux",
    "line_nii6584_flux_err",
    "line_ha_ew",
    "line_nii6584_ew",
    "line_ha_ew_err",
    "line_nii6584_ew_err",
]


def collect(ids: list[str]) -> pd.DataFrame:
    import sdss_spectroscopy as s

    lines = s._lines(ids)
    print("line_query_status:", lines["line_query_status"].value_counts().to_dict(), flush=True)
    return lines[["specobjid", *COLS, "line_source"]]


def _row(r: dict, with_err: bool) -> dict:
    out = {}
    for c in COLS:
        if not with_err and c.endswith("_ew_err"):
            continue
        v = r.get(c)
        if v is not None and v == v:
            out[P + c] = v
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true")
    a = p.parse_args()
    ids = pd.read_csv(OVERLAP, usecols=["specobjid"], dtype=str)["specobjid"].dropna().drop_duplicates().tolist()
    if a.offline:
        lines = pd.read_csv(ERRORS, dtype={"specobjid": str})
    else:
        lines = collect(ids)
        lines.to_csv(ERRORS, index=False)
    sc = ev.load_subclass()
    recs = lines.to_dict("records")
    old = [sc.galaxy_lines(_row(r, False)) for r in recs]
    new = [sc.galaxy_lines(_row(r, True)) for r in recs]
    lines["without_err"] = [x[0] if x else "undecided" for x in old]
    lines["with_err"] = [x[0] if x else "undecided" for x in new]
    has_ew = lines["line_ha_ew"].notna()
    near = lines["line_ha_ew"].between(1.0, 5.0)
    within = (lines["line_ha_ew"] - 3.0).abs() < 2 * lines["line_ha_ew_err"]
    out = {
        "spectra": len(ids),
        "with_ha_ew": int(has_ew.sum()),
        "with_ha_ew_err": int((has_ew & lines["line_ha_ew_err"].notna()).sum()),
        "with_nii_ew_err": int((lines["line_nii6584_ew"].notna() & lines["line_nii6584_ew_err"].notna()).sum()),
        "line_source": lines["line_source"].value_counts(dropna=False).to_dict(),
        "median_ha_ew_err": round(float(lines["line_ha_ew_err"].median()), 3),
        "ew_1_to_5_A": int(near.sum()),
        "ew_1_to_5_A_within_2sigma_of_3A": int((near & within).sum()),
        "verdict_without_err": lines["without_err"].value_counts().to_dict(),
        "verdict_with_err": lines["with_err"].value_counts().to_dict(),
        "changed": int((lines["without_err"] != lines["with_err"]).sum()),
        "changed_from_to": {
            f"{a_} -> {b_}": int(n)
            for (a_, b_), n in lines[lines["without_err"] != lines["with_err"]]
            .groupby(["without_err", "with_err"])
            .size()
            .items()
        },
    }
    OUT.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
