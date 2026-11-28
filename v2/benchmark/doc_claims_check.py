#!/usr/bin/env python3
"""The benchmark facts that the README and the documents quote, counted again from the committed data (2.62.7, task "머").

    python doc_claims_check.py --out OUT_DIR

For every claim: the value the documents give, the value counted from the committed files, the status (``ok``, ``differs``, ``not recountable`` with the reason) and every place that quotes it
(``file:line`` found by a regular expression over ``README.md``, ``v2/ALGORITHM.md``, ``v2/document/overview_content.py``, ``v2/document/deck_content.py``, ``v2/STATUS_2026-11-12.md`` and
``v2/benchmark/LOCKED_TEST_SET_C.md``).  Nothing is edited: the wrong statements go to ``v2/document/NEXT_RELEASE_DOCS.md`` and the documents are corrected at the next release.
Writes ``doc_claims_check.csv`` and prints the claims that differ.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
REPO = V2.parent
DOCS = [REPO / "README.md", V2 / "ALGORITHM.md", V2 / "document" / "overview_content.py", V2 / "document" / "deck_content.py", V2 / "STATUS_2026-11-12.md", V2 / "benchmark" / "LOCKED_TEST_SET_C.md"]
sys.path.insert(0, str(V2 / "benchmark"))
import run_info as RI  # noqa: E402


def cited(pattern: str) -> str:
    out = []
    rx = re.compile(pattern)
    for p in DOCS:
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if rx.search(line):
                out.append(f"{p.relative_to(REPO).as_posix()}:{i}")
    return "; ".join(out)


def sha_split(bid: str) -> str:
    import hashlib

    x = int(hashlib.sha256(bid.encode()).hexdigest()[:8], 16) % 10
    return "train" if x < 6 else ("calibration" if x < 8 else "test")


def claims() -> list[dict]:
    rows: list[dict] = []

    def add(cid, claim, quoted, recount, status, source, pattern, note=""):
        rows.append(dict(id=cid, claim=claim, quoted=quoted, recounted=recount, status=status, source=source, note=note, cited_at=cited(pattern) if pattern else ""))

    # ---- sky-spread SDSS benchmark ----
    sky = pd.read_csv(V2 / "benchmark" / "sdss_sky" / "truth.csv")
    sc = pd.read_csv(V2 / "benchmark" / "sdss_sky" / "scores.csv")
    fu = sc[(sc.model == "fusion")].set_index("subset")
    add("sky_objects", "sky-spread SDSS benchmark: objects", "9,999", f"{len(sky):,}", "ok" if len(sky) == 9999 else "differs", "benchmark/sdss_sky/truth.csv", r"9,999")
    pc = sky.truth_class.value_counts()
    add("sky_per_class", "objects per class", "3,333", "/".join(str(int(pc[c])) for c in ("STAR", "GALAXY", "QSO")), "ok" if (pc == 3333).all() else "differs", "benchmark/sdss_sky/truth.csv", r"3,333 per class|3,333")
    cells = int(sky.sky_cell.nunique())
    add("sky_cells", "equal-area sky cells", "768", f"{cells} occupied (STAR {sky[sky.truth_class == 'STAR'].sky_cell.nunique()}, GALAXY {sky[sky.truth_class == 'GALAXY'].sky_cell.nunique()}, QSO {sky[sky.truth_class == 'QSO'].sky_cell.nunique()})",
        "misleading", "benchmark/sdss_sky/truth.csv (sky_cell)", r"768", "768 is the size of the grid (24 bands uniform in sin Dec x 32 in RA, `build_sdss_sky_truth.py`); objects sit in 355 cells (the SDSS spectroscopic footprint covers part of the sky), so 'spread over 768 cells' overstates the coverage")
    a = fu.loc["all"]
    add("sky_accuracy", "sky-spread benchmark accuracy (fusion)", "93.79 % (93.24-94.30)", f"{a.acc:.2f} % ({a.acc_lo:.2f}-{a.acc_hi:.2f})", "ok" if abs(a.acc - 93.79) < 0.005 else "differs", "benchmark/sdss_sky/scores.csv", r"93\.79")
    add("sky_recalls", "recall STAR / GALAXY / QSO", "98.7 / 98.5 / 84.1 %", f"{a.recall_STAR:.1f} / {a.recall_GALAXY:.1f} / {a.recall_QSO:.1f}",
        "ok" if (round(a.recall_STAR, 1), round(a.recall_GALAXY, 1), round(a.recall_QSO, 1)) == (98.7, 98.5, 84.1) else "differs", "benchmark/sdss_sky/scores.csv", r"98\.7 / 98\.5 / 84\.1")
    r21 = fu.loc["r_bin=(21.0, 30.0]"]
    add("sky_r21", "r > 21: accuracy, QSO recall, star precision", "87.99 %, 71.6 %, 69.9 %", f"{r21.acc:.2f} %, {r21.recall_QSO:.1f} %, {r21.precision_STAR:.1f} %",
        "ok" if (round(r21.acc, 2), round(r21.recall_QSO, 1), round(r21.precision_STAR, 1)) == (87.99, 71.6, 69.9) else "differs", "benchmark/sdss_sky/scores.csv", r"87\.99")
    lo = sky[sky.gal_b.abs() < 20]
    lb = fu.loc["b_bin=(-0.001, 20.0]"]
    add("sky_lowb", "|b| < 20 deg: accuracy, galaxies, QSOs", "96.09 %, 32 galaxies, 49 QSOs", f"{lb.acc:.2f} %, {int((lo.truth_class == 'GALAXY').sum())} galaxies, {int((lo.truth_class == 'QSO').sum())} QSOs ({len(lo)} objects)",
        "ok" if (round(lb.acc, 2), (lo.truth_class == "GALAXY").sum(), (lo.truth_class == "QSO").sum()) == (96.09, 32, 49) else "differs", "benchmark/sdss_sky/truth.csv, scores.csv", r"96\.09")

    pl_sky = sky.groupby("truth_class").plate.nunique()
    add("sky_plates", "sky-spread benchmark: SDSS plates per class", "1,957-2,533 plates", f"{int(pl_sky.min()):,}-{int(pl_sky.max()):,} (STAR {int(pl_sky['STAR']):,}, QSO {int(pl_sky['QSO']):,}, GALAXY {int(pl_sky['GALAXY']):,}); {sky.plate.nunique():,} distinct",
        "ok" if (int(pl_sky.min()), int(pl_sky.max())) == (1957, 2533) else "differs", "benchmark/sdss_sky/truth.csv", r"1,957")

    # ---- old SDSS / DESI benchmarks ----
    sd = pd.read_csv(V2 / "benchmark" / "truth_data" / "ground_truth.csv")
    dx = pd.read_csv(V2 / "benchmark" / "desi_external" / "truth.csv")
    n_sd = int((sd.benchmark_id.map(sha_split) == "test").sum())
    n_dx = int((dx.benchmark_id.map(sha_split) == "test").sum())
    add("old_sdss_test", "old SDSS benchmark, test split", "n = 1,991", f"n = {n_sd:,}", "ok" if n_sd == 1991 else "differs", "benchmark/truth_data/ground_truth.csv (the split of validate_catalog_truth.py)", r"1,991")
    add("old_desi_test", "DESI external benchmark, test split", "n = 962", f"n = {n_dx:,}", "ok" if n_dx == 962 else "differs", "benchmark/desi_external/truth.csv (the split of validate_catalog_truth.py)", r"\b962\b")
    pl_all, pl_cls = int(sd.plate.nunique()), sd.groupby("truth_class").plate.nunique()
    add("old_plates", "SDSS plates of the old benchmark", "142 plates (7 for galaxies)", f"{pl_all} distinct plates ({int(pl_cls['GALAXY'])} for galaxies; per class STAR {int(pl_cls['STAR'])}, GALAXY {int(pl_cls['GALAXY'])}, QSO {int(pl_cls['QSO'])}); "
        f"{int(pl_cls.sum())} = the sum of the three per-class counts", "differs", "benchmark/truth_data/ground_truth.csv", r"142",
        "142 = 7 + 51 + 84, the per-class plate counts added although the classes share plates; first quoted in 2.51.3 (7d2f4af)")
    add("old_sdss_acc", "old SDSS / DESI test accuracy", "97.99 % / 90.33 %", "not recountable", "not recountable", "2.52.0 results; the data are committed, the 2.52.0 classifier is not (the rule baseline of today gives 91.47 % on the DESI test split, a different quantity)", r"97\.99")

    # ---- set C ----
    sc_ = pd.read_csv(V2 / "benchmark" / "locked_c" / "2.60.4" / "summary.csv").iloc[0]
    pool = pd.read_csv(V2 / "benchmark" / "locked_c" / "2.60.4" / "summary_by_pool.csv")
    run = json.loads((V2 / "benchmark" / "locked_c" / "2.60.4" / "run.json").read_text())
    add("setc_n", "locked test set C: objects, accuracy", "3,162 objects, 99.65 % (99.40-99.86)", f"{int(sc_.n):,} objects, {sc_.acc:.2f} % ({sc_.acc_lo:.2f}-{sc_.acc_hi:.2f})", "ok" if int(sc_.n) == 3162 and round(sc_.acc, 2) == 99.65 else "differs",
        "benchmark/locked_c/2.60.4/summary.csv", r"3,162")
    add("setc_regions", "locked test set C: regions", "60 regions", f"{run['fields_scored']} scored, {int(sc_.n_fields)} with truth (pools: " + ", ".join(f"{r.pool} {int(r.n_regions)}" for r in pool.itertuples()) + ")",
        "ok (60 scored; 59 have truth)", "benchmark/locked_c/2.60.4/run.json, summary_by_pool.csv", r"60 regions", "the 60th region (cpln has 12 planned, 11 with truth) has no truth objects; README's pool counts sum to 59")
    add("setc_classes", "locked test set C: share of stars, galaxies, QSOs", "95.26 % stars; about 143 galaxies and 7 QSOs", f"{pool.n_STAR.sum() / pool.n.sum() * 100:.2f} % stars ({int(pool.n_STAR.sum())}), {int(pool.n_GALAXY.sum())} galaxies, {int(pool.n_QSO.sum())} QSOs",
        "ok" if (round(pool.n_STAR.sum() / pool.n.sum() * 100, 2), pool.n_GALAXY.sum(), pool.n_QSO.sum()) == (95.26, 143, 7) else "differs", "benchmark/locked_c/2.60.4/summary_by_pool.csv", r"95\.26")
    p = pool.set_index("pool")
    add("setc_pools", "set C by pool: low latitude / south / LAMOST sky", "99.89 % (11 regions, 879), 99.08 % (218), 99.61 % (2,065)",
        f"{p.loc['cpln', 'acc']:.2f} % ({int(p.loc['cpln', 'n_regions'])} regions, {int(p.loc['cpln', 'n'])}), {p.loc['csth', 'acc']:.2f} % ({int(p.loc['csth', 'n'])}), {p.loc['clam', 'acc']:.2f} % ({int(p.loc['clam', 'n']):,})",
        "ok" if (round(p.loc["cpln", "acc"], 2), int(p.loc["cpln", "n"]), round(p.loc["csth", "acc"], 2), int(p.loc["clam", "n"])) == (99.89, 879, 99.08, 2065) else "differs", "benchmark/locked_c/2.60.4/summary_by_pool.csv", r"879")
    add("setc_dsc", "set C: Gaia DSC coverage, DSC alone, pipeline on the same objects", "98.0 %, 99.52 %, 99.81 %", f"{sc_.dsc_coverage:.1f} %, {sc_.baseline_dsc:.2f} %, {sc_.ours_on_dsc:.2f} %",
        "ok" if (round(sc_.dsc_coverage, 1), round(sc_.baseline_dsc, 2), round(sc_.ours_on_dsc, 2)) == (98.0, 99.52, 99.81) else "differs", "benchmark/locked_c/2.60.4/summary.csv", r"99\.52")

    # ---- COSMOS ----
    ae = pd.read_csv(V2 / "benchmark" / "deep_cosmos_confirmation" / "variants" / "accuracy_ece.csv")
    b = ae[ae.variant == "base"].set_index("split")
    add("cosmos17", "COSMOS, 17 new fields: objects, accuracy, ECE", "16,057 and 16,757; 96.68 % and 96.75 %; ECE 0.37 and 0.33 %",
        f"{int(b.loc['cal', 'n']):,} and {int(b.loc['test', 'n']):,}; {b.loc['cal', 'acc']:.2f} % and {b.loc['test', 'acc']:.2f} %; ECE {b.loc['cal', 'ece']:.3f} and {b.loc['test', 'ece']:.3f} %",
        "ok" if (int(b.loc["cal", "n"]), int(b.loc["test", "n"]), round(b.loc["cal", "acc"], 2), round(b.loc["test", "acc"], 2)) == (16057, 16757, 96.68, 96.75) else "differs", "benchmark/deep_cosmos_confirmation/variants/accuracy_ece.csv", r"16,057")
    pr = pd.read_csv(V2 / "benchmark" / "experiments" / "prior_layer_2_52" / "score" / "report.txt", sep=r"\s+", engine="python", nrows=27)
    pr = pr[(pr.group == "cosmos")]
    t = pr[pr.split == "test"].set_index("variant")
    add("cosmos_test_fields", "COSMOS test fields (2.52.0): objects, accuracy before / after the prior layer, ECE", "12,245; 96.36 % (was 94.48 %); ECE 0.37 % (was 1.52 %)",
        f"{int(t.loc['ucosmos', 'n']):,}; {t.loc['ucosmos', 'label_acc']:.2f} % (was {t.loc['base', 'label_acc']:.2f} %); ECE {t.loc['ucosmos', 'ece']:.3f} % (was {t.loc['base', 'ece']:.3f} %)",
        "ok" if (int(t.loc["ucosmos", "n"]), round(t.loc["ucosmos", "label_acc"], 2), round(t.loc["base", "label_acc"], 2)) == (12245, 96.36, 94.48) else "differs", "benchmark/experiments/prior_layer_2_52/score/report.txt", r"12,245")
    al = pr[pr.split == "all"].set_index("variant")
    add("cosmos9", "COSMOS, 9 deep fields (2.51.0): objects, accuracy", "28,194 objects, 94.31 % (91.09 % always GALAXY)", f"2.52.0 report of the same fields: {int(al.loc['base', 'n']):,} objects, base label accuracy {al.loc['base', 'label_acc']:.2f} %",
        "differs by 1 object / not recountable for 2.51.0", "benchmark/experiments/prior_layer_2_52/score/report.txt", r"28,194", "the 2.51.0 run itself is not committed; the 2.52.0 base run of the same nine fields has 28,195 objects")

    # ---- LS-GBM ----
    rep = json.loads((V2 / "benchmark" / "desi_gbm_truth" / "train_report.json").read_text())
    byr = rep["holdout_accuracy_by_r"]
    w = sum(v["n"] * v["acc"] for v in byr.values()) / sum(v["n"] for v in byr.values())
    n_gbm = sum(len(c) for c in pd.read_csv(V2 / "benchmark" / "desi_gbm_truth" / "train.csv.gz", usecols=["targetid"], chunksize=100000))
    add("gbm_rows", "LS-GBM: DESI spectra it was trained on", "149,769", f"{n_gbm:,} rows in train.csv.gz; the fit used {rep['train_rows']:,} (+ {rep['holdout_rows']:,} held out = {rep['train_rows'] + rep['holdout_rows']:,})",
        "differs" if rep["train_rows"] + rep["holdout_rows"] != 149769 else "ok", "benchmark/desi_gbm_truth/train.csv.gz, train_report.json", r"149,769", "the list has 149,769 rows; the report (2.44.0) fitted on 132,207 and held out 14,447")
    add("gbm_acc", "LS-GBM test accuracy", "95.6 %", f"hold-out {rep['holdout_accuracy'] * 100:.1f} % ({w * 100:.1f} % weighted over the r bins; 95.6 % is the 21-22 bin)", "differs", "benchmark/desi_gbm_truth/train_report.json", r"95\.6 %",
        "the quoted 95.6 % is not the hold-out accuracy of the committed report (96.0 %); it is the accuracy of one r bin, or a value of an earlier fit")

    # ---- section 8 of the README: the r > 22 high-confidence GALAXY flag on the 17 new COSMOS fields ----
    hc = pd.read_csv(V2 / "benchmark" / "deep_cosmos_confirmation" / "highconf" / "new17.csv")
    h = hc[(hc.truth_reading == "cosmos2020") & hc.split.isin(["cal", "test"])]  # the table also has a pooled row ("all")
    al = hc[(hc.truth_reading == "cosmos2020") & (hc.split == "all")].iloc[0]
    n_hc, pur, low = int(h.hc_b.sum()), float(al.purity_b), float(al.purity_b_lower84)
    add("hc17", "r > 22 high-confidence GALAXY on the 17 new COSMOS fields: flagged objects, purity, 84 % lower bound", "24,169 flagged; purity 0.983 (0.982)", f"{n_hc:,} flagged (calibration {int(h[h.split == 'cal'].hc_b.sum()):,} + test {int(h[h.split == 'test'].hc_b.sum()):,}); purity {pur:.4f} ({low:.4f}, pooled row)",
        "ok" if n_hc == 24169 == int(al.hc_b) and round(pur, 3) == 0.983 and round(low, 3) == 0.982 else "differs", "benchmark/deep_cosmos_confirmation/highconf/new17.csv", r"24,169")

    # ---- the 520-object reference validation (README section 7: 2.47.0) ----
    rv = pd.read_csv(V2 / "reference_objects" / "validation" / "reference_validation_summary.csv")
    plan = pd.read_csv(V2 / "reference_objects" / "validation" / "plan.csv")
    ref = pd.read_csv(V2 / "reference_objects" / "reference_objects.csv.gz", usecols=["type", "catalog_name", "name"]).drop_duplicates()

    def tot(mode):
        x = rv[rv["mode"] == mode]
        return int(x.coarse_ok.sum()), int(x[x.coarse_ok.notna()].matched.sum()), int(x.type_ok.sum()), int(x[x.type_ok.notna()].matched.sum())

    (bc, bcn, bt, btn), (fc, fcn, ft, ftn) = tot("blind"), tot("full")
    ok = (bc, bcn, bt, btn, fc, fcn, ft, ftn) == (410, 458, 202, 441, 407, 463, 253, 460)
    add("ref520_scores", "520 literature-confirmed objects: blind / full coarse-class and sub-type accuracy (2.47.0)", "blind 89.5 % / 45.8 %; full 87.9 % / 55.0 %",
        f"blind {100 * bc / bcn:.1f} % ({bc}/{bcn}) / {100 * bt / btn:.1f} % ({bt}/{btn}); full {100 * fc / fcn:.1f} % ({fc}/{fcn}) / {100 * ft / ftn:.1f} % ({ft}/{ftn})",
        "ok" if ok else "differs", "reference_objects/validation/reference_validation_summary.csv", r"520 literature-confirmed|520-object")
    n_types, per = plan.type.nunique(), plan.groupby("type").size()
    present = int(plan.merge(ref.assign(_in=1), on=["type", "catalog_name", "name"], how="left")._in.fillna(0).sum())
    add("ref520_design", "520 objects, 52 types, 10 each", "520, 52, 10 each", f"{len(plan)} plan rows, {n_types} types, {int(per.min())}-{int(per.max())} each", "ok" if (len(plan), n_types, int(per.min()), int(per.max())) == (520, 52, 10, 10) else "differs",
        "reference_objects/validation/plan.csv", r"520 literature-confirmed|520 reference objects")
    add("ref520_in_list", "the 520 validated objects are objects of the published reference list (reference_objects.csv.gz)", "implied (the list is the source of the 520)", f"{present} of {len(plan)} plan objects are in the published list today (520 of 520 in the 2.46.1 list)",
        "ok" if present == len(plan) else "differs", "reference_objects/reference_objects.csv.gz vs validation/plan.csv", r"520 reference objects",
        "the list was redrawn by the 2.46.2 squash (a6d47e1): the table changed after the plan was drawn from the 2.46.1 table; see the report")

    # ---- cited in the README, data committed, NOT recounted in this pass (see the report, section on limits) ----
    for cid, claim, quoted, pat, where in (
        ("cand_purity", "'QSO?' candidate flag on the 21 deep COSMOS fields: purity, recall", "purity 29/119 = 24 % (18-33 %), recall 47/97 = 48 % (39-58 %)", r"29/119", "WORK_REPORT_2026-11-24b.md, benchmark/DEEP_COSMOS_EXPANSION.md"),
        ("agn33", "type-1 AGN at r >= 24 that received the QSO label", "none of 33", r"none of 33", "benchmark/cosmos_xray_agn/"),
        ("lit_only_2361", "COSMOS 2' field: objects with only a NED or SIMBAD type", "2,361 of 3,621 (2.54.0)", r"2,361 of 3,621", "ALGORITHM.md (2.54.0), the 2.54.0 work report"),
    ):
        add(cid, claim, quoted, "not recounted in this pass", "not recounted", where, pat, "data are committed; the recount needs the 2.54.0 / 2.56.0 classifier output of the deep fields, which this pass did not rerun")

    # ---- not recountable here ----
    add("indep_fields", "independent blind fields, sets A and B: objects", "24,663 objects (200 regions each)", "not recountable", "not recountable", "raw data on the validation-data branch only (233 MB); scores in benchmark/independent_fields/", r"24,663")
    return rows


def markdown(t: pd.DataFrame) -> str:
    """The table of the report: claim, quoted, recounted, status, where it is cited (the first three places and a count)."""
    out = ["| id | 무엇 | 문서에 적힌 값 | 커밋된 자료로 다시 센 값 | 판정 | 인용 위치 |", "|---|---|---|---|---|---|"]
    for r in t.itertuples():
        where = [w for w in str(r.cited_at).split("; ") if w and w != "nan"]
        shown = ", ".join(f"`{w}`" for w in where[:3]) + (f" 외 {len(where) - 3}곳" if len(where) > 3 else "")
        out.append(f"| {r.id} | {r.claim} | {r.quoted} | {r.recounted} | **{r.status}** | {shown} |".replace("\n", " "))
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    t = pd.DataFrame(claims())
    t.to_csv(a.out / "doc_claims_check.csv", index=False)
    (a.out / "doc_claims_table.md").write_text(markdown(t), encoding="utf-8")
    with pd.option_context("display.width", 250, "display.max_colwidth", 70):
        print(t[["id", "quoted", "recounted", "status"]].to_string(index=False))
    RI.write(a.out, [V2 / "benchmark" / d for d in ("sdss_sky", "truth_data", "desi_external", "locked_c", "deep_cosmos_confirmation/variants", "desi_gbm_truth")], t0=t0, note="documents are not edited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
