#!/usr/bin/env python3
"""SHA-256 manifest of the committed truth tables (2.62.7).

    python truth_manifest.py build  [--manifest FILE]            write the manifest from the files as they are now (a deliberate act: it changes what "committed" means)
    python truth_manifest.py verify [--manifest FILE] [--only NAME ...]   compare the files with the manifest; exit 1 on any difference
    python truth_manifest.py show

Why.  The truth tables of the benchmarks are drawn from services with ``TOP`` / ``row_limit`` and no ``ORDER BY`` (the survey of 2026-11-28, WORK_REPORT_2026-11-28a.md
section 2): a rebuild can give other objects.  Every consumer reads the committed file, so nothing is wrong as long as the committed file stays what it is, but two workflow
paths could replace it without anyone deciding to (an automatic run of ``build-reference-objects.yml`` on a branch push, a ``v2_desi_external_validation.yml`` dispatch whose first
job rebuilt the list and whose last job committed it over ``truth.csv``).  Task 2.61.9 did the same for the independent truth list of the cross validation (``Classifier/truth/fixed``
with ``truth_manifest.json``).  The manifest here records, for each table of the survey, the SHA-256 of every file, the number of rows and a hash of the id set, so that

* a workflow can check the committed file before it uses it (``verify``), and says so in its log,
* a regeneration writes next to the committed file, never over it, and a person who decides to replace the table runs ``build`` in the same commit
  (the test ``test_truth_manifest.py`` fails for a changed file with an unchanged manifest, and for a manifest that does not match the files),
* the benchmark ids (``TRD000001`` ...  are row numbers) are guarded: a renumbering changes ``ids_sha256`` even if a file with the same rows is written.

``paired`` directories (``catalog_features`` of a benchmark) are hashed file by file: the features are keyed by ``benchmark_id``, so a truth table and its features are one unit.

No timestamp or commit hash is stored: the same files give the same manifest, byte for byte.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("truth_tables_manifest.json")
SCHEMA = 1

# name -> (files, id column, builder, workflow, paired directories, group, number in the survey of 2026-11-28 (WORK_REPORT_2026-11-28a.md 2.2))
# group: "order_dependent" = the construction depends on the order in which a service answers; "deterministic" = ORDER BY a unique key (listed because headline numbers rest on it)
TABLES: dict[str, dict] = {
    "desi_external_truth": dict(files=["benchmark/desi_external/truth.csv"], id="benchmark_id", builder="benchmark/build_desi_truth.py", workflow="v2_desi_external_validation.yml",
                                paired=["benchmark/desi_external/catalog_features"], group="order_dependent", survey=1),
    "desi_fusion_truth": dict(files=["benchmark/desi_fusion/truth.csv"], id="benchmark_id", builder="benchmark/build_desi_truth.py", workflow="collect-truth-radio-xray.yml",
                              paired=["benchmark/desi_fusion/catalog_features"], group="order_dependent", survey=1),
    "reference_objects": dict(files=["reference_objects/reference_objects.csv.gz"], id=None, builder="benchmark/build_reference_objects.py", workflow="build-reference-objects.yml",
                              paired=[], group="order_dependent", survey=2),
    "sdss_sky_truth": dict(files=["benchmark/sdss_sky/truth.csv"], id="benchmark_id", builder="benchmark/build_sdss_sky_truth.py", workflow="build-sdss-sky-benchmark.yml",
                           paired=["benchmark/sdss_sky/catalog_features"], group="order_dependent", survey=3),
    "lamost_star_external_truth": dict(files=["Classifier/lamost_star_external_truth.csv"], id="benchmark_id", builder="Classifier/build_lamost_star_external_truth.py",
                                       workflow="build-lamost-star-external-truth.yml", paired=[], group="order_dependent", survey=4),
    "star_diverse_truth": dict(files=["Classifier/star_diverse_validation/truth.csv"], id="benchmark_id", builder="Classifier/build_star_diverse_truth.py", workflow="validate-star-diverse.yml",
                               paired=[], group="order_dependent", survey=5),
    "mira_rr_ew_truth": dict(files=["benchmark/mira_truth/asassn_gaia_lpv.csv.gz", "benchmark/rr_ew_truth/asassn_ztf.csv.gz"], id=None, builder="benchmark/build_mira_truth.py",
                             workflow="build-mira-truth.yml", paired=[], group="order_dependent", survey=6),
    "bright_truth": dict(files=["benchmark/bright_truth/apogee.csv.gz", "benchmark/bright_truth/els.csv.gz", "benchmark/bright_truth/lpv_lamost.csv.gz"], id=None,
                         builder="benchmark/build_bright_truth.py", workflow="build-bright-truth.yml", paired=[], group="order_dependent", survey=7),
    "desi_lines_truth": dict(files=["benchmark/desi_lines_truth/overlap.csv.gz"], id=None, builder="benchmark/build_desi_lines_truth.py", workflow="build-desi-lines-truth.yml",
                             paired=[], group="order_dependent", survey=8),
    "desi_gbm_truth": dict(files=["benchmark/desi_gbm_truth/train.csv.gz"], id=None, builder="benchmark/build_desi_gbm_truth.py", workflow="build-desi-gbm-truth.yml",
                           paired=[], group="order_dependent", survey=9),
    "xray_rules_sample": dict(files=["benchmark/xray_rules/sample.csv.gz"], id=None, builder="benchmark/xray_rules/build_sample.py", workflow=None, paired=[],
                              group="order_dependent", survey=10),
    "radio_xray_truth": dict(files=["benchmark/radio_xray_truth/ground_truth.csv"], id="benchmark_id", builder="benchmark/build_radio_xray_truth.py",
                             workflow="build-radio-xray-benchmark.yml", paired=[], group="order_dependent", survey=11),
    # the tables the headline SDSS numbers rest on: ORDER BY specObjID, so deterministic while DR18 is fixed (not rows of the survey table)
    "sdss_ground_truth": dict(files=["benchmark/truth_data/ground_truth.csv"], id="benchmark_id", builder="benchmark/build_truth_sets.py", workflow="build-truth-dataset.yml",
                              paired=["benchmark/catalog_features"], group="deterministic", survey=None),
    "star_truth": dict(files=["Classifier/star_truth.csv"], id="benchmark_id", builder="Classifier/build_star_truth.py", workflow="build-star-branch-truth.yml", paired=[],
                       group="deterministic", survey=None),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def describe_file(root: Path, rel: str, id_col: str | None) -> dict:
    p = root / rel
    out = dict(path=rel, sha256=sha256_file(p), bytes=p.stat().st_size)
    d = read_table(p)
    out["rows"] = int(len(d))
    if id_col:
        ids = sorted(d[id_col].astype(str))
        out["id_column"] = id_col
        out["ids_sha256"] = sha256_bytes("\n".join(ids).encode())
    return out


def describe_dir(root: Path, rel: str) -> dict:
    d = root / rel
    files = sorted(x for x in d.rglob("*") if x.is_file())
    entries = [dict(path=x.relative_to(root).as_posix(), sha256=sha256_file(x), bytes=x.stat().st_size) for x in files]
    digest = sha256_bytes("\n".join(f"{e['path']}|{e['sha256']}" for e in entries).encode())
    return dict(path=rel, n_files=len(entries), digest_sha256=digest, files=entries)


def build(root: Path = V2, tables: dict | None = None) -> dict:
    tables = TABLES if tables is None else tables
    out = {}
    for name, t in tables.items():
        out[name] = dict(group=t["group"], survey_row=t["survey"], builder=t["builder"], workflow=t["workflow"],
                         files=[describe_file(root, f, t["id"]) for f in t["files"]], paired=[describe_dir(root, d) for d in t["paired"]])
    return dict(schema=SCHEMA, note="SHA-256 of the committed truth tables (truth_manifest.py); regenerate only together with a deliberate replacement of a table",
                tables=out)


def dumps(m: dict) -> str:
    return json.dumps(m, indent=1, sort_keys=True) + "\n"


def verify(manifest: dict, root: Path = V2, only: list[str] | None = None, paired: str = "names") -> list[str]:
    """The differences between the files under ``root`` and ``manifest`` (empty: they match).  Reads rows and ids only of a file whose hash differs.

    ``paired``: how the feature directories are compared.  ``"names"`` (default) = the set of files; ``"strict"`` = the SHA-256 of every file.  The features of a benchmark are
    changed on purpose by other workflows (``augment-ls-columns``, ``recollect-ps1-features``: new or replaced columns of the same rows), so the test of the repository and
    the workflows use ``names``; ``strict`` is for an audit (what was in the directory when the manifest was written)."""
    problems = []
    for name, t in manifest["tables"].items():
        if only and name not in only:
            continue
        for f in t["files"]:
            p = root / f["path"]
            if not p.exists():
                problems.append(f"{name}: {f['path']} is missing")
                continue
            if sha256_file(p) != f["sha256"]:
                msg = f"{name}: {f['path']} differs from the manifest (SHA-256)"
                try:
                    d = read_table(p)
                    msg += f"; rows {len(d)} (manifest {f['rows']})"
                    if f.get("id_column") in d:
                        same = sha256_bytes("\n".join(sorted(d[f["id_column"]].astype(str))).encode()) == f.get("ids_sha256")
                        msg += "; the id set is " + ("the same (other columns changed)" if same else "different (rows added, removed or renumbered)")
                except Exception as exc:  # a damaged file is reported as damaged
                    msg += f"; unreadable ({type(exc).__name__})"
                problems.append(msg)
        for dd in t["paired"]:
            d = root / dd["path"]
            now = describe_dir(root, dd["path"]) if d.is_dir() else None
            if now is None:
                problems.append(f"{name}: {dd['path']} is missing")
            elif paired == "names" and sorted(e["path"] for e in now["files"]) != sorted(e["path"] for e in dd["files"]):
                have, want = {e["path"] for e in now["files"]}, {e["path"] for e in dd["files"]}
                diff = sorted(have ^ want)
                problems.append(f"{name}: {dd['path']} has other files than the manifest: {', '.join(diff[:6])}{' ...' if len(diff) > 6 else ''}")
            elif paired == "strict" and now["digest_sha256"] != dd["digest_sha256"]:
                have = {e["path"]: e["sha256"] for e in now["files"]}
                want = {e["path"]: e["sha256"] for e in dd["files"]}
                diff = sorted({*(k for k in want if have.get(k) != want[k]), *(k for k in have if k not in want)})
                problems.append(f"{name}: {dd['path']} differs from the manifest in {len(diff)} file(s): {', '.join(diff[:6])}{' ...' if len(diff) > 6 else ''}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["build", "verify", "show"])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--only", nargs="*", default=None, help="verify only these tables")
    ap.add_argument("--paired", choices=["names", "strict"], default="names", help="feature directories: same files (default) or same SHA-256 of every file")
    a = ap.parse_args()
    if a.action == "build":
        a.manifest.write_text(dumps(build()))
        print(f"wrote {a.manifest}: {len(TABLES)} tables")
        return 0
    m = json.loads(a.manifest.read_text())
    if a.action == "show":
        for n, t in m["tables"].items():
            print(f"{n:28s} {t['group']:16s} " + " ".join(f"{f['path']}({f['rows']} rows, {f['sha256'][:10]})" for f in t["files"]))
        return 0
    if a.only:
        unknown = [n for n in a.only if n not in m["tables"]]
        if unknown:
            print("unknown tables:", ", ".join(unknown), file=sys.stderr)
            return 2
    problems = verify(m, only=a.only, paired=a.paired)
    for p in problems:
        print("MISMATCH", p)
    print(f"{'OK' if not problems else 'FAILED'}: {len(a.only or m['tables'])} table(s) checked against {a.manifest.name}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
