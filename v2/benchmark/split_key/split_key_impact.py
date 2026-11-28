#!/usr/bin/env python3
"""What changes if the train / calibration / test split is keyed on a stable object identifier instead of the row-number ``benchmark_id`` (2.62.7, task 거 item 3; DESIGN STUDY, nothing is changed).

    python split_key_impact.py --out OUT

The split of every benchmark is ``SHA-256(salt + key)`` (first 8 hex digits mod 10: < 6 train, < 8 calibration, else test; ``validate_catalog_truth.py:split_for``, the star / WD
scripts of ``Classifier`` add the salts ``star-wd:`` and ``wd-subtype:``).  The key is ``benchmark_id``, which the builder writes as a row number of the list it just built (``TRD000001``
...), so adding or removing one object of a rebuilt list renumbers everything behind it.  For each table that is split by a row-number id the tool measures, against the current split:

* ``split_change.csv``   the split of every object with the key replaced by (a) the list's own identifier (``specobjid`` / ``external_id``) and (b) a coordinate string (RA, Dec to 1e-5 deg):
                         how many objects change split, and what share of the new test set was in the old train set (a fit on the old train would have seen it);
* ``class_balance.csv``  the class shares of the three splits under the current and the new keys (``split_change.csv``: the largest deviation of a split's class share from the share in the whole table);
* ``delete_one_row.csv`` the failure the change is meant to prevent: delete the object at row 100, renumber the list the way the builder does, and count the objects whose split changes
                         under the current key and under the stable keys;
* ``coord_collisions.csv`` objects that share a coordinate key.

The salt is kept for the new keys, so the comparison is between keys, not between hash functions.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(V2 / "benchmark"))
import run_info as RI  # noqa: E402

# name, file, salt, stable id column, class column, consumer
TABLES = [
    ("sdss_ground_truth", "benchmark/truth_data/ground_truth.csv", "", "specobjid", "truth_class", "validate_catalog_truth.py (the SDSS benchmark: fusion weights, GBM, calibration, every SDSS number)"),
    ("desi_external_truth", "benchmark/desi_external/truth.csv", "", "desi_targetid", "truth_class", "validate_catalog_truth.py without --split-all (the regression gate of evaluate-preprocess-coarse.yml, README's DESI test split n = 962, the fusion fit); the validation workflow scores --split all"),
    ("radio_xray_truth", "benchmark/radio_xray_truth/ground_truth.csv", "", "specobjid", "truth_class", "validate_catalog_truth.py (radio / X-ray benchmark)"),
    ("star_truth", "Classifier/star_truth.csv", "star-wd:", "specobjid", "star_truth_class", "train_validate_star_wd.py"),
    # Not split by its consumer (Codex review of 2.62.7): validate_star_wd_external.py splits only the SDSS frame (train / calibration) and predicts the WHOLE
    # external frame, so a split migration of this table would describe a partition that does not exist.  Kept for the coordinate-collision check only.
    ("lamost_star_external", "Classifier/lamost_star_external_truth.csv", "star-wd:", "external_id", "star_truth_class", "validate_star_wd_external.py (not split: every row is predicted)"),
    ("wd_subtype_truth", "Classifier/wd_subtype_truth.csv", "wd-subtype:", "external_id", "wd_subtype", "train_validate_wd_subtype.py"),
]
NAMES = ("train", "calibration", "test")
UNSPLIT = {"lamost_star_external"}  # tables whose consumer does not split them: only the coordinate collisions are counted


def split_of(keys: pd.Series, salt: str = "") -> np.ndarray:
    x = np.array([int(hashlib.sha256((salt + str(k)).encode()).hexdigest()[:8], 16) % 10 for k in keys])
    return np.where(x < 6, 0, np.where(x < 8, 1, 2))


def coord_key(d: pd.DataFrame) -> pd.Series:
    return d.ra.map(lambda v: f"{v:.5f}") + "," + d.dec.map(lambda v: f"{v:+.5f}")


def renumber(ids: pd.Series, n: int) -> list[str]:
    m = re.match(r"([A-Za-z_]+)(\d+)$", str(ids.iloc[0]))
    prefix, width = m.group(1), len(m.group(2))
    return [f"{prefix}{i + 1:0{width}d}" for i in range(n)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--delete-row", type=int, default=100)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    change, balance, delete, coll = [], [], [], []
    for name, rel, salt, stable, cls, consumer in TABLES:
        d = pd.read_csv(V2 / rel, low_memory=False)
        old = split_of(d.benchmark_id, salt)
        keys = {stable: d[stable], "coordinates": coord_key(d)}
        if name in UNSPLIT:
            k = keys["coordinates"]
            coll.append(dict(table=name, rows=len(d), rows_sharing_a_coordinate_key=int(k.duplicated(keep=False).sum())))
            continue
        for kname, k in keys.items():
            new = split_of(k, salt)
            ch = int((old != new).sum())
            n = len(d)
            p = 1.0 - sum(f * f for f in (0.6, 0.2, 0.2))
            se = float(np.sqrt(p * (1 - p) / n))
            whole = d[cls].value_counts(normalize=True)
            dev = lambda sp: round(100 * max(abs(d[sp == s2][cls].value_counts(normalize=True).reindex(whole.index, fill_value=0) - whole).max() for s2 in range(3)), 1)  # noqa: E731
            nt = int((new == 2).sum())
            from_train = int(((new == 2) & (old == 0)).sum())
            change.append(dict(table=name, key=kname, n=n, changed=ch, changed_pct=round(100 * ch / n, 2), expected_pct=56.0, se_pct=round(100 * se, 2),
                               within_3se=bool(abs(ch / n - p) <= 3 * se), max_class_share_dev_pp_current=dev(old), max_class_share_dev_pp_new=dev(new), new_test_n=nt, new_test_from_old_train=from_train,
                               new_test_from_old_train_pct=round(100 * from_train / max(1, nt), 1), consumer=consumer))
            for (o, nn), c in pd.crosstab(pd.Series(old, name="old"), pd.Series(new, name="new")).stack().items():
                change[-1][f"{NAMES[o]}->{NAMES[nn]}"] = int(c)
            if kname == "coordinates":
                dup = int(k.duplicated(keep=False).sum())
                coll.append(dict(table=name, rows=n, rows_sharing_a_coordinate_key=dup))
            for label, sp in (("benchmark_id", old), (kname, new)):
                for s in range(3):
                    sub = d[sp == s][cls].value_counts(normalize=True)
                    for c, share in sub.items():
                        balance.append(dict(table=name, key=label, split=NAMES[s], cls=c, n_split=int((sp == s).sum()), share_pct=round(100 * share, 1)))
        # delete one object, renumber like the builder, and count the objects (of those that remain) whose split changes
        r = a.delete_row - 1
        keep = d.drop(index=r).reset_index(drop=True)
        before = pd.Series(old, index=d.index).drop(index=r).reset_index(drop=True)
        after_id = split_of(pd.Series(renumber(d.benchmark_id, len(keep))), salt)
        row = dict(table=name, rows_after=len(keep), deleted_row=a.delete_row, changed_with_benchmark_id=int((before.to_numpy() != after_id).sum()))
        row["changed_pct_with_benchmark_id"] = round(100 * row["changed_with_benchmark_id"] / len(keep), 1)
        row["changed_with_stable_id"] = int((split_of(keep[stable], salt) != split_of(d[stable].drop(index=r).reset_index(drop=True), salt)).sum())
        row["changed_with_coordinates"] = int((split_of(coord_key(keep), salt) != split_of(coord_key(d).drop(index=r).reset_index(drop=True), salt)).sum())
        delete.append(row)
    pd.DataFrame(change).to_csv(a.out / "split_change.csv", index=False)
    pd.DataFrame(balance).to_csv(a.out / "class_balance.csv", index=False)
    pd.DataFrame(delete).to_csv(a.out / "delete_one_row.csv", index=False)
    pd.DataFrame(coll).to_csv(a.out / "coord_collisions.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(pd.DataFrame(change).drop(columns=["consumer"]).to_string(index=False))
        print(pd.DataFrame(delete).to_string(index=False))
        print(pd.DataFrame(coll).to_string(index=False))
    RI.write(a.out, [V2 / t[1] for t in TABLES], t0=t0, note="design study of the split key; reads the committed truth tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
