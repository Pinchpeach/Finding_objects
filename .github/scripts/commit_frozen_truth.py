#!/usr/bin/env python3
"""Check one or two frozen truth lists and copy the first into v2/Classifier/truth/fixed/ (2.62.8, workflow v2_commit_frozen_truth.yml).

    python commit_frozen_truth.py LIST_A [LIST_B] --into v2/Classifier/truth/fixed

* every list is checked with ``build_independent_truth_sets.verify`` (file SHA-256, the id set of every class, every set status ok) and its ``list_sha256`` is computed;
* with a second list the two ``list_sha256`` must be equal: the builder is deterministic, and two freeze runs made at different times must agree;
* only the manifest and the files it lists are copied (an artifact may carry other files of the work directory); the target directory is replaced as a whole;
* a table of the files, their SHA-256 and the list_sha256 goes to stdout and, in a workflow, to the step summary.
Exit status 1 on any problem, with nothing copied.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "v2" / "Classifier" / "truth" / "build_independent_truth_sets.py"


def builder():
    spec = importlib.util.spec_from_file_location("truth_builder", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(BUILDER.parent))
    spec.loader.exec_module(mod)
    return mod


def find_list(path: Path, manifest: str) -> Path:
    """The directory that holds the manifest (download-artifact may keep the artifact's own sub-path)."""
    if (path / manifest).exists():
        return path
    hits = sorted(path.rglob(manifest))
    if len(hits) != 1:
        raise SystemExit(f"{path}: expected one {manifest}, found {len(hits)}")
    return hits[0].parent


def check(tb, path: Path) -> tuple[Path, str, dict]:
    d = find_list(path, tb.MANIFEST)
    problems = tb.verify(d)
    if problems:
        raise SystemExit(f"{d}: the list does not match its manifest:\n  " + "\n  ".join(problems))
    return d, tb.list_sha256(d), json.loads((d / tb.MANIFEST).read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lists", nargs="+", type=Path, help="one or two downloaded lists")
    ap.add_argument("--into", type=Path, required=True)
    a = ap.parse_args()
    if len(a.lists) > 2:
        raise SystemExit("one or two lists")
    tb = builder()
    checked = [check(tb, p) for p in a.lists]
    (d, sha, manifest) = checked[0]
    lines = ["| set | file | rows | status | SHA-256 |", "|---|---|---|---|---|"]
    lines += [f"| {n} | {e['file']} | {e['rows']} | {e['status']} | `{e['sha256']}` |" for n, e in manifest["sets"].items()]
    lines.append(f"\nlist_sha256 `{sha}` (run {os.environ.get('RUN_ID', '?')})")
    if len(checked) == 2:
        other = checked[1][1]
        lines.append(f"list_sha256 `{other}` (run {os.environ.get('COMPARE_RUN_ID', '?')}): {'**the same**' if other == sha else '**DIFFERENT**'}")
        if other != sha:
            differ = [n for n in manifest["sets"] if checked[1][2]["sets"].get(n, {}).get("sha256") != manifest["sets"][n]["sha256"]]
            lines.append("sets that differ: " + ", ".join(differ))
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("### Frozen truth list\n\n" + text + "\n")
    if len(checked) == 2 and checked[1][1] != sha:
        print("the two freeze runs gave different lists: nothing is committed", file=sys.stderr)
        return 1
    if a.into.exists():
        shutil.rmtree(a.into)
    a.into.mkdir(parents=True)
    for e in manifest["sets"].values():
        shutil.copy2(d / e["file"], a.into / e["file"])
    shutil.copy2(d / tb.MANIFEST, a.into / tb.MANIFEST)
    problems = tb.verify(a.into)  # the copy is the list
    if problems:
        raise SystemExit("the copy does not verify:\n  " + "\n  ".join(problems))
    print(f"copied {len(manifest['sets'])} files and {tb.MANIFEST} into {a.into}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
