#!/usr/bin/env python3
"""Sampled end-to-end cross-validation on independent per-axis truth sets.

Truth catalogues are never passed directly as evidence.  Each truth family uses
an explicitly separate collector set, so this measures independent evidence
coverage as well as classification accuracy.  UNKNOWN is an abstention and is
reported separately from classified-only accuracy.
"""

from __future__ import annotations
import argparse, collections, importlib.util, json, math, sys, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GET = ROOT / "Get_data"
PRE = ROOT / "Preprocess"
CLS = ROOT / "Classifier"
if str(GET) not in sys.path:
    sys.path.insert(0, str(GET))

COLLECTORS = {
    ("physical", "RGB"): ("gaia_dr3_physical_vizier",),
    ("physical", "AGB"): ("gaia_dr3_physical_vizier", "allwise", "twomass", "agb_suh2021"),
    ("variability", "RR_LYRAE"): ("gaia_dr3_variability_vizier", "gaia_dr3_variability_sos_vizier", "ztf_periodic"),
    ("variability", "CEPHEID"): ("gaia_dr3_variability_vizier", "gaia_dr3_variability_sos_vizier", "ztf_periodic"),
    ("variability", "MIRA"): ("gaia_dr3_variability_vizier", "gaia_dr3_variability_sos_vizier", "ztf_periodic"),
    ("variability", "LPV"): ("gaia_dr3_variability_vizier", "gaia_dr3_variability_sos_vizier", "ztf_periodic"),
    # ATNF is truth here and is deliberately excluded from evidence.
    ("compact", "PULSAR"): ("gaia_dr3", "chandra", "xmm", "first", "nvss", "tgss"),
    # Acker V/84 is truth; HASH is independent production evidence.
    ("phenomenon", "PN"): ("hash_pn",),
    # Asiago is truth; ASAS-SN is independent, but only covers a limited epoch.
    ("phenomenon", "SN"): ("asas_sn_supernova",),
}
SOS_KIND = {"RR_LYRAE": ("rr",), "CEPHEID": ("cep",), "MIRA": ("lpv",), "LPV": ("lpv",)}


def load_module(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    if s is None or s.loader is None:
        raise ImportError(path)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m


def run_cmd(args):
    import subprocess

    p = subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError("command failed: " + " ".join(map(str, args)) + "\n" + p.stderr[-3000:])


def partial_failure(frame) -> str:
    """The failed sub-queries a collector reports in a ``*_query_status`` column while returning the rows of the others
    (``agb_suh2021`` ``agb_query_status``, ``asas_sn_supernova`` ``sn_query_status``: ``error:<table>``); '' when none failed.

    Such a frame is not empty, so without this check it was logged ``ok`` and escaped the retry and the OK / DEGRADED gate (Codex review of 2.62.0).
    """
    bad = set()
    for c in getattr(frame, "columns", ()):
        if str(c).endswith("_query_status"):
            bad |= {str(v) for v in frame[c].astype(str) if str(v).strip().lower().startswith("error")}
    return ",".join(sorted(bad))


def collect(row, raw, radius):
    logs = []
    names = COLLECTORS.get((str(row.truth_axis), str(row.truth_class)), ())
    for name in names:
        try:
            mod = load_module(GET / f"{name}.py", f"truthval_{name}_{abs(hash(str(row.truth_id)))%1000000}")
            kwargs = {"kinds": SOS_KIND[str(row.truth_class)]} if name == "gaia_dr3_variability_sos_vizier" else {}
            frame = mod.fetch(float(row.ra), float(row.dec), radius, **kwargs)
            mod.save(frame, raw / f"{name}.csv")
            partial = partial_failure(frame)
            if partial:  # rows came back but a sub-query failed: an archive error like any other (archive_errors counts status error*)
                logs.append({"collector": name, "status": "error_partial", "rows": len(frame), "error": partial})
            else:
                logs.append({"collector": name, "status": "ok" if len(frame) else "empty", "rows": len(frame)})
        except Exception as exc:
            logs.append({"collector": name, "status": "error", "rows": 0, "error": repr(exc)})
    return logs


def select(frame, ra, dec, radius, entity=None):
    ras = pd.to_numeric(frame["ra"], errors="coerce")
    des = pd.to_numeric(frame["dec"], errors="coerce")
    # Wrap the RA difference into [-180, 180): a target near RA 0/360 deg
    # otherwise sees its neighbours across the wrap ~360 deg away.
    dra = ((ras - ra + 180) % 360 - 180) * math.cos(math.radians(dec))
    dde = des - dec
    sep = 3600 * (dra * dra + dde * dde) ** 0.5
    cand = frame.copy()
    cand["_sep"] = sep
    cand = cand[cand._sep <= radius * 60]
    if entity and "entity_kind" in cand.columns:
        sub = cand[cand.entity_kind.astype(str) == entity]
        if not sub.empty:
            cand = sub
    if cand.empty:
        if frame.empty:
            return None, math.nan
        i = sep.idxmin()
        return frame.loc[i], float(sep.loc[i])
    cand["_members"] = pd.to_numeric(cand.get("association_members"), errors="coerce").fillna(1)
    cand = cand.sort_values(["_members", "_sep"], ascending=[False, True])
    r = cand.iloc[0]
    return r, float(r._sep)


def evaluate_one(rec, base, radius):
    safe = str(rec.truth_id).replace("/", "_").replace(" ", "_")
    work = base / f"{rec.truth_axis}_{rec.truth_class}_{safe}"
    raw = work / "raw"
    pre = work / "pre"
    cls = work / "cls"
    for d in (raw, pre, cls):
        d.mkdir(parents=True, exist_ok=True)
    logs = collect(rec, raw, radius)
    usable = sum(x.get("rows", 0) for x in logs if x.get("status") == "ok")
    if not usable:
        return {
            "truth_id": rec.truth_id,
            "axis": rec.truth_axis,
            "truth_class": rec.truth_class,
            "predicted_class": "UNKNOWN",
            "status": "NO_EVIDENCE",
            "raw_score": math.nan,
            "match": False,
            "family_match": False,
            "classified": False,
            "sep_arcsec": math.nan,
            "collectors": json.dumps(logs),
        }
    run_cmd([PRE / "01_source_association.py", "--raw-dir", raw, "--out", pre / "source_association.csv"])
    run_cmd(
        [
            PRE / "02_integrate_objects.py",
            "--associations",
            pre / "source_association.csv",
            "--raw-dir",
            raw,
            "--out",
            pre / "integrated_objects.csv",
        ]
    )
    run_cmd(
        [
            PRE / "03_extract_features.py",
            "--objects",
            pre / "integrated_objects.csv",
            "--rules",
            PRE / "classification_rules.csv",
            "--out",
            pre / "features.csv",
        ]
    )
    run_cmd(
        [
            PRE / "04_build_evidence.py",
            "--features",
            pre / "features.csv",
            "--rules",
            PRE / "classification_rules.csv",
            "--out",
            pre / "evidence.csv",
        ]
    )
    run_cmd(
        [PRE / "05_likelihood_vectors.py", "--evidence", pre / "evidence.csv", "--out", pre / "likelihood_vectors.csv"]
    )
    run_cmd([CLS / "01_prepare_input.py", "--input", pre / "likelihood_vectors.csv", "--out", cls / "input.csv"])
    run_cmd([CLS / "control.py", "--input", cls / "input.csv", "--out", cls / "classified.csv"])
    df = pd.read_csv(cls / "classified.csv")
    entity = "transient_event" if rec.truth_class == "SN" else None
    row, sep = select(df, float(rec.ra), float(rec.dec), radius, entity)
    if row is None:
        return {
            "truth_id": rec.truth_id,
            "axis": rec.truth_axis,
            "truth_class": rec.truth_class,
            "predicted_class": "UNKNOWN",
            "status": "NO_OBJECT",
            "raw_score": math.nan,
            "match": False,
            "family_match": False,
            "classified": False,
            "sep_arcsec": math.nan,
            "collectors": json.dumps(logs),
        }
    axis = str(rec.truth_axis)
    pred = str(row.get(f"{axis}_class", "UNKNOWN"))
    status = str(row.get(f"{axis}_status", ""))
    score = pd.to_numeric(pd.Series([row.get(f"{axis}_confidence")]), errors="coerce").iloc[0]
    classified = pred not in {"UNKNOWN", "nan", "ERROR"}
    family_match = (
        (pred == rec.truth_class)
        or (str(rec.truth_class) == "MIRA" and pred == "LPV")
        or (str(rec.truth_class) == "PULSAR" and pred == "PULSAR_CANDIDATE")
        or (str(rec.truth_class) in {"RGB", "AGB"} and pred == "RED_GIANT")
    )
    return {
        "truth_id": rec.truth_id,
        "axis": axis,
        "truth_class": rec.truth_class,
        "predicted_class": pred,
        "status": status,
        "raw_score": score,
        "match": pred == rec.truth_class,
        "family_match": family_match,
        "classified": classified,
        "sep_arcsec": sep,
        "collectors": json.dumps(logs),
    }


def _deterministic():
    """``truth/deterministic.py`` (loaded by path like the collectors; one module object per process)."""
    m = sys.modules.get("truth_deterministic")
    return m if m is not None else load_module(CLS / "truth" / "deterministic.py", "truth_deterministic")


def sample_truth(truth_dir, per_class):
    """At most ``per_class`` rows of every (axis, class): the ones with the smallest seeded hash of their id, whatever order the file is in.

    Before 2.61.9 this was ``DataFrame.sample(random_state=42)``, which picks other objects as soon as the input rows are other rows or in another order.
    """
    D = _deterministic()
    parts = []
    for p in sorted(truth_dir.glob("*_truth.csv")):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if not {"truth_id", "ra", "dec", "truth_axis", "truth_class"}.issubset(df.columns):
            continue
        parts.append(D.bottom_k(df.dropna(subset=["ra", "dec", "truth_class"]), per_class))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def archive_errors(collectors) -> list[str]:
    """Collectors of one validation row that raised (an archive that was down or refused): their ``status`` starts with ``error``.

    Such a row is not a result about the classifier: with the other collectors empty it falls to NO_EVIDENCE / UNKNOWN.
    """
    try:
        logs = json.loads(collectors) if isinstance(collectors, str) else (collectors or [])
    except Exception:
        return ["unreadable collector log"]
    return [str(e.get("collector")) for e in logs if str(e.get("status", "")).startswith("error")]


COVERAGE_TOLERANCE = 0.05


def coverage_by_class(rows) -> dict:
    """Share of the rows of every (axis, class) that got a class other than UNKNOWN."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    return {f"{a}|{c}": round(float(g["classified"].astype(bool).mean()), 4) for (a, c), g in df.groupby(["axis", "truth_class"])} if len(df) else {}


def coverage_drops(rows, baseline) -> list:
    """Classes whose classified share fell below the baseline by more than its tolerance.

    An archive that answers with zero rows instead of an error looks like a classifier that abstains: of the bot runs with a PN exact-match rate below
    its usual 0.892, most had no collector error at all (validation/reproducibility/sample_history.csv), so errors alone do not find an outage.  The baseline
    (``truth/fixed/baseline_coverage.json``) is the share measured once on the frozen list; only a drop counts, a gain is not a problem.  A drop is an archive
    outage or a change of the classifier: after a change the baseline is refreshed by hand with a version number.
    """
    if not baseline:
        return []
    tol = float(baseline.get("tolerance", COVERAGE_TOLERANCE))
    now = coverage_by_class(rows)
    return [
        {"class": k, "baseline": v, "observed": now.get(k), "tolerance": tol}
        for k, v in sorted(baseline.get("classes", {}).items())
        if k in now and now[k] < v - tol
    ]


def run_status(rows, baseline=None) -> dict:
    """OK, or DEGRADED when any row met an archive error (after the retries), crashed, or a class lost coverage against the baseline.

    The numbers of a degraded run are not comparable with other runs.
    """
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    errs = [archive_errors(c) for c in df["collectors"]] if "collectors" in df else []
    bad = [i for i, e in enumerate(errs) if e]
    crashed = int((df["predicted_class"].astype(str) == "ERROR").sum()) if "predicted_class" in df else 0
    by = collections.Counter(c for e in errs for c in e)
    classes = sorted({f"{df.iloc[i]['axis']}|{df.iloc[i]['truth_class']}" for i in bad}) if bad else []
    drops = coverage_drops(df, baseline)
    return {
        "status": "DEGRADED" if bad or crashed or drops else "OK",
        "rows": int(len(df)),
        "archive_error_rows": len(bad),
        "evaluation_error_rows": crashed,
        "errors_by_collector": dict(sorted(by.items())),
        "affected_classes": classes,
        "coverage_baseline": bool(baseline),
        "coverage_drops": drops,
    }


def retry_errors(rows, truth, radius, max_workers, attempts, evaluate=None):
    """Evaluate again, up to ``attempts`` times, the rows that met an archive error or crashed (a transient outage must not decide a number).

    ``rows`` is the list of result records; the truth rows are looked up by (axis, class, id).  Returns (rows, how many evaluations were repeated).
    """
    evaluate = evaluate or evaluate_one
    key = lambda r: (str(r.get("axis", r.get("truth_axis"))), str(r["truth_class"]), str(r["truth_id"]))  # noqa: E731
    lookup = {(str(t.truth_axis), str(t.truth_class), str(t.truth_id)): t for _, t in truth.iterrows()}
    repeated = 0
    for _ in range(max(0, attempts)):
        bad = [i for i, r in enumerate(rows) if (archive_errors(r.get("collectors")) or str(r.get("predicted_class")) == "ERROR") and key(r) in lookup]
        if not bad:
            break
        with tempfile.TemporaryDirectory() as tmp:
            with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(bad)))) as pool:
                futs = {pool.submit(evaluate, lookup[key(rows[i])], Path(tmp), radius): i for i in bad}
                for f in as_completed(futs):
                    try:
                        rows[futs[f]] = f.result()
                    except Exception:
                        pass  # keep the earlier record; it stays flagged
        repeated += len(bad)
    return rows, repeated


def write_report(rows, out, status=None):
    out.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out / "independent_truth_predictions.csv", index=False)
    summary = []
    if not rows.empty:
        for (axis, label), g in rows.groupby(["axis", "truth_class"]):
            classified = g.classified.astype(bool)
            matches = g.match.astype(bool)
            family = g["family_match"].fillna(False).astype(bool) if "family_match" in g else matches
            summary.append(
                {
                    "axis": axis,
                    "truth_class": label,
                    "n": len(g),
                    "classified": int(classified.sum()),
                    "coverage": float(classified.mean()),
                    "exact_accuracy_all": float(matches.mean()),
                    "accuracy_when_classified": float(matches[classified].mean()) if classified.any() else math.nan,
                    "family_accuracy_all": float(family.mean()),
                    "family_accuracy_when_classified": (
                        float(family[classified].mean()) if classified.any() else math.nan
                    ),
                }
            )
    s = pd.DataFrame(summary)
    s.to_csv(out / "independent_truth_summary.csv", index=False)
    lines = [
        "# Independent truth-set cross-validation",
        "",
    ]
    if status and status.get("status") != "OK":
        lines += [
            f"> **DEGRADED RUN** ({status['archive_error_rows']} rows met an archive error, {status['evaluation_error_rows']} crashed; collectors {status['errors_by_collector']}; classes {status['affected_classes']}; "
            f"coverage below the baseline: {[(d['class'], d['baseline'], d['observed']) for d in status.get('coverage_drops', [])]}).",
            "> The numbers below are not comparable with other runs and must not be read as a change of the classifier.",
            "",
        ]
    if status and status.get("truth_list_frozen") is False:
        lines += [
            "> **UNFROZEN truth list**: `v2/Classifier/truth/fixed` is not committed, so this run built the list itself (deterministically, SHA-256 "
            f"{status.get('truth_list_sha256', '?')[:12]}); freeze it to make the numbers comparable across runs.",
            "",
        ]
    lines += [
        "Truth-catalog rows are used only as coordinates/labels. The same catalog is excluded from production evidence for that validation family.",
        "",
        "| axis | class | n | classified | coverage | exact all | exact classified | family all | family classified |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in s.iterrows():
        exact = f"{r.accuracy_when_classified:.1%}" if pd.notna(r.accuracy_when_classified) else "n/a"
        fam = f"{r.family_accuracy_when_classified:.1%}" if pd.notna(r.family_accuracy_when_classified) else "n/a"
        lines.append(
            f"| {r.axis} | {r.truth_class} | {int(r.n)} | {int(r.classified)} | {r.coverage:.1%} | {r.exact_accuracy_all:.1%} | {exact} | {r.family_accuracy_all:.1%} | {fam} |"
        )
    lines += [
        "",
        "Exact accuracy requires the requested leaf label. Family accuracy additionally credits a Mira truth object classified as the broader Gaia LPV family, and a pulsar classified as a radio pulsar candidate, and an RGB or AGB star classified as a red giant; it is reported separately and never substituted for the exact value. UNKNOWN is abstention. Low coverage is therefore reported separately from errors. Pulsar truth explicitly excludes ATNF evidence, and SN truth excludes Asiago evidence; those rows test whether another evidence family can independently recover the identity.",
    ]
    (out / "INDEPENDENT_TRUTH_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--truth-dir", type=Path, default=CLS / "truth" / "generated")
    p.add_argument("--out-dir", type=Path, default=CLS / "validation" / "independent_truth")
    p.add_argument("--per-class", type=int, default=8)
    p.add_argument("--axis")
    p.add_argument("--truth-class")
    p.add_argument("--radius-arcmin", type=float, default=0.5)
    p.add_argument("--max-workers", type=int, default=6)
    p.add_argument("--retry-errors", type=int, default=1, help="evaluate rows that met an archive error again this many times (2.61.9)")
    a = p.parse_args()
    truth = sample_truth(a.truth_dir, a.per_class)
    if a.axis:
        truth = truth[truth.truth_axis.astype(str) == a.axis]
    if a.truth_class:
        truth = truth[truth.truth_class.astype(str) == a.truth_class]
    if truth.empty:
        raise RuntimeError("no independent truth rows available")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = a.out_dir / "independent_truth_checkpoint.csv"
    rows = []
    if checkpoint.exists():
        try:
            prior = pd.read_csv(checkpoint)
            rows = prior.to_dict("records")
        except Exception:
            rows = []
    done = {(str(x.get("axis")), str(x.get("truth_class")), str(x.get("truth_id"))) for x in rows}
    pending = [r for _, r in truth.iterrows() if (str(r.truth_axis), str(r.truth_class), str(r.truth_id)) not in done]
    print(f"resume: {len(rows)} completed, {len(pending)} pending of {len(truth)}", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        with ThreadPoolExecutor(max_workers=max(1, min(a.max_workers, len(pending) or 1))) as pool:
            fs = {pool.submit(evaluate_one, r, base, a.radius_arcmin): r for r in pending}
            for f in as_completed(fs):
                try:
                    rows.append(f.result())
                except Exception as exc:
                    r = fs[f]
                    rows.append(
                        {
                            "truth_id": r.truth_id,
                            "axis": r.truth_axis,
                            "truth_class": r.truth_class,
                            "predicted_class": "ERROR",
                            "status": repr(exc),
                            "raw_score": math.nan,
                            "match": False,
                            "family_match": False,
                            "classified": False,
                            "sep_arcsec": math.nan,
                            "collectors": "[]",
                        }
                    )
                pd.DataFrame(rows).to_csv(checkpoint, index=False)
                if len(rows) % 10 == 0:
                    print(f"checkpoint: {len(rows)}/{len(truth)}", flush=True)
    rows, repeated = retry_errors(rows, truth, a.radius_arcmin, a.max_workers, a.retry_errors)
    result = pd.DataFrame(rows)
    status = {**run_status(result), "retried_evaluations": repeated}
    (a.out_dir / "validation_status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result, a.out_dir, status)
    checkpoint.unlink(missing_ok=True)
    print(f"status: {status['status']} ({status['archive_error_rows']} rows with an archive error after {repeated} repeated evaluations)", flush=True)
    print(result.groupby(["axis", "truth_class"])[["classified", "match"]].mean())


if __name__ == "__main__":
    main()
    # Interpreter teardown after the archive queries segfaulted in CI after the
    # report was written (also with no Python thread alive): skip it.
    import os

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
