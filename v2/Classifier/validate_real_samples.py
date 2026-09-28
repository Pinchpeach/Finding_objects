#!/usr/bin/env python3
"""Blind-style validation on named real astronomical sources.

SIMBAD is used only to resolve the requested object's coordinates and external reference type. It is not written into the blind raw-data directory, so every blind classification must arise from independent survey/catalog measurements.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import astropy.units as u
import pandas as pd
from astropy.coordinates import SkyCoord
from astroquery.simbad import Simbad

ROOT = Path(__file__).resolve().parents[1]
GET = ROOT / "Get_data"
PRE = ROOT / "Preprocess"
CLS = ROOT / "Classifier"

SAMPLES = [
    {"name": "GD 71", "truth_axis": "physical", "truth_class": "WD"},
    {"name": "RR Lyr", "truth_axis": "variability", "truth_class": "RR_LYRAE"},
    {"name": "delta Cep", "truth_axis": "variability", "truth_class": "CEPHEID"},
    {"name": "Mira", "truth_axis": "physical", "truth_class": "AGB"},
    {"name": "PSR B0531+21", "truth_axis": "compact", "truth_class": "PULSAR"},
    {"name": "M 57", "truth_axis": "phenomenon", "truth_class": "PN"},
    {"name": "SN 2011fe", "truth_axis": "phenomenon", "truth_class": "SN"},
    {"name": "3C 273", "truth_axis": "extragalactic", "truth_class": "QSO"},
]

SAMPLE_COLLECTORS = {
    "GD 71": ("gaia_dr3", "allwise", "twomass"),
    "RR Lyr": ("gaia_dr3",),
    "delta Cep": ("gaia_dr3",),
    "Mira": ("gaia_dr3", "allwise", "twomass", "agb_suh2021"),
    "PSR B0531+21": ("atnf_pulsar",),
    "M 57": (),
    "SN 2011fe": (),
    "3C 273": ("gaia_dr3", "allwise", "sdss_dr18", "sdss_spectroscopy"),
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_text(value):
    if value is None:
        return None
    s = str(value).strip()
    return None if not s or s.lower() == "nan" else s


def as_num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def resolve(name: str):
    simbad = Simbad()
    simbad.add_votable_fields("otype", "sp")
    table = simbad.query_object(name)
    if table is None or len(table) == 0:
        raise RuntimeError(f"SIMBAD cannot resolve {name}")
    row = table.to_pandas().iloc[0]
    low = {str(k).lower(): k for k in row.index}
    rac, decc = low.get("ra"), low.get("dec")
    if rac is None or decc is None:
        raise KeyError(f"SIMBAD coordinate columns missing for {name}: {list(row.index)}")
    ra, dec = as_num(row[rac]), as_num(row[decc])
    if ra is None or dec is None:
        coord = SkyCoord(str(row[rac]), str(row[decc]), unit=(u.hourangle, u.deg))
        ra, dec = float(coord.ra.deg), float(coord.dec.deg)
    return {
        "resolved_name": as_text(row[low["main_id"]]) if "main_id" in low else name,
        "ra": ra,
        "dec": dec,
        "truth_otype": as_text(row[low["otype"]]) if "otype" in low else None,
        "truth_sp": as_text(row[low["sp"]]) if "sp" in low else None,
    }


def run_cmd(args):
    proc = subprocess.run(
        [sys.executable, *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(map(str, args))
            + "\nSTDOUT="
            + proc.stdout[-2500:]
            + "\nSTDERR="
            + proc.stderr[-5000:]
        )
    return proc


def collect(sample, raw: Path, radius_arcmin: float):
    logs = []
    for name in SAMPLE_COLLECTORS[sample["name"]]:
        module = load_module(GET / f"{name}.py", f"realval_{name}")
        output = raw / f"{name}.csv"
        try:
            frame = module.fetch(sample["ra"], sample["dec"], radius_arcmin)
            module.save(frame, output)
            logs.append({
                "collector": name,
                "status": "ok" if len(frame) else "empty",
                "rows": len(frame),
                "error": "",
            })
        except Exception as exc:
            logs.append({
                "collector": name,
                "status": "error",
                "rows": 0,
                "error": repr(exc),
            })
    return logs


def select_target(frame: pd.DataFrame, ra: float, dec: float, radius_arcmin: float):
    ras = pd.to_numeric(frame["ra"], errors="coerce")
    decs = pd.to_numeric(frame["dec"], errors="coerce")
    dra = (ras - ra) * math.cos(math.radians(dec))
    dde = decs - dec
    sep = 3600.0 * (dra * dra + dde * dde) ** 0.5

    candidates = frame.copy()
    candidates["_sep_arcsec"] = sep
    candidates = candidates[candidates["_sep_arcsec"] <= radius_arcmin * 60.0].copy()
    if candidates.empty:
        index = sep.idxmin()
        return frame.loc[index], float(sep.loc[index])

    # Prefer the object supported by the largest number of independent catalog
    # members; use evidence count and angular separation only as tie breakers.
    members = pd.to_numeric(candidates.get("association_members"), errors="coerce").fillna(1)
    evidence = pd.to_numeric(candidates.get("evidence_count"), errors="coerce").fillna(0)
    candidates["_rank_members"] = members
    candidates["_rank_evidence"] = evidence
    candidates = candidates.sort_values(
        ["_rank_members", "_rank_evidence", "_sep_arcsec"],
        ascending=[False, False, True],
    )
    row = candidates.iloc[0]
    return row, float(row["_sep_arcsec"])


def science_snapshot(row: pd.Series):
    columns = [
        "ra",
        "dec",
        "parallax",
        "parallax_error",
        "pmra",
        "pmdec",
        "ruwe",
        "phot_g_mean_mag",
        "phot_bp_mean_mag",
        "phot_rp_mean_mag",
        "bp_rp",
        "teff_gspphot",
        "logg_gspphot",
        "mh_gspphot",
        "mass_flame",
        "age_flame",
        "evolstage_flame",
        "best_class_name",
        "best_class_score",
        "agb_subclass",
    ]
    result = {}
    for column in columns:
        if column in row.index and pd.notna(row[column]):
            value = row[column]
            result[column] = value.item() if hasattr(value, "item") else value

    # ATNF field naming can vary by service release. Preserve common pulsar
    # period/derivative/dispersion-measure fields without assuming one schema.
    for column in row.index:
        low = str(column).lower()
        if (
            any(key in low for key in ("period", "p0", "pdot", "dispersion", "__dm"))
            and column not in result
            and pd.notna(row[column])
        ):
            value = row[column]
            result[column] = value.item() if hasattr(value, "item") else value
    return result


def classify_assisted(row: pd.Series, truth_otype, axis: str):
    # Catalog-assisted routing is diagnostic only. Drop pre-existing axis output
    # columns before re-annotating to avoid duplicate-column ambiguity.
    axes = load_module(CLS / "control_axes.py", "realval_axes")
    payload = row.to_dict()
    for suffix in ("class","confidence","status","evidence_json"):
        payload.pop(f"{axis}_{suffix}", None)
    payload["otype"] = truth_otype
    annotated = axes.annotate(pd.DataFrame([payload])).iloc[0]
    return as_text(annotated.get(f"{axis}_class")) or "UNKNOWN"


def validate_one(spec, base: Path, radius_arcmin: float):
    sample = {**spec, **resolve(spec["name"])}
    safe = spec["name"].replace(" ", "_").replace("/", "_")
    work = base / safe
    raw, pre, cls = work / "raw", work / "pre", work / "cls"
    raw.mkdir(parents=True, exist_ok=True)
    pre.mkdir(parents=True, exist_ok=True)
    cls.mkdir(parents=True, exist_ok=True)

    collector_logs = collect(sample, raw, radius_arcmin)
    usable_rows = sum(int(x["rows"]) for x in collector_logs if x["status"] == "ok")
    if usable_rows == 0:
        return {
            **sample,
            "nearest_sep_arcsec": math.nan,
            "primary_class": "UNKNOWN",
            "blind_class": "UNKNOWN",
            "blind_status": "NO_BLIND_CATALOG_EVIDENCE",
            "blind_match": False,
            "catalog_assisted_class": "UNKNOWN",
            "catalog_assisted_match": False,
            "science_json": "{}",
            "collector_json": json.dumps(collector_logs, ensure_ascii=False),
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
        [
            PRE / "05_likelihood_vectors.py",
            "--evidence",
            pre / "evidence.csv",
            "--out",
            pre / "likelihood_vectors.csv",
        ]
    )
    run_cmd(
        [
            CLS / "01_prepare_input.py",
            "--input",
            pre / "likelihood_vectors.csv",
            "--out",
            cls / "classifier_input.csv",
        ]
    )
    run_cmd(
        [
            CLS / "control.py",
            "--input",
            cls / "classifier_input.csv",
            "--out",
            cls / "classified.csv",
        ]
    )

    classified = pd.read_csv(cls / "classified.csv")
    row, separation = select_target(classified, sample["ra"], sample["dec"], radius_arcmin)
    axis = sample["truth_axis"]
    blind_class = as_text(row.get(f"{axis}_class")) or "UNKNOWN"
    blind_status = as_text(row.get(f"{axis}_status"))
    assisted_class = classify_assisted(row, sample["truth_otype"], axis)

    return {
        **sample,
        "nearest_sep_arcsec": separation,
        "primary_class": as_text(row.get("primary_class")),
        "blind_class": blind_class,
        "blind_status": blind_status,
        "blind_match": blind_class == sample["truth_class"],
        "catalog_assisted_class": assisted_class,
        "catalog_assisted_match": assisted_class == sample["truth_class"],
        "science_json": json.dumps(science_snapshot(row), ensure_ascii=False, default=str),
        "collector_json": json.dumps(collector_logs, ensure_ascii=False),
    }


def error_row(spec, exc):
    return {
        **spec,
        "resolved_name": None,
        "ra": math.nan,
        "dec": math.nan,
        "truth_otype": None,
        "truth_sp": None,
        "nearest_sep_arcsec": math.nan,
        "primary_class": None,
        "blind_class": "ERROR",
        "blind_status": repr(exc),
        "blind_match": False,
        "catalog_assisted_class": "ERROR",
        "catalog_assisted_match": False,
        "science_json": "{}",
        "collector_json": "[]",
    }


def write_report(frame: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_dir / "real_sample_validation.csv", index=False)

    valid = frame["blind_class"].ne("ERROR")
    matches = frame.loc[valid, "blind_match"].astype(bool)
    lines = [
        "# Real-sample multi-axis validation",
        "",
        "SIMBAD supplies only the validation coordinates and external reference type; no SIMBAD row is passed into the blind pipeline.",
        "Catalog-assisted results are reported separately and are not independent validation.",
        "",
        f"- requested samples: **{len(frame)}**",
        f"- successfully executed samples: **{int(valid.sum())}/{len(frame)}**",
        f"- blind exact-axis matches among executed: **{int(matches.sum())}/{len(matches)} ({matches.mean() if len(matches) else 0:.1%})**",
        "",
        "| sample | SIMBAD ref | axis | expected | blind | status | sep_arcsec | assisted |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for _, row in frame.iterrows():
        sep = row["nearest_sep_arcsec"]
        sep_text = f"{sep:.3f}" if pd.notna(sep) else ""
        lines.append(
            f"| {row['name']} | {row['truth_otype']} | {row['truth_axis']} | "
            f"{row['truth_class']} | {row['blind_class']} | {row['blind_status']} | "
            f"{sep_text} | {row['catalog_assisted_class']} |"
        )

    lines += ["", "## Scientific measurements", ""]
    for _, row in frame.iterrows():
        lines.append(f"### {row['name']}")
        lines.append("")
        if pd.notna(row["ra"]) and pd.notna(row["dec"]):
            lines.append(f"- coordinates: RA={row['ra']:.8f} deg, Dec={row['dec']:.8f} deg")
        lines.append(f"- reference spectral type: {row['truth_sp']}")
        lines.append(f"- measured fields: {row['science_json']}")
        lines.append(f"- collectors: {row['collector_json']}")
        lines.append("")

    lines += [
        "## Interpretation",
        "",
        "- Blind success means the expected axis class was recovered without SIMBAD otype.",
        "- UNKNOWN is treated as abstention, not as a false scientific claim.",
        "- PN/SN catalog-assisted matches demonstrate routing only; they are not independent physical validation.",
        "- A catalog query failure is retained explicitly instead of being interpreted as an astrophysical non-detection.",
    ]
    (out_dir / "REAL_SAMPLE_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=CLS / "validation")
    parser.add_argument("--radius-arcmin", type=float, default=0.25)
    args = parser.parse_args()

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for spec in SAMPLES:
            try:
                result = validate_one(spec, base, args.radius_arcmin)
            except Exception as exc:
                result = error_row(spec, exc)
            rows.append(result)
            print(
                f"{spec['name']}: expected={spec['truth_class']} "
                f"blind={result['blind_class']} status={result['blind_status']}",
                flush=True,
            )

    frame = pd.DataFrame(rows)
    write_report(frame, args.out_dir)
    print(frame[["name", "truth_axis", "truth_class", "blind_class", "blind_status", "blind_match"]].to_string(index=False))


if __name__ == "__main__":
    main()
