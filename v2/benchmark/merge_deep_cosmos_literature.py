#!/usr/bin/env python3
"""Put the NED / SIMBAD rows of ``collect_deep_cosmos_literature.py`` next to the stored blind rows of the deep COSMOS fields, offline (2.62.7, task "더").

    python merge_deep_cosmos_literature.py --blind-root DIR --literature-root DIR --out DIR [--fields a,b]

``--blind-root``       the unpacked bundles of ``v2_deep_cosmos.yml``: ``<field>/raw/<tag>/*.csv`` (and ``field.json``).
``--literature-root``  the output of ``collect_deep_cosmos_literature.py collect``: ``<field>/{simbad_<tag>.csv, ned_<tag>.csv, literature_state.json}``.
``--out``              a NEW directory with the same layout as the blind root, holding a COPY of every field's ``raw/<tag>`` plus the two literature files, ready for
                       ``association_truth/run_variant.py --fields-root OUT``, ``association_ambiguity/literature_only.py --raw OUT/<field>/raw/<tag>`` or ``pipeline.py --raw-dir``.

The blind data are never written: ``--out`` must not exist (or be empty) and must not lie inside the blind root; a blind bundle that already holds a SIMBAD or NED file is refused (it
would no longer be blind); a field whose collection did not finish (``literature_state.json`` ``ok`` is false) is refused; the SHA-256 of every blind file is taken before and after
and the run fails if one changed.  ``merge_manifest.json`` lists the SHA-256 of every file added and of every blind file copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_info as RI  # noqa: E402

LITERATURE_PREFIXES = ("simbad_", "ned_")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def blind_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def merge(blind_root: Path, literature_root: Path, out: Path, fields: list[str] | None = None) -> dict:
    blind_root, literature_root, out = blind_root.resolve(), literature_root.resolve(), out.resolve()
    if out == blind_root or blind_root in out.parents or out in blind_root.parents:
        raise SystemExit(f"--out {out} must be a directory of its own, outside the blind root {blind_root}")
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"--out {out} exists and is not empty: the merge never writes into an existing directory")
    names = fields or sorted(p.name for p in literature_root.iterdir() if (p / "literature_state.json").exists())
    if not names:
        raise SystemExit(f"no field with a literature_state.json under {literature_root}")
    before = blind_hashes(blind_root)
    manifest = {"blind_root": str(blind_root), "literature_root": str(literature_root), "fields": {}}
    for name in names:
        state = json.loads((literature_root / name / "literature_state.json").read_text())
        if not state.get("ok"):
            raise SystemExit(f"{name}: the literature collection did not finish (literature_state.json ok = false)")
        t = state["tag"]
        raw = blind_root / name / "raw" / t
        if not raw.is_dir():
            raise SystemExit(f"{name}: no blind raw folder {raw}")
        held = [p.name for p in raw.iterdir() if p.name.startswith(LITERATURE_PREFIXES)]
        if held:
            raise SystemExit(f"{name}: the blind folder already holds {held}: it is not a blind bundle")
        dst = out / name / "raw" / t
        shutil.copytree(raw, dst)
        if (blind_root / name / "field.json").exists():
            shutil.copy2(blind_root / name / "field.json", out / name / "field.json")
        added = []
        for prefix in LITERATURE_PREFIXES:
            src = literature_root / name / f"{prefix}{t}.csv"
            if not src.exists():
                raise SystemExit(f"{name}: {src.name} is missing in the literature root")
            shutil.copy2(src, dst / src.name)
            added.append(src.name)
        manifest["fields"][name] = dict(tag=t, added=sorted(added), added_sha256={a: sha(dst / a) for a in sorted(added)},
                                         blind_copied={p.name: sha(p) for p in sorted(raw.iterdir()) if p.is_file()}, state={k: v for k, v in state.items() if k != "ned_tap"})  # fmt: skip
    if blind_hashes(blind_root) != before:
        raise SystemExit("a blind file changed during the merge (this must not happen)")
    (out / "merge_manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blind-root", type=Path, required=True)
    ap.add_argument("--literature-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fields", default="")
    a = ap.parse_args()
    t0 = RI.start()
    man = merge(a.blind_root, a.literature_root, a.out, [f for f in a.fields.replace(",", " ").split() if f] or None)
    print(f"merged {len(man['fields'])} field(s) into {a.out}")
    RI.write(a.out, [a.blind_root, a.literature_root], t0=t0, note="blind rows + NED / SIMBAD rows; the blind data are not written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
