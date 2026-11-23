#!/usr/bin/env python3
"""Gaia: the VizieR I/355 copy's astrophysical parameters against the ESA archive (2.57.0 review).

``gaia_dr3._vizier_fallback`` (used while the ESA archive is down, e.g. for
the DR4 preparation) maps I/355/paramp columns to the archive's names
(``gaia_dr3._PARAMP``).  2.57.0 took ESP-UCD and FLAME to be absent from the
copy; I/355/paramp has them (Teff-UCD, Flags-UCD, Mass-Flame, Age-Flame,
Flags-Flame, Evol).  This checks that the copy's values equal the archive's:

* fields: raw Gaia files collected from the ESA archive
  (``gaia_base_query_status = tap``; the practical-use probe sets on the
  ``validation-data`` branch), the copy asked for the same cone;
* ultracool dwarfs: the Best et al. (2018) dwarfs with an ESA ESP-UCD Teff
  (``new_targets/truth/ucd_best2018_match.csv.gz``), the copy asked at their
  positions.

    python v2/benchmark/compare_gaia_copy_columns.py --gaia-files F1.csv F2.csv ... [--ucd N] [--out metrics.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH.parent / "Get_data"))
import gaia_dr3 as g  # noqa: E402

TAG = re.compile(r"ra(?P<ra>m?[0-9p]+)_dec(?P<dec>m?[0-9p]+)_r(?P<r>[0-9p]+)arcmin")
FLAGS = {"flags_espucd", "flags_flame", "flags_gspspec", "classlabel_espels_flag"}
UCD_TRUTH = BENCH / "new_targets" / "truth" / "ucd_best2018_match.csv.gz"


def _num(t: str) -> float:
    return float(t.replace("m", "-").replace("p", "."))


def _same(a: pd.Series, b: pd.Series, col: str) -> np.ndarray:
    if col in FLAGS or col.startswith("classlabel"):

        def norm(x):
            s = x.astype(str).str.strip()
            n = pd.to_numeric(s, errors="coerce")
            return np.where(n.notna(), n.fillna(-1).astype("int64").astype(str).str.zfill(2), s)

        return norm(a) == norm(b)
    x, y = pd.to_numeric(a, errors="coerce").to_numpy(float), pd.to_numeric(b, errors="coerce").to_numpy(float)
    return np.isclose(x, y, rtol=1e-4, atol=0.0)


def compare_columns(esa: pd.DataFrame, copy: pd.DataFrame, cols) -> dict:
    esa = esa.assign(source_id=pd.to_numeric(esa.source_id, errors="coerce").astype("Int64"))
    copy = copy.assign(source_id=pd.to_numeric(copy.source_id, errors="coerce").astype("Int64"))
    m = esa.merge(copy, on="source_id", how="inner", suffixes=("_esa", "_copy"))
    out = {"rows_esa": int(len(esa)), "rows_copy": int(len(copy)), "common_source_id": int(len(m))}
    for c in cols:
        a, b = m.get(c + "_esa"), m.get(c + "_copy")
        if a is None or b is None:
            out[c] = "missing in " + ("esa" if a is None else "copy")
            continue
        fa, fb = a.notna() & a.astype(str).str.strip().ne(""), b.notna() & b.astype(str).str.strip().ne("")
        both = fa & fb
        eq = _same(a[both], b[both], c) if both.any() else np.array([], bool)
        out[c] = {"esa": int(fa.sum()), "copy": int(fb.sum()), "both": int(both.sum()), "equal": int(eq.sum())}
    return out


def fields(paths: list[Path]) -> dict:
    cols = list(dict.fromkeys(g._PARAMP.values()))
    res = {}
    for p in paths:
        m = TAG.search(p.name)
        ra, dec, r = _num(m["ra"]), _num(m["dec"]), _num(m["r"])
        esa = pd.read_csv(p, low_memory=False)
        copy = g._vizier_fallback(ra, dec, r)
        res[p.stem] = compare_columns(esa, copy, cols)
        print(p.stem, json.dumps(res[p.stem]), flush=True)
    return res


def ucd(n: int) -> dict:
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astroquery.vizier import Vizier

    t = pd.read_csv(UCD_TRUTH)
    t = t[t.teff_espucd.notna()].sample(min(n, int(t.teff_espucd.notna().sum())), random_state=1).reset_index(drop=True)
    pos = SkyCoord(t.ra.to_numpy() * u.deg, t.dec.to_numpy() * u.deg)
    res = None
    for host in ("vizier.cfa.harvard.edu", "vizier.cds.unistra.fr", "vizier.iucaa.in"):
        v = Vizier(columns=["Source", "RA_ICRS", "DE_ICRS", "Teff-UCD", "Flags-UCD"], row_limit=-1)
        v.VIZIER_SERVER = host
        v.TIMEOUT = 300
        try:
            r = v.query_region(pos, radius=3 * u.arcsec, catalog="I/355/paramp")
            if len(r):
                res = r[0].to_pandas()
                break
        except Exception as exc:  # noqa: BLE001
            print("mirror failed", host, repr(exc)[:200], flush=True)
    if res is None:
        return {"error": "I/355/paramp not reachable"}
    res = res[res["Teff-UCD"].notna()]
    res["_q"] = res["_q"].astype(int) - 1
    best = res.sort_values("_q").drop_duplicates("_q")  # one row per asked position (the UCD row)
    m = t.join(best.set_index("_q"), how="inner")
    teq = np.isclose(m["Teff-UCD"].astype(float), m.teff_espucd.astype(float), rtol=1e-4)
    feq = _same(m["Flags-UCD"], m.flags_espucd, "flags_espucd")
    out = {
        "asked": int(len(t)),
        "with_copy_teff_ucd": int(len(m)),
        "teff_equal": int(teq.sum()),
        "flags_equal": int(feq.sum()),
        "teff_max_abs_diff_K": (
            float(np.nanmax(np.abs(m["Teff-UCD"].astype(float) - m.teff_espucd.astype(float)))) if len(m) else None
        ),
    }
    print("ucd", json.dumps(out), flush=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gaia-files", type=Path, nargs="*", default=[])
    p.add_argument("--ucd", type=int, default=200)
    p.add_argument("--out", type=Path, default=Path("gaia_copy_metrics.json"))
    a = p.parse_args()
    out = {"fields": fields(a.gaia_files), "ucd_best2018": ucd(a.ucd) if a.ucd else None}
    a.out.write_text(json.dumps(out, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
