#!/usr/bin/env python3
"""Do the order-key variants change how much the tie order (``V2_ASSOC_TIE_ORDER``) decides? (2.62.7, task "너" item 2)

    python tie_order_interaction.py --fields-root ROOT --out OUT [--field-glob '*']

``ROOT/<field>/raw/<tag>/*.csv``.  For every order-key variant (base, allwise_order, allwise_sigma, floored, allwise) and every tie order (brightness = the default, position, file) Stage 1 runs
(``run_variant.py`` in a child process with the variant's environment), then the objects (sets of detection ids) of the three tie orders are compared per variant: how many objects exist in
one tie order only.  ``file`` is the order of 2.60.x (the row of the input file decides ties); ``brightness`` and ``position`` do not depend on the file's order.  A variant whose key has
fewer ties leaves less to the tie order, so the file-order difference should shrink; ``floored`` maps many rows to one value (the PSF/6 floor) and should enlarge it.
Writes ``tie_order_interaction.csv``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_info as RI  # noqa: E402

VARIANTS = {
    "base": {"V2_POSERR_NATIVE": "", "V2_ASSOC_ORDER_KEY": ""},
    "allwise": {"V2_POSERR_NATIVE": "allwise", "V2_ASSOC_ORDER_KEY": ""},
    "allwise_order": {"V2_POSERR_NATIVE": "allwise_order", "V2_ASSOC_ORDER_KEY": ""},
    "allwise_sigma": {"V2_POSERR_NATIVE": "allwise_sigma", "V2_ASSOC_ORDER_KEY": ""},
    "floored": {"V2_POSERR_NATIVE": "", "V2_ASSOC_ORDER_KEY": "floored"},
}
TIES = ("brightness", "position", "file")


def partition(a: pd.DataFrame) -> set:
    return {tuple(sorted(g)) for _, g in a.groupby("object_id").detection_id}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fields-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--field-glob", default="*")
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    fields = sorted(p.name for p in a.fields_root.glob(a.field_glob) if p.is_dir())
    for v, env in VARIANTS.items():
        for t in TIES:
            d = a.out / v / t
            if (d / "done").exists():
                continue
            e = {**{k: x for k, x in os.environ.items() if not k.startswith("V2_")}, **env, "V2_ASSOC_TIE_ORDER": t, "PYTHONHASHSEED": "0", "V2_CACHE": "0"}
            subprocess.run([sys.executable, str(HERE / "run_variant.py"), "--fields-root", str(a.fields_root), "--field-glob", a.field_glob, "--out", str(d)], env=e, check=True,
                           capture_output=True)  # fmt: skip
            (d / "done").write_text("ok\n")
    rows = []
    for v in VARIANTS:
        for f in fields:
            p = {t: partition(pd.read_csv(a.out / v / t / f / "source_association.csv", low_memory=False)) for t in TIES}
            n = len(p["brightness"])
            rows.append(dict(variant=v, field=f, objects=n, differ_file_vs_brightness=len(p["file"] ^ p["brightness"]) // 2, differ_position_vs_brightness=len(p["position"] ^ p["brightness"]) // 2,
                             differ_file_vs_position=len(p["file"] ^ p["position"]) // 2))  # fmt: skip
    t = pd.DataFrame(rows)
    t.to_csv(a.out / "tie_order_interaction.csv", index=False)
    s = t.groupby("variant", sort=False)[["objects", "differ_file_vs_brightness", "differ_position_vs_brightness", "differ_file_vs_position"]].sum()
    print(s.to_string())
    RI.write_args(a, ["fields_root"], t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
