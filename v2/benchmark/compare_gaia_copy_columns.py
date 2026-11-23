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
    if col == "flags_gspspec":  # 41-digit text ("F" + digits, gaia_dr3._gspspec_quality on both sides): no int
        return a.astype(str).str.strip().to_numpy() == b.astype(str).str.strip().to_numpy()
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
        if both.any() and c not in FLAGS and not c.startswith("classlabel"):
            # VizieR stores the values rounded (e.g. probabilities to 1e-4): the largest difference
            d = np.abs(pd.to_numeric(a[both], errors="coerce") - pd.to_numeric(b[both], errors="coerce"))
            out[c]["max_abs_diff"] = float(d.max())
            out[c]["max_rel_diff"] = float((d / pd.to_numeric(a[both], errors="coerce").abs().clip(lower=1e-30)).max())
    return out


def fields(paths: list[Path]) -> dict:
    cols = list(dict.fromkeys(g._PARAMP.values()))
    res = {}
    for p in paths:
        m = TAG.search(p.name)
        ra, dec, r = _num(m["ra"]), _num(m["dec"]), _num(m["r"])
        esa = pd.read_csv(p, low_memory=False)
        # the encodings fetch() applies to both paths (PR #73 review: flags_gspspec is "F" + 41 digits in the
        # stored ESA files, the bare VizieR value before _gspspec_quality)
        copy = g._gspspec_quality(g._vizier_fallback(ra, dec, r))
        res[p.stem] = compare_columns(esa, copy, cols)
        print(p.stem, json.dumps(res[p.stem]), flush=True)
    return res


def ucd(n: int) -> dict:
    """The copy's ESP-UCD at the positions of Best+2018 dwarfs with an ESA ESP-UCD Teff (matched within 5")."""
    from concurrent.futures import ThreadPoolExecutor

    t = pd.read_csv(UCD_TRUTH)
    t = t[t.teff_espucd.notna()].sample(min(n, int(t.teff_espucd.notna().sum())), random_state=1).reset_index(drop=True)

    def ask(row):
        try:
            d = g.vizier_cone("I/355/paramp", row.ra, row.dec, 5.0 / 60.0, ["Source", "Teff-UCD", "Flags-UCD"])
        except Exception as exc:  # noqa: BLE001
            return {"error": repr(exc)[:120]}
        if d is None or d.empty or "Teff-UCD" not in d:
            return {}
        d = d[pd.to_numeric(d["Teff-UCD"], errors="coerce").notna()]
        if d.empty:
            return {}
        k = (pd.to_numeric(d["Teff-UCD"], errors="coerce") - row.teff_espucd).abs().idxmin()
        return {"teff": float(d.loc[k, "Teff-UCD"]), "flags": d.loc[k, "Flags-UCD"]}

    with ThreadPoolExecutor(8) as ex:
        got = list(ex.map(ask, t.itertuples()))
    r = pd.DataFrame(got, index=t.index)
    ok = r.get("teff", pd.Series(np.nan, index=t.index)).notna()
    diff = (r["teff"] - t["teff_espucd"]).abs()[ok]
    out = {
        "asked": int(len(t)),
        "errors": int(r.get("error", pd.Series(dtype=object)).notna().sum()),
        "with_copy_teff_ucd": int(ok.sum()),
        "teff_within_1K": int((diff <= 1.0).sum()),
        "teff_max_abs_diff_K": float(diff.max()) if ok.any() else None,
        "flags_equal": int(_same(r["flags"][ok], t["flags_espucd"][ok], "flags_espucd").sum()) if ok.any() else 0,
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
