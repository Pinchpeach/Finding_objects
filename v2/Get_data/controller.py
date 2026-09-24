"""Run every v2 catalog collector independently for one sky position."""
from __future__ import annotations

import argparse
import importlib.util
import math
import time
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GET_DATA = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "rawdata"
DEFAULT_CHUNK_RADIUS = 1.0
BASE_COLUMNS = ["catalog", "catalog_object_id", "object_name", "ra", "dec"]


def plan_chunks(ra, dec, radius_arcmin, chunk_radius_arcmin):
    """Cover a cone with overlapping small cones in a rotated sky frame.

    Longitude/latitude distances bound spherical distances from above, so each
    square is covered by its circumscribed cone, including at RA wrap/poles.
    """
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    if not all(math.isfinite(v) for v in (ra, dec, radius_arcmin, chunk_radius_arcmin)):
        raise ValueError("coordinates and radii must be finite")
    if not -90 <= dec <= 90 or not 0 < radius_arcmin < 5400 or chunk_radius_arcmin <= 0:
        raise ValueError("require Dec in [-90,90], radius in (0,5400), and positive chunk radius")
    if radius_arcmin <= chunk_radius_arcmin:
        return [(ra % 360, dec, radius_arcmin)]
    n = math.ceil(math.sqrt(2) * radius_arcmin / chunk_radius_arcmin)
    if n * n > 10000:
        raise ValueError("too many chunks; increase --chunk-radius")
    step = 2 * radius_arcmin / n
    tile_radius = step / math.sqrt(2)
    center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
    frame = center.skyoffset_frame()
    chunks = []
    for i in range(n):
        for j in range(n):
            p = SkyCoord(lon=(-radius_arcmin + (i + .5) * step) * u.arcmin,
                         lat=(-radius_arcmin + (j + .5) * step) * u.arcmin,
                         frame=frame).icrs
            if center.separation(p).arcmin <= radius_arcmin + tile_radius:
                chunks.append((float(p.ra.deg), float(p.dec.deg), tile_radius))
    return chunks


def _clip_frame(df, ra, dec, radius_arcmin):
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    if df.empty:
        return df.reindex(columns=list(dict.fromkeys([*BASE_COLUMNS, *df.columns])))
    if not set(BASE_COLUMNS).issubset(df.columns):
        raise ValueError("collector output missing standard columns")
    coords = df[["ra", "dec"]].apply(pd.to_numeric, errors="coerce")
    if not (coords.notna().all().all() and
            coords["ra"].map(math.isfinite).all() and coords["dec"].between(-90, 90).all()):
        raise ValueError("collector output contains invalid coordinates")
    points = SkyCoord(ra=coords.ra.to_numpy() * u.deg, dec=coords.dec.to_numpy() * u.deg)
    center = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
    return df.loc[center.separation(points).arcmin <= radius_arcmin + 1e-8].copy()


def _merge_frames(frames):
    df = pd.concat(frames, ignore_index=True, sort=False)
    # Missing identifiers must not collapse unrelated sources.
    identified = df.catalog_object_id.notna() & df.catalog_object_id.astype(str).str.strip().ne("")
    duplicates = df.loc[identified].duplicated(["catalog", "catalog_object_id"], keep="last")
    return df.drop(index=duplicates.index[duplicates]).drop_duplicates().reset_index(drop=True)

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
    *,
    chunk_radius_arcmin: float = DEFAULT_CHUNK_RADIUS,
) -> pd.DataFrame:
    chunks = plan_chunks(ra, dec, radius_arcmin, chunk_radius_arcmin)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = _tag(ra, dec, radius_arcmin)
    results = []

    for name in COLLECTORS:
        started = time.monotonic()
        output = out_dir / f"{name}_{tag}.csv"
        frames, chunk_errors = [], []
        attempted = 0
        try:
            module = _load_collector(name)
            for index, (chunk_ra, chunk_dec, chunk_radius) in enumerate(chunks, 1):
                attempted += 1
                try:
                    df = module.fetch(chunk_ra, chunk_dec, chunk_radius)
                    df = pd.DataFrame() if df is None else pd.DataFrame(df)
                    frames.append(_clip_frame(df, ra, dec, radius_arcmin))
                except Exception as exc:
                    chunk_errors.append(f"chunk {index}/{len(chunks)}: {exc!r}")
                    traceback.print_exc()
                print(f"[{name}] chunk {index}/{len(chunks)} completed", flush=True)
            if not frames:
                raise RuntimeError("all chunks failed: " + "; ".join(chunk_errors))
            df = _merge_frames(frames)
            # Publish only after save succeeds, avoiding stale/partial output.
            temporary = output.with_suffix(".tmp.csv")
            try:
                module.save(df, temporary)
                temporary.replace(output)
            finally:
                temporary.unlink(missing_ok=True)
            status = "partial" if chunk_errors else ("ok" if len(df) else "empty")
            error = "; ".join(chunk_errors)
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

        if not output_file:
            output.unlink(missing_ok=True)
        results.append({
            "collector": name,
            "status": status,
            "rows": rows,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "output_file": output_file,
            "error": error,
            "chunks_planned": len(chunks),
            "chunks_attempted": attempted,
            "chunks_succeeded": len(frames),
            "chunks_failed": len(chunk_errors),
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
    parser.add_argument("--chunk-radius", type=float, default=DEFAULT_CHUNK_RADIUS,
                        help="Maximum radius per collector call, in arcminutes (default: 1)")
    args = parser.parse_args()
    if args.radius <= 0:
        parser.error("--radius must be > 0")
    try:
        collect_all(args.ra, args.dec, args.radius, args.out_dir,
                    chunk_radius_arcmin=args.chunk_radius)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
