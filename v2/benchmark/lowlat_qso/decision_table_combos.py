#!/usr/bin/env python3
"""The decision table of the survey-count switches combined with the association rules (2.62.2): one row per combination, every number from a table written by the other tools.

    python decision_table_combos.py --inputs results_2026-11-27h/inputs --assoc ../association_ambiguity/results_2026-11-27f --out results_2026-11-27h/decision_table.csv

Rows (the work order of 2026-11-27, task 차): base; surveys2 and surveys3 as they are (reference); surveys2 + spectro_keep; same,nearest; same,nearest + surveys2;
same,nearest + surveys2 + spectro_keep; same,nearest + surveys3; and (2026-11-28, task b) V2_POSERR_UNITS=fixed + same,nearest + surveys2 (the three together).  ``spectro_keep`` acts only on objects with a spectral class QSO, which the blind low-latitude and
deep COSMOS runs do not have: those columns of a ``+spectro_keep`` row are those of the same row without it, and the spectroscopic column is the one that tells them apart.

Columns (inputs in ``--inputs``):
  history                  which of the data was used to pick the thresholds / switches this row stands on, and which is unused (set C only)
  lowlat_conf_*, lowlat_cal_*   ``lowlat_confirmation.csv`` / ``lowlat_calibration.csv`` (``combos_table.py``): sample-quasar recall, quasars lost against the base,
                           QSO labels that are not sample quasars per deg^2 (all / Legacy Surveys cones / cones without it, bootstrap over regions), and the objects lost
                           and gained against the base matched by position
  spectro_held             ``held_{b,d}_{base,same_nearest}.csv`` (``spectro_held.py``): objects with a spectral class QSO (SDSS, LAMOST, DESI) that the base labels QSO and
                           the row does not, over the 32 of the 15 + 17 cones
  cosmos_*                 ``faint_cost.py tables`` on the 26 deep COSMOS fields (the latitude limit lifted): Chandra type 1 AGN the base labels QSO and the row does not,
                           their QSO recall, and the claims at 22 <= r < 24 (label QSO or flagged candidate: purity and recall of type 1)
  assoc_*                  COSMOS2020 association truth (``association_truth``): false / missed rate and extra fragment objects of the association rules (the survey switches act
                           after Stage 1, so a row's association is that of its ``same_nearest`` / base part)
"""

from __future__ import annotations

import sys

import argparse
import math
from pathlib import Path

import pandas as pd

ROWS = [  # name, association, low-latitude / COSMOS variant key, spectroscopic column (None = no switch), +spectro_keep
    ("base", "base", "base", None, False),
    ("surveys2", "base", "surveys2", "surveys2", False),
    ("surveys3", "base", "surveys3", "surveys3", False),
    ("surveys2+spectro_keep", "base", "surveys2", "surveys2_keep", True),
    ("same_nearest", "same_nearest", "same_nearest", None, False),
    ("same_nearest+surveys2", "same_nearest", "same_nearest_surveys2", "surveys2", False),
    ("same_nearest+surveys2+spectro_keep", "same_nearest", "same_nearest_surveys2", "surveys2_keep", True),
    ("same_nearest+surveys3", "same_nearest", "same_nearest_surveys3", "surveys3", False),
    # 2.62.6 (order of 2026-11-28, task b): the three switches together; the association columns are those of fixed + same,nearest without the survey-count switch
    ("fixed+same_nearest+surveys2", "fixed_same_nearest", "fixed_same_nearest_surveys2", "surveys2", False),
    # 2.62.7 (order of 2026-11-28, task b, addition): the same with V2_LOWLAT_QSO=surveys2,lit_keep (the NED / SIMBAD QSO exempt from the survey-count rule); the association is that of the row above
    ("fixed+same_nearest+surveys2+lit_keep", "fixed_same_nearest", "fixed_same_nearest_surveys2_litkeep", "surveys2", False),
]
HELD_KEY = {"fixed+same_nearest+surveys2+lit_keep": "fixed_same_nearest_litkeep"}  # held_{b,d}_<key>.csv of the spectroscopic cones; the association columns still use the row's own ``assoc``
HISTORY = {
    "base": "no threshold; reference",
    "surveys2": "the 3 / 4 survey rule was chosen on the 169 low-latitude calibration cones + 9 COSMOS fields and checked on the 140 confirmation cones (2.61.3-2.61.5); the 32 spectroscopic QSO are the objects that motivated spectro_keep",
    "surveys3": "as surveys2",
    "surveys2+spectro_keep": "spectro_keep was written after the 5 held spectroscopic QSO were seen (2.61.5): the 32 are not independent of it",
    "same_nearest": "0.3'' / 3x chosen on COSMOS fields 1-9; fields 10-26 and the 140 cones were seen once (pooled counts) before the constants were fixed and used again to reject 'best' and to restrict 'profiles'; 2.61.8",
    "same_nearest+surveys2": "both choices above; the combination was not measured before this table",
    "same_nearest+surveys2+spectro_keep": "both choices above",
    "same_nearest+surveys3": "both choices above",
    "fixed+same_nearest+surveys2+lit_keep": "the three choices and lit_keep (2.62.4: written after the 16 literature QSO labels of the real-use COSMOS field were seen to be erased by surveys2; the blind sets have no NED / SIMBAD rows, so only the real-use field can move)",
    "fixed+same_nearest+surveys2": "all three choices; V2_POSERR_UNITS=fixed was chosen on the 179 regions of the unit study (no threshold), was never measured together with the other two before this row; the base of every column is the legacy-unit base",
}
UNUSED = "the only sample no threshold or switch has been fitted on is set C (LOCKED_TEST_SET_C.md); it has not been run with these combinations"


def frac(k, n) -> str:
    return f"{int(k)}/{int(n)}"


def lowlat(tab: pd.DataFrame, key: str, prefix: str) -> dict:
    r = tab.set_index("variant").loc[key]
    out = {
        f"{prefix}_sample_quasars_qso": frac(r.quasars_qso, r.quasars),
        f"{prefix}_recall": f"{r.recall:.3f} [{r.recall_lo:.3f}-{r.recall_hi:.3f}]",
        f"{prefix}_quasars_lost_vs_base": int(r.quasars_lost_vs_control),
    }
    for lab, nm in (("all", "false_all"), ("LS", "false_LS_cones"), ("noLS", "false_noLS_cones")):
        out[f"{prefix}_false_{lab}_per_deg2"] = f"{r[nm + '_per_deg2']:.0f} [{r[nm + '_lo']:.0f}-{r[nm + '_hi']:.0f}] (n={int(r[nm + '_n'])})"
    if key != tab.variant.iloc[0]:
        out[f"{prefix}_removed_vs_base_per_deg2"] = f"{r.exch_lost_per_deg2:.0f} (n={int(r.exch_lost)})"
        out[f"{prefix}_added_vs_base_per_deg2"] = f"{r.exch_gained_per_deg2:.1f} (n={int(r.exch_gained)})"
    else:
        out[f"{prefix}_removed_vs_base_per_deg2"] = out[f"{prefix}_added_vs_base_per_deg2"] = ""
    return out


def held(inputs: Path, assoc: str, col: str | None) -> str:
    if col is None:
        return "0/32 (no switch)"
    n = k = 0
    for part in ("b", "d"):
        d = pd.read_csv(inputs / f"held_{part}_{assoc}.csv")
        q = d[d.label_base == "QSO"]
        n += len(q)
        k += int((q[f"label_{col}"] != "QSO").sum())
    return frac(k, n)


def cosmos(loss: pd.DataFrame, claims: pd.DataFrame, key: str) -> dict:
    if key == "base":
        sel = lambda r: loss[(loss.variant == "same_nearest") & (loss.truth == "type1") & (loss.r == r)]  # noqa: E731
        out = {}
        for lab, rs in (("all", ["all"]),):
            x = sel("all")
            out["cosmos_type1_qso_recall"] = f"{x.recall_base.iloc[0]:.3f} ({int(x.qso_base.iloc[0])}/{int(x.n.iloc[0])})"
        out["cosmos_type1_lost_vs_base"] = "0 (control)"
        out["cosmos_type1_lost_r_lt_22"] = out["cosmos_type1_lost_22_24"] = "0 (control)"
    else:
        x = loss[(loss.variant == key) & (loss.truth == "type1")]
        a = x[x.r == "all"].iloc[0]
        out = {"cosmos_type1_qso_recall": f"{a.recall_variant:.3f} ({int(a.qso_variant)}/{int(a.n)})", "cosmos_type1_lost_vs_base": frac(a.lost, a.qso_base)}
        for lab, rs in (("r_lt_22", ["<20", "20-21", "21-22"]), ("22_24", ["22-23", "23-24"])):
            y = x[x.r.isin(rs)]
            out[f"cosmos_type1_lost_{lab}"] = frac(y.lost.sum(), y.qso_base.sum())
    c = claims[(claims.variant == key) & (claims.r == "22-24") & (claims.claim == "label QSO or candidate")]
    if len(c):
        c = c.iloc[0]
        out["cosmos_claim_22_24_label_or_candidate"] = f"purity {c.purity:.3f} ({int(c.type1_among_claims)}/{int(c.claims)}), recall {c.recall:.3f} ({int(c.type1_among_claims)}/{int(c.n_type1)})"
    c = claims[(claims.variant == key) & (claims.r == "22-24") & (claims.claim == "label QSO")]
    if len(c):
        c = c.iloc[0]
        out["cosmos_claim_22_24_label_only"] = f"purity {c.purity:.3f} ({int(c.type1_among_claims)}/{int(c.claims)}), recall {c.recall:.3f}"
    return out


def wilson_upper(k: int, n: int, z: float = 1.959964) -> float:
    if n == 0:
        return float("nan")
    p = k / n
    return 100.0 * (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def new_join_bound(assoc_dir: Path, assoc: str) -> dict:
    """The joins the association rule ADDS (rows not joined in the base, joined with it), against the COSMOS2020 truth: false / known, calibration + confirmation pooled, with the
    Wilson 95 % upper bound as it is.  0/68 (AllWISE) has an upper bound of 5.3 %, above the 1.8 % false rate of the joins the base makes, so it cannot be said that the new joins are
    better than the old ones (review of 2.61.8); the 1 % of the adoption criterion is not shown by it either."""
    if assoc == "base":
        return {}
    out, tk, tn = {}, 0, 0
    for cat in ("AllWISE", "2MASS PSC", "GALEX AIS"):
        k = n = 0
        for half in ("calibration", "confirmation"):
            e = pd.read_csv(assoc_dir / half / "cosmos" / "exchange.csv")
            sel = e[(e.variant == assoc) & (e.catalog == cat)]
            if sel.empty:  # 2.62.6 review: no exchange table for this association (fixed_same_nearest): leave the cells empty, not the same_nearest numbers
                return {}
            r = sel.iloc[0]
            k += int(r.new_false)
            n += int(r.new_correct + r.new_false)
        tk, tn = tk + k, tn + n
        out[f"assoc_new_joins_false_{cat.split()[0]}"] = f"{k}/{n} (upper {wilson_upper(k, n):.1f} %)"
    out["assoc_new_joins_false_all"] = f"{tk}/{tn} (upper {wilson_upper(tk, tn):.1f} %)"
    return out


def assoc_cols(assoc_dir: Path, assoc: str) -> dict:
    out = {}
    out.update(new_join_bound(assoc_dir, assoc))
    for half, name in (("calibration", "cal9"), ("confirmation", "conf17")):
        rates = pd.read_csv(assoc_dir / half / "cosmos" / "rates.csv").set_index(["variant", "catalog"])
        st = pd.read_csv(assoc_dir / half / "cosmos" / "structure.csv").set_index("variant")
        v = assoc  # "base", "same_nearest" or "fixed_same_nearest": the variant names of rates.csv / structure.csv
        for cat in ("AllWISE", "GALEX AIS"):
            r = rates.loc[(v, cat)]
            out[f"assoc_{name}_{cat.split()[0]}_false_missed_pct"] = f"{r.false_pct:.2f} / {r.missed_pct:.1f}"
        out[f"assoc_{name}_extra_fragment_objects"] = int(st.loc[v, "extra_fragment_objects"])
    return out


def labels(inputs: Path, key: str) -> dict:
    """Primary-label changes against the base: the 26 deep COSMOS fields (objects paired by position) and the three real-use fields (NGC 4522, COSMOS, plane)."""
    out = {}
    for name, f, tag in (("cosmos26", "cosmos_label_changes.csv", "cosmos"), ("real_use3", "real_use_label_changes.csv", "real")):
        t = pd.read_csv(inputs / f).set_index("variant")
        if key in t.index:
            r = t.loc[key]
            out[f"{tag}_labels_changed"] = f"{int(r.changed)} of {int(r.pairs)} (to QSO {int(r.to_QSO)}, from QSO {int(r.from_QSO)})"
        else:
            out[f"{tag}_labels_changed"] = "0 (control)"
    c = pd.read_csv(inputs / "real_use_counts.csv").set_index("variant")
    r = c.loc[key]
    out["real_use_qso_labels_ngc_cosmos_plane"] = f"{int(r.ngc_QSO)} / {int(r.cosmos_QSO)} / {int(r.plane_QSO)}"
    return out


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # benchmark/: run_info
import run_info as RI  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--assoc", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    conf = pd.read_csv(a.inputs / "lowlat_confirmation.csv")
    cal = pd.read_csv(a.inputs / "lowlat_calibration.csv")
    loss = pd.read_csv(a.inputs / "type1_loss_by_r.csv")
    claims = pd.read_csv(a.inputs / "claims.csv")
    rows = []
    for name, assoc, key, spec, keep in ROWS:
        row = dict(variant=name, history=HISTORY[name])
        row.update(lowlat(conf, key, "lowlat_conf"))
        row.update(lowlat(cal, key, "lowlat_cal"))
        row["spectroscopic_qso_held"] = held(a.inputs, HELD_KEY.get(name, assoc), spec)
        row.update(cosmos(loss, claims, key))
        row.update(labels(a.inputs, key))
        row.update(assoc_cols(a.assoc, assoc))
        rows.append(row)
    d = pd.DataFrame(rows)
    d.to_csv(a.out, index=False)
    print(UNUSED)
    with pd.option_context("display.width", 300, "display.max_columns", 60, "display.max_colwidth", 60):
        print(d.T.to_string())
    RI.write_args(a, ('inputs', 'assoc'), t0=t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
