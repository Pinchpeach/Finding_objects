#!/usr/bin/env python3
"""``run_info.json``: what a result directory was made with (2.62.6).

Why: the decision table of 2.62.2 could not be shown to have run with ``V2_POSERR_UNITS=legacy`` from its result files; the switch was in the shell that
started the runs, nowhere in the outputs.  Every directory a measurement tool writes gets a ``run_info.json`` (a file result gets ``<stem>.run_info.json`` next to it)
with

* ``commit`` / ``branch`` / ``dirty``   the checkout the tool ran in (``dirty`` = files under ``v2/`` differ from the commit: the result is not reproducible from the hash alone)
* ``env``                             every ``V2_*`` environment variable plus ``PYTHONHASHSEED`` and ``XDG_CACHE_HOME``, as set
* ``effective``                       what the code READS in that environment (a fresh interpreter): ``association_model.POSERR_UNITS`` (default included), ``AMBIG_FIX``,
                                      ``POSERR_NATIVE``, ``ANNOT_ASSOC``, ``lowlat_qso.options()`` -- the environment alone does not say what a default was
* ``started_utc`` / ``finished_utc`` / ``status``   ``ok`` / ``failed`` / ``running``
* ``inputs``                          per input (file or directory): path, kind, SHA-256 (of the file; of the sorted ``relative path|size`` list for a directory, or of
                                      the content too with ``content=True``), number of files
* ``argv``, ``python``, ``note``

Use in a Python tool::

    import run_info as RI
    t0 = RI.start()
    ...                                              # the work
    RI.write(out_dir, inputs=[fields_csv, raw_root], t0=t0, note="what this is")

or as a context manager (``with RI.RunInfo(out_dir, inputs=[...]):``, which also records ``failed`` when the block raises); from a shell script::

    python3 v2/benchmark/run_info.py begin --out DIR --input FILE_OR_DIR ...
    ...
    python3 v2/benchmark/run_info.py end --out DIR [--status failed]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
ENV_EXTRA = ("PYTHONHASHSEED", "XDG_CACHE_HOME")
SCHEMA = 1


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=V2, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def git_info(exclude=()) -> dict:
    """``exclude``: the outputs of the run itself (its result directory or file and the record).  A tool that writes its results inside v2/ (a committed
    results folder) would otherwise always be ``dirty`` by its own output, and the flag would no longer say that the CODE differed from the commit (review of 2.62.6)."""
    spec = ["."]
    for e in exclude:
        try:
            rel = Path(e).resolve().relative_to(V2.resolve())
        except ValueError:
            continue  # outside v2/: not in the status anyway
        spec.append(f":(exclude){rel.as_posix()}")
    status = _git("status", "--porcelain", "--", *spec)
    return dict(commit=_git("rev-parse", "HEAD") or None, branch=_git("rev-parse", "--abbrev-ref", "HEAD") or None, dirty=bool(status), dirty_files=len([x for x in status.splitlines() if x]))


def env_info() -> dict:
    return {k: os.environ[k] for k in sorted(os.environ) if k.startswith("V2_") or k in ENV_EXTRA}


_PROBE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
out = {}
try:
    import association_model as am
    out["POSERR_UNITS"] = am.POSERR_UNITS
    out["AMBIG_FIX"] = sorted(am.AMBIG_FIX)
    out["POSERR_NATIVE"] = sorted(getattr(am, "POSERR_NATIVE", ()))
    out["ANNOT_ASSOC"] = sorted(getattr(am, "ANNOT_ASSOC", ()))
except Exception as exc:
    out["association_model"] = "not readable: " + type(exc).__name__
try:
    import lowlat_qso as ll
    out["LOWLAT_QSO"] = sorted(ll.options())
    out["LOWLAT_QSO_ABSB"] = ll.max_abs_b()
except Exception as exc:
    out["lowlat_qso"] = "not readable: " + type(exc).__name__
print(json.dumps(out))
"""


def effective_switches(env: dict | None = None) -> dict:
    """What the code READS in environment ``env`` (default: this process's), defaults included.  Read by a fresh interpreter, so it is the value a pipeline started
    with that environment gets, whatever this process imported before.  A tool that starts pipelines with its own environment passes that environment."""
    try:
        r = subprocess.run([sys.executable, "-c", _PROBE, str(V2 / "Preprocess")], env=dict(os.environ if env is None else env), capture_output=True, text=True, timeout=120)
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {"probe": f"failed: {r.stderr.strip()[-200:]}"}
    except Exception as exc:  # a missing dependency must not stop the measurement from being recorded
        return {"probe": f"failed: {type(exc).__name__}"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _walk_files(root: Path) -> list[Path]:
    """Every file under ``root``, FOLLOWING symbolic links to directories.  ``Path.rglob`` does not descend into a symlinked directory (Python < 3.13 and the
    default after), so a results folder made of links to the runs it reuses (``d_new26`` of 2.62.6) hashed as an empty listing (n_files 0, the SHA-256 of
    nothing; review of 2.62.6).  A directory already visited (same real path) is not entered again, so a link loop ends."""
    seen, out = set(), []
    for d, dirs, files in os.walk(root, followlinks=True):
        real = os.path.realpath(d)
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        dirs.sort()
        out.extend(Path(d) / f for f in files if (Path(d) / f).is_file())
    return out


def describe_input(item, content: bool = False) -> dict:
    p = Path(item)
    if p.is_file():
        return dict(path=str(p), kind="file", sha256=sha256_file(p), size=p.stat().st_size)
    if p.is_dir():
        files = sorted(_walk_files(p))
        h = hashlib.sha256()
        for x in files:
            h.update(f"{x.relative_to(p).as_posix()}|{x.stat().st_size}".encode())
            if content:
                h.update(sha256_file(x).encode())
        return dict(path=str(p), kind="directory", sha256=h.hexdigest(), n_files=len(files), hashed="relative path, size" + (" and content" if content else ""))
    return dict(path=str(p), kind="missing", sha256=None)


def target(out) -> Path:
    """``DIR/run_info.json`` for a directory, ``STEM.run_info.json`` next to a file result."""
    p = Path(out)
    if p.suffix and not p.is_dir():
        return p.with_name(p.name.split(".")[0] + ".run_info.json")
    return p / "run_info.json"


def reuse_info(out, computed, reused) -> dict:
    """For a tool that resumes: what this run computed and what it took over from an earlier run in the same directory (Codex review of 2.62.6).  Call it BEFORE
    the first ``write`` of the run.  The earlier record, if there is one, is kept under ``previous`` by ``write`` when its setting differs; without one, the
    provenance of the reused parts is unknown and the record says so (the commit and settings of this record then apply to ``computed`` only)."""
    reused = sorted(str(x) for x in reused)
    had = target(out).exists()
    prov = "none reused" if not reused else ("the earlier record of this directory" if had else "unknown: no earlier record")
    return dict(computed=len(list(computed)), reused=len(reused), reused_items=reused[:500], reused_provenance=prov)


def start() -> str:
    return now()


def write(out, inputs=(), t0: str | None = None, status: str = "ok", note: str = "", extra: dict | None = None, effective: dict | None = None, content: bool = False,
          env: dict | None = None, replace_env: bool = False) -> Path:  # fmt: skip
    """``env``: the V2_* variables a tool gives to the pipelines it starts; they are what the result was made with.  ``replace_env``: ``env`` is the whole environment of
    those pipelines (a tool that drops the V2_* variables of its own shell before it starts them), otherwise it is added to this process's."""
    path = target(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    full_env = {k: str(v) for k, v in (env or {}).items()} if replace_env else {**os.environ, **{k: str(v) for k, v in (env or {}).items()}}
    info = dict(schema=SCHEMA, **git_info(exclude=[Path(out), path]), env={k: full_env[k] for k in sorted(full_env) if k.startswith("V2_") or k in ENV_EXTRA},
                effective=effective if effective is not None else effective_switches(full_env), started_utc=t0 or now(),
                finished_utc=None if status == "running" else now(), status=status, inputs=[describe_input(i, content) for i in inputs],
                argv=sys.argv, python=platform.python_version(), note=note)  # fmt: skip
    if extra:
        info["extra"] = extra
    if path.exists():  # a directory that was written before: keep the earlier record when the setting differs (the files in it are then of more than one run)
        try:
            old = json.loads(path.read_text())
        except Exception:
            old = {}
        prev = list(old.get("previous", []))
        if old and (old.get("env"), old.get("effective"), old.get("commit")) != (info["env"], info["effective"], info["commit"]) and old.get("status") != "running":
            prev.append({k: old.get(k) for k in ("commit", "dirty", "env", "effective", "started_utc", "finished_utc", "status", "note")})
        elif old and old.get("status") == "running" and old.get("started_utc") == info["started_utc"]:
            pass  # the end of the run that began it
        if prev:
            info["previous"], info["mixed"] = prev, True
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(info, indent=2, sort_keys=False, default=str) + "\n")
    tmp.replace(path)
    return path


def inputs_from_args(a, names="auto", out_name: str = "out") -> list:
    """The input paths of a parsed ``argparse`` namespace: for each name that is set, a path, or every path of a list (``name=DIR`` items give DIR).  ``names="auto"``:
    every argument except the output whose value is an existing file or directory."""
    if names == "auto":
        names = []
        for n, v in vars(a).items():
            if n == out_name:
                continue
            items = v if isinstance(v, (list, tuple)) else [v]
            for x in items:
                x = str(x).split("=", 1)[1] if isinstance(x, str) and "=" in x and not Path(x).exists() else x
                if isinstance(x, (str, Path)) and str(x) and Path(x).exists():
                    names.append(n)
                    break
    out = []
    for n in names:
        v = getattr(a, n, None)
        for x in v if isinstance(v, (list, tuple)) else [v]:
            if x is None or x == "":
                continue
            x = str(x)
            out.append(x.split("=", 1)[1] if "=" in x and not Path(x).exists() else x)
    return out


def write_args(a, input_names="auto", t0: str | None = None, note: str = "", status: str = "ok", env: dict | None = None, out_name: str = "out", **kw) -> Path:
    """``write`` for a tool that has an ``--out`` argument: the output is ``a.out``, the inputs are the arguments named in ``input_names``."""
    return write(getattr(a, out_name), inputs_from_args(a, input_names, out_name), t0=t0, note=note, status=status, env=env, **kw)


class RunInfo:
    """``with RunInfo(out, inputs=[...]):`` writes ``running`` at the start and ``ok`` / ``failed`` at the end."""

    def __init__(self, out, inputs=(), note: str = "", content: bool = False):
        self.out, self.inputs, self.note, self.content = out, tuple(inputs), note, content

    def __enter__(self):
        self.t0 = start()
        write(self.out, self.inputs, t0=self.t0, status="running", note=self.note, content=self.content)
        return self

    def __exit__(self, exc_type, exc, tb):
        write(self.out, self.inputs, t0=self.t0, status="failed" if exc_type else "ok", note=self.note, content=self.content)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["begin", "end", "show"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--input", nargs="*", default=[])
    ap.add_argument("--status", default="ok")
    ap.add_argument("--note", default="")
    ap.add_argument("--content", action="store_true", help="hash the content of every file of a directory input (slow)")
    a = ap.parse_args()
    path = target(a.out)
    if a.action == "begin":
        write(a.out, a.input, status="running", note=a.note, content=a.content)
    elif a.action == "end":
        if not path.exists():  # no begin: record what we can
            write(a.out, a.input, status=a.status, note=a.note, content=a.content)
        else:  # keep what the start recorded (environment, effective values, inputs); only the end changes
            info = json.loads(path.read_text())
            info.update(finished_utc=now(), status=a.status)
            if a.note:
                info["note"] = a.note
            path.write_text(json.dumps(info, indent=2, default=str) + "\n")
    else:
        print(path.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
