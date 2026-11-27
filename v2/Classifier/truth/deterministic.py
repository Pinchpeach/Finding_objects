"""Order-free, seeded selection of independent truth rows (2.61.9).

Why this exists.  The truth lists used to be "the first N rows the archive answers" (a VizieR ``row_limit`` without a sort key), and the validator then
drew ``DataFrame.sample(n, random_state=42)`` from them.  A fixed seed does not fix a sample whose input is another set of rows in another order, and
an archive may answer in any order ("The order of the rows MAY be arbitrary unless an ORDER BY clause is specified", IVOA ADQL 2.1, Sect. 2.2; for a
sample, Sandve et al. 2013, Rule 6: note the underlying random seed).  Over the 25 bot commits since 2026-10-25 the variability classes had 6-7
different sets of truth ids each.

The rule here needs no row order: every candidate gets the key SHA-256("<seed>|<truth_id>") and a class keeps the ``k`` smallest keys (a bottom-k
sample; the same ids are chosen from any permutation of the candidates, and a candidate that is not among the ``k`` smallest does not change the
choice when it is removed or others are added).  Ties and duplicates are broken by ``truth_id`` itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

SEED = "independent-truth-v1"
GROUP = ("truth_axis", "truth_class")


def rank_key(truth_id, seed: str = SEED) -> str:
    return hashlib.sha256(f"{seed}|{truth_id}".encode("utf-8")).hexdigest()


def ids_sha256(ids) -> str:
    """Hash of a set of ids, independent of their order."""
    return hashlib.sha256("\n".join(sorted(str(i) for i in ids)).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bottom_k(df: pd.DataFrame, k: int, by=GROUP, seed: str = SEED) -> pd.DataFrame:
    """The ``k`` rows of every group with the smallest rank key; one row per ``truth_id``; sorted by group and ``truth_id``.

    The result is the same for every ordering of the rows of ``df``.
    """
    if df.empty:
        return df
    d = df.copy()
    d["truth_id"] = d["truth_id"].astype(str)
    for c in ("ra", "dec"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    by = [c for c in by if c in d]
    d = d.sort_values([*by, "truth_id", *[c for c in ("ra", "dec") if c in d]], kind="mergesort")
    d = d.drop_duplicates([*by, "truth_id"], keep="first")
    d["_rank"] = [rank_key(i, seed) for i in d["truth_id"]]
    d = d.sort_values([*by, "_rank", "truth_id"], kind="mergesort")
    d = d.groupby(by, group_keys=False, sort=False).head(k) if by else d.head(k)
    return d.drop(columns="_rank").sort_values([*by, "truth_id"], kind="mergesort").reset_index(drop=True)
