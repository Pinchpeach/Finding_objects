#!/usr/bin/env python3
"""Build larger per-axis truth samples with explicit evidence-exclusion metadata.

These truth sets are for evaluation/calibration only.  If a truth catalogue is
also available as production evidence, `excluded_evidence_catalog` records that
it must be masked during evaluation to prevent leakage.

2.61.9: the build is deterministic.  Every query asks for the whole table (no ``row_limit`` that cuts it at an arbitrary place), and a class keeps
the ``limit`` rows with the smallest SHA-256("<seed>|<truth_id>") (``deterministic.bottom_k``), so the list does not depend on the order in which an
archive answers.  A manifest (``truth_manifest.json``) records the SHA-256 of every file and of the id set of every class; ``--verify DIR`` checks a
directory against it.  The list the workflow validates is the committed one in ``v2/Classifier/truth/fixed`` (made by ``--freeze``).
"""

from __future__ import annotations
import argparse, datetime, importlib.util, json, sys, time
from pathlib import Path
import pandas as pd

_spec = importlib.util.spec_from_file_location("truth_deterministic", Path(__file__).resolve().parent / "deterministic.py")
D = importlib.util.module_from_spec(_spec)
sys.modules["truth_deterministic"] = D
_spec.loader.exec_module(D)
MANIFEST = "truth_manifest.json"
SCHEMA = 1


def _pick(df, names):
    low = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n in df.columns:
            return n
        if n.lower() in low:
            return low[n.lower()]
    return None


def _vizier(catalog, row_limit=-1, **constraints):
    from astroquery.vizier import Vizier

    last = None
    for attempt in range(3):
        try:
            v = Vizier(columns=["**", "_RAJ2000", "_DEJ2000"], row_limit=row_limit, timeout=180)
            tabs = v.query_constraints(catalog=catalog, **constraints) if constraints else v.get_catalogs(catalog)
            return tabs[0].to_pandas() if tabs else pd.DataFrame()
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise last


def _coords(df):
    ra = _pick(df, ["RAJ2000", "RA_ICRS", "_RA", "_RAJ2000"])
    de = _pick(df, ["DEJ2000", "DE_ICRS", "_DE", "_DEJ2000"])
    if ra is None or de is None:
        return pd.Series(pd.NA, index=df.index), pd.Series(pd.NA, index=df.index)
    r = pd.to_numeric(df[ra], errors="coerce")
    d = pd.to_numeric(df[de], errors="coerce")
    if r.notna().all() and d.notna().all():
        return r, d
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    for i in df.index[r.isna() | d.isna()]:
        try:
            rs = str(df.at[i, ra])
            ds = str(df.at[i, de])
            c = SkyCoord(rs, ds, unit=(u.hourangle, u.deg))
            r.at[i] = c.ra.deg
            d.at[i] = c.dec.deg
        except Exception:
            pass
    return r, d


def red_giants(limit):
    # Vrard+ 2025 table4: EV=1 certain RGB, EV=2 candidate AGB.
    df = _vizier("J/A+A/697/A165/table4")
    if df.empty:
        return df
    ev = _pick(df, ["EV"])
    idc = _pick(df, ["KIC"])
    ra, dec = _coords(df)
    out = pd.DataFrame(
        {
            "truth_id": df[idc].astype("string") if idc else df.index.astype(str),
            "ra": ra,
            "dec": dec,
            "truth_axis": "physical",
            "truth_class": df[ev].map({1: "RGB", 2: "AGB"}),
        }
    )
    out = out.dropna(subset=["truth_class", "ra", "dec"])
    out["truth_source"] = "Vrard+2025 Kepler RGB/AGB"
    out["excluded_evidence_catalog"] = ""
    return D.bottom_k(out, limit)


def variables(limit):
    specs = [
        ("RRAB", "RR_LYRAE"),
        ("RRC", "RR_LYRAE"),
        ("DCEP", "CEPHEID"),
        ("DCEPS", "CEPHEID"),
        ("M", "MIRA"),
        ("SR", "LPV"),
    ]
    parts = []
    for typ, label in specs:
        df = _vizier("II/366/catv2021", Type=typ)  # a failed query raises: a class must not go missing without notice (2.61.9)
        if df.empty:
            raise RuntimeError(f"II/366/catv2021 Type={typ}: empty answer")
        idc = _pick(df, ["ASASSN-V", "ID"])
        ra, dec = _coords(df)
        p = _pick(df, ["Prob"])
        part = pd.DataFrame(
            {
                "truth_id": df[idc].astype("string"),
                "ra": ra,
                "dec": dec,
                "truth_axis": "variability",
                "truth_class": label,
                "truth_quality": pd.to_numeric(df[p], errors="coerce") if p else pd.NA,
            }
        )
        part["truth_source"] = "ASAS-SN Variable Stars II/366"
        part["excluded_evidence_catalog"] = ""
        parts.append(part)
    if not parts:
        return pd.DataFrame()
    return D.bottom_k(pd.concat(parts, ignore_index=True).dropna(subset=["ra", "dec"]), limit)


def pulsars(limit):
    df = _vizier("B/psr/psr")
    if df.empty:
        return df
    idc = _pick(df, ["PSRJ", "Name"])
    ra, dec = _coords(df)
    out = pd.DataFrame(
        {"truth_id": df[idc].astype("string"), "ra": ra, "dec": dec, "truth_axis": "compact", "truth_class": "PULSAR"}
    )
    out["truth_source"] = "ATNF B/psr"
    out["excluded_evidence_catalog"] = "ATNF Pulsar Catalog"
    return D.bottom_k(out.dropna(subset=["ra", "dec"]), limit)


def pns(limit):
    df = _vizier("V/84/main")
    if df.empty:
        return df
    idc = _pick(df, ["PNG"])
    ra, dec = _coords(df)
    out = pd.DataFrame(
        {"truth_id": df[idc].astype("string"), "ra": ra, "dec": dec, "truth_axis": "phenomenon", "truth_class": "PN"}
    )
    out["truth_source"] = "Acker V/84 PN catalogue"
    out["excluded_evidence_catalog"] = "Acker PN Spectroscopy"
    return D.bottom_k(out.dropna(subset=["ra", "dec"]), limit)


def supernovae(limit):
    df = _vizier("B/sn/sncat")
    if df.empty:
        return df
    idc = _pick(df, ["SN"])
    typec = _pick(df, ["Type"])
    ra, dec = _coords(df)
    out = pd.DataFrame(
        {
            "truth_id": df[idc].astype("string"),
            "ra": ra,
            "dec": dec,
            "truth_axis": "phenomenon",
            "truth_class": "SN",
            "truth_subtype": df[typec].astype("string") if typec else pd.NA,
        }
    )
    out["truth_source"] = "Asiago B/sn"
    out["excluded_evidence_catalog"] = "Asiago Supernova Catalog"
    return D.bottom_k(out.dropna(subset=["ra", "dec"]), limit)


def build(out_dir: Path, limit: int):
    """Write one CSV per set, the summary and the manifest; return the summary rows."""
    out_dir.mkdir(parents=True, exist_ok=True)
    builders = {"rgb_agb": red_giants, "variables": variables, "pulsars": pulsars, "pn": pns, "sn": supernovae}
    summary, sets = [], {}
    for name, fn in builders.items():
        try:
            df = fn(limit)
            status = "ok"
        except Exception as exc:
            df = pd.DataFrame()
            status = f"error:{type(exc).__name__}:{exc}"
        f = out_dir / f"{name}_truth.csv"
        df.to_csv(f, index=False)
        classes = {}
        if not df.empty:
            for (axis, cls), g in df.groupby(["truth_axis", "truth_class"]):
                classes[f"{axis}|{cls}"] = {"rows": len(g), "ids_sha256": D.ids_sha256(g["truth_id"])}
        sets[name] = {"file": f.name, "sha256": D.file_sha256(f), "rows": len(df), "status": status, "classes": classes}
        summary.append(
            {
                "set": name,
                "rows": len(df),
                "status": status,
                "classes": "|".join(sorted(df.get("truth_class", pd.Series(dtype=str)).dropna().astype(str).unique())),
            }
        )
    pd.DataFrame(summary).to_csv(out_dir / "truth_build_summary.csv", index=False)
    (out_dir / "README.md").write_text(
        "# Independent per-axis truth sets\n\nGenerated truth sets carry `excluded_evidence_catalog` so evaluation code can mask same-catalog evidence and avoid circular validation. Candidate AGB labels from Vrard+2025 remain candidates and must not be described as spectroscopic certainty.\n",
        encoding="utf-8",
    )
    manifest = {"schema": SCHEMA, "seed": D.SEED, "limit": limit, "built_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sets": sets}
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def list_sha256(directory: Path) -> str:
    """One hash of the whole list: the SHA-256 of the sorted "file:sha256" lines of its manifest."""
    m = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
    return D.ids_sha256(f"{v['file']}:{v['sha256']}" for v in m["sets"].values())


def verify(directory: Path) -> list[str]:
    """Differences between a directory and its manifest (empty = the list is exactly what was frozen)."""
    mf = directory / MANIFEST
    if not mf.exists():
        return [f"{MANIFEST} is missing in {directory}"]
    m = json.loads(mf.read_text(encoding="utf-8"))
    problems = []
    for name, e in m["sets"].items():
        f = directory / e["file"]
        if e.get("status") != "ok" or not e.get("rows"):
            problems.append(f"{name}: the manifest records status {e.get('status')!r} with {e.get('rows')} rows")
            continue  # an empty file has no columns to read
        if not f.exists():
            problems.append(f"{e['file']} is missing")
            continue
        if D.file_sha256(f) != e["sha256"]:
            problems.append(f"{e['file']}: SHA-256 differs from the manifest")
            continue
        df = pd.read_csv(f)
        for key, c in e["classes"].items():
            axis, cls = key.split("|")
            g = df[(df.truth_axis == axis) & (df.truth_class == cls)]
            if len(g) != c["rows"] or D.ids_sha256(g["truth_id"]) != c["ids_sha256"]:
                problems.append(f"{e['file']}: class {key} differs from the manifest")
    return problems


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Get_data"))
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "generated")
    p.add_argument("--limit", type=int, default=250)
    p.add_argument("--verify", type=Path, help="check this directory against its manifest and exit (1 on any difference)")
    p.add_argument("--require-complete", action="store_true", help="exit 1 unless every set was built (a list to freeze must be complete)")
    a = p.parse_args()
    if a.verify:
        problems = verify(a.verify)
        print(json.dumps({"directory": str(a.verify), "problems": problems, "list_sha256": None if problems else list_sha256(a.verify)}, indent=2))
        raise SystemExit(1 if problems else 0)
    import throttle

    throttle.install()  # 3-5 s before every archive request (2.33.0)
    summary = build(a.out_dir, a.limit)
    print(json.dumps(summary, indent=2))
    bad = [x for x in summary if x["status"] != "ok" or not x["rows"]]
    if a.require_complete and bad:
        raise SystemExit(f"incomplete truth list, not to be frozen: {bad}")


if __name__ == "__main__":
    main()
