"""Run every v2 catalog collector independently for one sky position."""
from __future__ import annotations

import argparse
import importlib.util
import time
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GET_DATA = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "rawdata"

COLLECTORS = [
    "gaia_dr3", "sdss_dr18", "panstarrs1", "desi_legacy", "galex",
    "twomass", "allwise", "lotss", "first", "nvss", "vlass", "xmm",
    "chandra", "erosita", "sdss_spectroscopy", "desi_spectroscopy",
    "lamost_spectroscopy", "simbad", "ned",
]


def _load_collector(name: str):
    path = GET_DATA / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"v2_collector_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load collector: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "fetch", None)):
        raise AttributeError(f"{name} has no callable fetch()")
    if not callable(getattr(module, "save", None)):
        raise AttributeError(f"{name} has no callable save()")
    return module


def _tag(ra: float, dec: float, radius_arcmin: float) -> str:
    def clean(value: float) -> str:
        return f"{value:.6f}".rstrip("0").rstrip(".").replace("-", "m").replace(".", "p")
    return f"ra{clean(ra)}_dec{clean(dec)}_r{clean(radius_arcmin)}arcmin"


def collect_all(
    ra: float,
    dec: float,
    radius_arcmin: float,
    out_dir: Path = DEFAULT_OUT,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = _tag(ra, dec, radius_arcmin)
    results = []

    for name in COLLECTORS:
        started = time.monotonic()
        output = out_dir / f"{name}_{tag}.csv"
        try:
            module = _load_collector(name)
            df = module.fetch(ra, dec, radius_arcmin)
            if df is None:
                df = pd.DataFrame()
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)

            module.save(df, output)
            status = "ok" if len(df) else "empty"
            error = ""
            rows = len(df)
            output_file = str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output)
        except TimeoutError as exc:
            status, rows, output_file, error = "timeout", 0, "", repr(exc)
            traceback.print_exc()
        except Exception as exc:
            # Network libraries often wrap timeouts in package-specific exceptions.
            message = repr(exc)
            status = "timeout" if "timeout" in message.lower() or "timed out" in message.lower() else "error"
            rows, output_file, error = 0, "", message
            traceback.print_exc()

        results.append({
            "collector": name,
            "status": status,
            "rows": rows,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "output_file": output_file,
            "error": error,
        })
        print(f"[{name}] {status}: {rows} rows ({results[-1]['elapsed_seconds']} s)", flush=True)

    summary = pd.DataFrame(results)
    summary_path = out_dir / f"collection_summary_{tag}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Completed: {len(summary)}/{len(COLLECTORS)} collectors attempted", flush=True)
    print(f"Summary: {summary_path}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ra", type=float, required=True, help="ICRS RA in degrees")
    parser.add_argument("--dec", type=float, required=True, help="ICRS Dec in degrees")
    parser.add_argument("--radius", type=float, required=True, help="Cone radius in arcminutes")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.radius <= 0:
        parser.error("--radius must be > 0")
    collect_all(args.ra, args.dec, args.radius, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
