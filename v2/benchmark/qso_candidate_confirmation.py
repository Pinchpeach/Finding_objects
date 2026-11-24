#!/usr/bin/env python3
"""Confirmation of the faint QSO candidate flag on more deep COSMOS fields (2.60.2).

The flag of 2.58.0 (``secondary_class = QSO``, ``FAINT_QSO_CANDIDATE``: not labelled QSO, 22 <= LS r < 24,
``p_qso`` >= 0.1) was measured on nine deep COSMOS fields, 21 Chandra type 1 in the four test fields: recall
0.33 (Wilson 0.17-0.55), purity 0.21 (0.10-0.37).  ``DEEP_COSMOS_EXPANSION.md`` fixed 17 more fields before any
of them was collected or classified (option A: threshold 0.1 fixed, the new fields are confirmation only).  This
script measures them with the definitions of 2.58.0 (``faint_qso_candidates.py``), per field, and gives the
intervals in two ways:

  Wilson     the binomial interval of the pooled counts (as in 2.58.0);
  bootstrap  fields drawn with replacement (the fields differ in X-ray depth and in how many objects they hold,
             so the pooled binomial interval is too narrow if the field-to-field spread is real), 2.5 / 97.5 %.

Definitions (22 <= LS r < 24, the edge cut of the measurement, truth classes as faint_qso_candidates.py):
  claim          an object labelled QSO or flagged as a candidate;
  recall         Chandra type 1 claimed / all Chandra type 1 (``label`` = only the QSO labels count);
  purity         Chandra type 1 among the claims that have a truth class (graded);
  purity range   the claims without any truth class (``ungraded``: no COSMOS2020 star / galaxy and no Chandra
                 source within 1") counted as all false / all true (a lower and an upper bound; Chandra misses
                 non-X-ray quasars, so the type-1 truth is itself a lower bound);
  false rate     candidates (not the labels) among the truth GALAXY / Chandra type 2 / STAR.
  ACS purity     the COSMOS2020 star / galaxy classes exist only where the HST/ACS F814W image does (68 % of the
                 COSMOS2020 rows of the central field 5, 30-37 % of the outer new fields).  Chandra type 1 are known
                 everywhere, so the purity above counts the type 1 of the whole field against the false claims of
                 the ACS part only: too high where the ACS covers part of a field.  ``purity_acs`` uses only the
                 claims that lie where the ACS has photometry (nearest COSMOS2020 row within MATCH_ARCSEC = 1.0" has ACSF814Wmag),
                 graded among them / all of them (the range for the ungraded ones, as above).

    python v2/benchmark/qso_candidate_confirmation.py --deep DIR --fields-file ALL26.csv --out OUT [--run base]

The groups: ``new17`` (the confirmation, split by number parity as everywhere), ``orig9`` (the nine of 2.58.0,
now from the ESA Gaia archive), ``orig9_cal`` (the five fields the threshold was chosen on), ``orig9_test``, and the
pooled ``all26`` and ``all26_without_orig_cal`` (the 21 fields the threshold was not chosen on).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parent
sys.path.insert(0, str(B))
import faint_qso_candidates as FQ  # noqa: E402
import measure_cosmos_xray_agn as X  # noqa: E402

T = 0.1  # the threshold of 2.58.0 (Preprocess/qso_options.CANDIDATE_P); not re-fitted
COUNTS = [
    "n_type1",
    "label_type1",
    "cand_type1",
    "n_galaxy",
    "n_type2",
    "n_star",
    "cand_galaxy",
    "cand_type2",
    "cand_star",
    "label_galaxy",
    "label_type2",
    "label_star",
    "claims_independent",
    "ungraded",
    "claims_acs",
    "graded_acs",
    "tp_acs",
]
PREDICTED = {"recall": 0.33, "purity": 0.21}  # DEEP_COSMOS_EXPANSION.md, written before any new field was classified


_CHANDRA = None


def chandra_count(ra: float, dec: float) -> int:
    """Chandra COSMOS Legacy sources inside the edge cut of a field (the X-ray depth proxy of select_deep_cosmos_2.py)."""
    global _CHANDRA
    import select_deep_cosmos_2 as S

    if _CHANDRA is None:
        _CHANDRA = S.chandra_positions()
    return S.count_within(ra, dec, *_CHANDRA, FQ.RADIUS_ARCMIN - FQ.EDGE_ARCMIN)


def field_counts(deep: Path, run: str, field: str, t: float = T) -> dict:
    """Counts of one field (22 <= r < 24)."""
    ra0, de0 = FQ.FIELDS[field]
    obj = pd.read_csv(
        deep / f"run_{run}" / field / "classified_objects.csv", low_memory=False, usecols=lambda c: c in FQ.COLS
    )
    m = FQ.match(obj, FQ.truth_table(deep, field))
    s = FQ.rbin(m, FQ.CAND_R_MIN, FQ.CAND_R_MAX)
    cand = FQ.candidate(s, t)
    lab = s.o_primary_class == "QSO"
    row = {"field": field, "split": FQ.split_of(field), "n_chandra": chandra_count(ra0, de0)}
    for k, name in (("TYPE1", "type1"), ("GALAXY", "galaxy"), ("TYPE2", "type2"), ("STAR", "star")):
        sel = s.truth == k
        row[f"n_{name}"] = int(sel.sum())
        row[f"cand_{name}"] = int((cand & sel).sum())
        row[f"label_{name}"] = int((lab & sel).sum())
    # independent objects (galaxy parts grouped under the host), inside the edge cut, claimed: graded or not
    o = obj[obj.parent_object_id.isna()]
    sep = X.sep_arcsec(ra0, de0, o.ra.to_numpy(float), o.dec.to_numpy(float)) / 60
    o = o[
        (sep <= FQ.RADIUS_ARCMIN - FQ.EDGE_ARCMIN)
        & o.std_mag__ls_r.ge(FQ.CAND_R_MIN)
        & o.std_mag__ls_r.lt(FQ.CAND_R_MAX)
    ]
    claim = (o.primary_class == "QSO") | (o.primary_class.ne("QSO") & (o.p_qso >= t))
    o = o[claim]
    row["claims_independent"] = len(o)
    row["ungraded"] = int((~o.object_id.isin(set(m.o_object_id))).sum())
    # claims inside the ACS part of the field: the COSMOS2020 row nearest to the claim has F814W photometry
    c20 = pd.read_csv(
        deep / field / "truth" / FQ.COSMOS2020, low_memory=False, usecols=["_RAJ2000", "_DEJ2000", "ACSF814Wmag"]
    )
    c20 = c20.dropna(subset=["_RAJ2000", "_DEJ2000"]).reset_index(drop=True)
    has_acs = pd.to_numeric(c20.ACSF814Wmag, errors="coerce").notna().to_numpy()
    if len(o) and len(c20):
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        i, sep, _ = SkyCoord(o.ra.to_numpy(float) * u.deg, o.dec.to_numpy(float) * u.deg).match_to_catalog_sky(
            SkyCoord(c20._RAJ2000.to_numpy(float) * u.deg, c20._DEJ2000.to_numpy(float) * u.deg)
        )
        in_acs = (sep.arcsec <= FQ.MATCH_ARCSEC) & has_acs[i]
    else:
        in_acs = np.zeros(len(o), bool)
    graded = o.object_id.isin(set(m.o_object_id)).to_numpy()
    type1 = o.object_id.isin(set(m[m.truth == "TYPE1"].o_object_id)).to_numpy()
    row["claims_acs"], row["graded_acs"], row["tp_acs"] = (
        int(in_acs.sum()),
        int((in_acs & graded).sum()),
        int((in_acs & type1).sum()),
    )
    row["acs_fraction"] = round(float(has_acs.mean()), 3) if len(c20) else float("nan")
    # the flag the pipeline wrote must be the threshold rule (2.58.0 verified this on two fields)
    flagged = obj[(obj.secondary_class_reason == "FAINT_QSO_CANDIDATE")]
    row["pipeline_flags"] = len(flagged)
    return row


def ratio(num: float, den: float) -> float:
    return float(num) / den if den else float("nan")


def stats(d: pd.DataFrame) -> dict:
    """The pooled numbers of a set of fields."""
    s = d[COUNTS].sum()
    claims_g = (
        s.label_type1
        + s.cand_type1
        + s.label_galaxy
        + s.cand_galaxy
        + s.label_type2
        + s.cand_type2
        + s.label_star
        + s.cand_star
    )
    tp = s.label_type1 + s.cand_type1
    return {
        "recall_label": ratio(s.label_type1, s.n_type1),
        "recall_union": ratio(tp, s.n_type1),
        "purity_union": ratio(tp, claims_g),
        "purity_low": ratio(tp, s.claims_independent) if s.claims_independent else float("nan"),
        "purity_high": ratio(tp + s.ungraded, s.claims_independent) if s.claims_independent else float("nan"),
        "purity_acs": ratio(s.tp_acs, s.graded_acs),
        "purity_acs_low": ratio(s.tp_acs, s.claims_acs),
        "purity_acs_high": ratio(s.tp_acs + s.claims_acs - s.graded_acs, s.claims_acs),
        "false_galaxy": ratio(s.cand_galaxy, s.n_galaxy),
        "false_type2": ratio(s.cand_type2, s.n_type2),
        "false_star": ratio(s.cand_star, s.n_star),
        "n_type1": s.n_type1,
        "type1_claimed": tp,
        "claims_graded": claims_g,
    }


def bootstrap(d: pd.DataFrame, nboot: int = 10000, seed: int = 20261124) -> dict:
    """Percentile 95 % intervals of ``stats`` with the fields drawn with replacement."""
    rng = np.random.default_rng(seed)
    n = len(d)
    vals = d[COUNTS].to_numpy(float)
    out = None
    idx = rng.integers(0, n, size=(nboot, n))
    s = vals[idx].sum(axis=1)  # (nboot, ncols)
    c = {name: s[:, i] for i, name in enumerate(COUNTS)}
    with np.errstate(divide="ignore", invalid="ignore"):
        tp = c["label_type1"] + c["cand_type1"]
        claims = (
            tp
            + c["label_galaxy"]
            + c["cand_galaxy"]
            + c["label_type2"]
            + c["cand_type2"]
            + c["label_star"]
            + c["cand_star"]
        )
        r = {
            "recall_label": c["label_type1"] / c["n_type1"],
            "recall_union": tp / c["n_type1"],
            "purity_union": tp / claims,
            "purity_acs": c["tp_acs"] / c["graded_acs"],
            "false_galaxy": c["cand_galaxy"] / c["n_galaxy"],
            "false_type2": c["cand_type2"] / c["n_type2"],
            "false_star": c["cand_star"] / c["n_star"],
        }
    return {k: tuple(float(x) for x in np.round(np.nanpercentile(v, [2.5, 97.5]), 4)) for k, v in r.items()}


def groups(f: pd.DataFrame) -> dict:
    n = f.field.str.rsplit("_", n=1).str[1].astype(int)
    f = f.assign(num=n)
    order = f.sort_values("n_chandra").field.tolist()  # the X-ray depth proxy, shallow to deep
    third = [
        set(order[: len(order) // 3]),
        set(order[len(order) // 3 : 2 * len(order) // 3]),
        set(order[2 * len(order) // 3 :]),
    ]
    return {
        "depth_shallow": f[f.field.isin(third[0])],
        "depth_middle": f[f.field.isin(third[1])],
        "depth_deep": f[f.field.isin(third[2])],
        "new17": f[f.num >= 10],
        "new17_cal": f[(f.num >= 10) & (f.num % 2 == 1)],
        "new17_test": f[(f.num >= 10) & (f.num % 2 == 0)],
        "orig9": f[f.num <= 9],
        "orig9_cal": f[(f.num <= 9) & (f.num % 2 == 1)],
        "orig9_test": f[(f.num <= 9) & (f.num % 2 == 0)],
        "all26": f,
        "all26_without_orig_cal": f[~((f.num <= 9) & (f.num % 2 == 1))],
    }


def summary(f: pd.DataFrame, nboot: int) -> pd.DataFrame:
    rows = []
    for name, d in groups(f).items():
        if not len(d):
            continue
        st = stats(d)
        bs = bootstrap(d, nboot) if len(d) > 1 else {}
        s = d[COUNTS].sum()
        tp = int(st["type1_claimed"])
        row = {
            "group": name,
            "fields": len(d),
            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()},
        }
        row["recall_label_wilson"] = X.wilson(int(s.label_type1), int(s.n_type1))
        row["recall_union_wilson"] = X.wilson(tp, int(s.n_type1))
        row["purity_union_wilson"] = X.wilson(tp, int(st["claims_graded"]))
        row["purity_acs_wilson"] = X.wilson(int(s.tp_acs), int(s.graded_acs))
        row["false_galaxy_wilson"] = X.wilson(int(s.cand_galaxy), int(s.n_galaxy))
        row["false_type2_wilson"] = X.wilson(int(s.cand_type2), int(s.n_type2))
        for k, v in bs.items():
            row[f"{k}_boot"] = v
        row["ungraded"] = int(s.ungraded)
        row["claims_independent"] = int(s.claims_independent)
        row["claims_acs"], row["graded_acs"], row["tp_acs"] = int(s.claims_acs), int(s.graded_acs), int(s.tp_acs)
        row["acs_fraction_mean"] = round(float(d.acs_fraction.mean()), 3)
        row["cand_galaxy"], row["n_galaxy"] = int(s.cand_galaxy), int(s.n_galaxy)
        row["cand_type2"], row["n_type2"] = int(s.cand_type2), int(s.n_type2)
        row["cand_star"], row["n_star"] = int(s.cand_star), int(s.n_star)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deep", type=Path, required=True)
    p.add_argument("--fields-file", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run", default="base")
    p.add_argument("--threshold", type=float, default=T)
    p.add_argument("--nboot", type=int, default=10000)
    a = p.parse_args()
    FQ.FIELDS = FQ.load_fields(a.fields_file)
    a.out.mkdir(parents=True, exist_ok=True)
    f = pd.DataFrame([field_counts(a.deep, a.run, name, a.threshold) for name in FQ.FIELDS])
    f["purity_union"] = (f.label_type1 + f.cand_type1) / (
        f.label_type1
        + f.cand_type1
        + f.label_galaxy
        + f.cand_galaxy
        + f.label_type2
        + f.cand_type2
        + f.label_star
        + f.cand_star
    ).replace(0, np.nan)
    f["type1_per_chandra"] = (f.n_type1 / f.n_chandra).round(3)
    f["recall_union"] = (f.label_type1 + f.cand_type1) / f.n_type1.replace(0, np.nan)
    f.to_csv(a.out / f"fields_{a.run}.csv", index=False)
    s = summary(f, a.nboot)
    s.to_csv(a.out / f"groups_{a.run}.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 60)
    print(f.round(3).to_string(index=False))
    print(s.drop(columns=[c for c in s.columns if c.endswith("_wilson") or c.endswith("_boot")]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
