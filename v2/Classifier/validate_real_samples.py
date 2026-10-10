#!/usr/bin/env python3
"""Blind-style validation on named real astronomical sources.

SIMBAD is used only to resolve validation coordinates/reference type.  It is not
written into the blind raw-data directory.  Event sources remain distinct from
persistent hosts during source association.
"""

from __future__ import annotations
import argparse, importlib.util, json, math, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import astropy.units as u
import pandas as pd
from astropy.coordinates import SkyCoord
from astroquery.simbad import Simbad

ROOT = Path(__file__).resolve().parents[1]
GET = ROOT / "Get_data"
PRE = ROOT / "Preprocess"
CLS = ROOT / "Classifier"
# Allow collectors loaded by spec to import shared helpers from Get_data.
if str(GET) not in sys.path:
    sys.path.insert(0, str(GET))

SAMPLES = [
    {"name": "GD 71", "truth_axis": "physical", "truth_class": "WD"},
    {"name": "RR Lyr", "truth_axis": "variability", "truth_class": "RR_LYRAE"},
    {"name": "delta Cep", "truth_axis": "variability", "truth_class": "CEPHEID"},
    {"name": "Mira", "truth_axis": "physical", "truth_class": "AGB"},
    {"name": "PSR B0531+21", "truth_axis": "compact", "truth_class": "PULSAR"},
    {"name": "M 57", "truth_axis": "phenomenon", "truth_class": "PN"},
    {"name": "SN 2018fhw", "truth_axis": "phenomenon", "truth_class": "SN"},
    {"name": "SN 2011fe", "truth_axis": "phenomenon", "truth_class": "SN"},
    {"name": "3C 273", "truth_axis": "extragalactic", "truth_class": "AGN"},
]
SAMPLE_COLLECTORS = {
    "GD 71": ("gaia_dr3", "allwise", "twomass"),
    "RR Lyr": ("gaia_dr3",),
    "delta Cep": ("gaia_dr3",),
    "Mira": ("gaia_dr3", "allwise", "twomass", "agb_suh2021"),
    "PSR B0531+21": ("atnf_pulsar",),
    "M 57": ("hash_pn", "pn_spectroscopy"),
    "SN 2018fhw": ("asas_sn_supernova", "asiago_supernova"),
    "SN 2011fe": ("asiago_supernova",),
    "3C 273": ("gaia_dr3", "allwise", "sdss_dr18", "sdss_spectroscopy"),
}


def load_module(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    if s is None or s.loader is None:
        raise ImportError(path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def as_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if not s or s.lower() == "nan" else s


def as_num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def resolve(name):
    simbad = Simbad()
    simbad.add_votable_fields("otype", "sp")
    t = simbad.query_object(name)
    if t is None or len(t) == 0:
        raise RuntimeError(f"SIMBAD cannot resolve {name}")
    row = t.to_pandas().iloc[0]
    low = {str(k).lower(): k for k in row.index}
    rac, decc = low.get("ra"), low.get("dec")
    if rac is None or decc is None:
        raise KeyError(f"SIMBAD coordinate columns missing: {list(row.index)}")
    ra, dec = as_num(row[rac]), as_num(row[decc])
    if ra is None or dec is None:
        c = SkyCoord(str(row[rac]), str(row[decc]), unit=(u.hourangle, u.deg))
        ra, dec = float(c.ra.deg), float(c.dec.deg)
    return {
        "resolved_name": as_text(row[low["main_id"]]) if "main_id" in low else name,
        "ra": ra,
        "dec": dec,
        "truth_otype": as_text(row[low["otype"]]) if "otype" in low else None,
        "truth_sp": as_text(row[low["sp"]]) if "sp" in low else None,
    }


def run_cmd(args):
    p = subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(map(str, args))
            + "\nSTDOUT="
            + p.stdout[-2500:]
            + "\nSTDERR="
            + p.stderr[-5000:]
        )
    return p


def collect(sample, raw, radius):
    logs = []
    for name in SAMPLE_COLLECTORS[sample["name"]]:
        module = load_module(GET / f"{name}.py", f"realval_{name}")
        output = raw / f"{name}.csv"
        try:
            frame = module.fetch(sample["ra"], sample["dec"], radius)
            module.save(frame, output)
            logs.append({"collector": name, "status": "ok" if len(frame) else "empty", "rows": len(frame), "error": ""})
        except Exception as exc:
            logs.append({"collector": name, "status": "error", "rows": 0, "error": repr(exc)})
    return logs


def _separations(frame, ra, dec):
    ras = pd.to_numeric(frame["ra"], errors="coerce")
    decs = pd.to_numeric(frame["dec"], errors="coerce")
    dra = (ras - ra) * math.cos(math.radians(dec))
    dde = decs - dec
    return 3600.0 * (dra * dra + dde * dde) ** 0.5


def select_target(frame, ra, dec, radius, preferred_entity_kind=None):
    sep = _separations(frame, ra, dec)
    cand = frame.copy()
    cand["_sep_arcsec"] = sep
    cand = cand[cand["_sep_arcsec"] <= radius * 60.0].copy()
    if cand.empty:
        i = sep.idxmin()
        return frame.loc[i], float(sep.loc[i])
    if preferred_entity_kind and "entity_kind" in cand:
        subset = cand[cand["entity_kind"].astype(str) == preferred_entity_kind]
        if not subset.empty:
            cand = subset
    members = pd.to_numeric(cand.get("association_members"), errors="coerce").fillna(1)
    evidence = pd.to_numeric(cand.get("evidence_count"), errors="coerce").fillna(0)
    cand["_rank_members"] = members
    cand["_rank_evidence"] = evidence
    # Within the correct entity layer, positional agreement is the primary named-source criterion.
    cand = cand.sort_values(["_rank_members", "_rank_evidence", "_sep_arcsec"], ascending=[False, False, True])
    row = cand.iloc[0]
    return row, float(row["_sep_arcsec"])


def candidate_snapshot(frame, ra, dec, radius):
    sep = _separations(frame, ra, dec)
    out = []
    for idx in sep[sep <= radius * 60.0].sort_values().index[:12]:
        r = frame.loc[idx]
        out.append(
            {
                "object_id": as_text(r.get("object_id")),
                "sep_arcsec": float(sep.loc[idx]),
                "catalogs": as_text(r.get("catalogs")),
                "entity_kind": as_text(r.get("entity_kind")),
                "anchor_catalog": as_text(r.get("anchor_catalog")),
                "association_members": as_num(r.get("association_members")),
                "association_confidence_mean": as_num(r.get("association_confidence_mean")),
                "proper_motion_propagated_any": bool(r.get("proper_motion_propagated_any", False)),
                "primary_class": as_text(r.get("primary_class")),
                "physical_class": as_text(r.get("physical_class")),
                "variability_class": as_text(r.get("variability_class")),
                "compact_class": as_text(r.get("compact_class")),
                "phenomenon_class": as_text(r.get("phenomenon_class")),
            }
        )
    return out


def science_snapshot(row):
    cols = [
        "ra",
        "dec",
        "ref_epoch",
        "anchor_catalog",
        "entity_kind",
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
        "position_basis",
        "event_mjd",
        "event_time_raw",
        "sn_subtype",
        "pn_spectra_count",
        "pn_heii_4686",
        "pn_oiii_4363",
        "pn_oiii_5007",
        "pn_halpha",
        "pn_nii_6584",
        "pn_sii_6717",
        "pn_sii_6731",
    ]
    result = {}
    for c in cols:
        if c in row.index and pd.notna(row[c]):
            v = row[c]
            result[c] = v.item() if hasattr(v, "item") else v
    for c in row.index:
        low = str(c).lower()
        if (
            any(k in low for k in ("period", "p0", "pdot", "dispersion", "__dm"))
            and c not in result
            and pd.notna(row[c])
        ):
            v = row[c]
            result[c] = v.item() if hasattr(v, "item") else v
    return result


def classify_assisted(row, truth_otype, axis):
    axes = load_module(CLS / "control_axes.py", "realval_axes")
    payload = row.to_dict()
    for suffix in (
        "class",
        "confidence",
        "status",
        "evidence_json",
        "calibrated_probability",
        "calibration_status",
        "calibration_method",
    ):
        payload.pop(f"{axis}_{suffix}", None)
    payload["otype"] = truth_otype
    annotated = axes.annotate(pd.DataFrame([payload])).iloc[0]
    return as_text(annotated.get(f"{axis}_class")) or "UNKNOWN"


def validate_one(spec, base, radius):
    sample = {**spec, **resolve(spec["name"])}
    safe = spec["name"].replace(" ", "_").replace("/", "_")
    work = base / safe
    raw, pre, cls = work / "raw", work / "pre", work / "cls"
    raw.mkdir(parents=True, exist_ok=True)
    pre.mkdir(parents=True, exist_ok=True)
    cls.mkdir(parents=True, exist_ok=True)
    logs = collect(sample, raw, radius)
    usable = sum(int(x["rows"]) for x in logs if x["status"] == "ok")
    if usable == 0:
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
            "collector_json": json.dumps(logs, ensure_ascii=False),
            "candidate_json": "[]",
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
    run_cmd(
        [CLS / "01_prepare_input.py", "--input", pre / "likelihood_vectors.csv", "--out", cls / "classifier_input.csv"]
    )
    run_cmd([CLS / "control.py", "--input", cls / "classifier_input.csv", "--out", cls / "classified.csv"])
    classified = pd.read_csv(cls / "classified.csv")
    candidates = candidate_snapshot(classified, sample["ra"], sample["dec"], radius)
    preferred = "transient_event" if sample["truth_axis"] == "phenomenon" and sample["truth_class"] == "SN" else None
    row, separation = select_target(classified, sample["ra"], sample["dec"], radius, preferred)
    axis = sample["truth_axis"]
    blind = as_text(row.get(f"{axis}_class")) or "UNKNOWN"
    status = as_text(row.get(f"{axis}_status"))
    assisted = classify_assisted(row, sample["truth_otype"], axis)
    return {
        **sample,
        "nearest_sep_arcsec": separation,
        "primary_class": as_text(row.get("primary_class")),
        "blind_class": blind,
        "blind_status": status,
        "blind_match": blind == sample["truth_class"],
        "catalog_assisted_class": assisted,
        "catalog_assisted_match": assisted == sample["truth_class"],
        "science_json": json.dumps(science_snapshot(row), ensure_ascii=False, default=str),
        "collector_json": json.dumps(logs, ensure_ascii=False),
        "candidate_json": json.dumps(candidates, ensure_ascii=False),
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
        "candidate_json": "[]",
    }


def write_report(frame, out):
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "real_sample_validation.csv", index=False)
    valid = frame["blind_class"].ne("ERROR")
    matches = frame.loc[valid, "blind_match"].astype(bool)
    lines = [
        "# Real-sample multi-axis validation",
        "",
        "SIMBAD supplies only validation coordinates/reference type; no SIMBAD row enters the blind pipeline.",
        "Transient event rows are associated in a separate entity layer from persistent hosts.",
        "",
        f"- requested samples: **{len(frame)}**",
        f"- successfully executed: **{int(valid.sum())}/{len(frame)}**",
        f"- blind exact-axis matches: **{int(matches.sum())}/{len(matches)} ({matches.mean() if len(matches) else 0:.1%})**",
        "",
        "| sample | axis | expected | blind | status | sep_arcsec |",
        "|---|---|---|---|---|---:|",
    ]
    for _, r in frame.iterrows():
        sep = f"{r['nearest_sep_arcsec']:.3f}" if pd.notna(r["nearest_sep_arcsec"]) else ""
        lines.append(
            f"| {r['name']} | {r['truth_axis']} | {r['truth_class']} | {r['blind_class']} | {r['blind_status']} | {sep} |"
        )
    lines += ["", "## Scientific measurements and association diagnostics", ""]
    for _, r in frame.iterrows():
        lines += [
            f"### {r['name']}",
            "",
            f"- measured fields: {r['science_json']}",
            f"- collectors: {r['collector_json']}",
            f"- candidates: {r['candidate_json']}",
            "",
        ]
    lines += [
        "## Interpretation",
        "",
        "- UNKNOWN remains abstention, not negative evidence.",
        "- Association scores and Gaia catalog scores are raw evidence; calibrated probabilities are emitted only when an independent calibration model passes support gates.",
        "- Event catalog identity is kept separate from host-galaxy detections and event time is preserved when available.",
    ]
    (out / "REAL_SAMPLE_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", type=Path, default=CLS / "validation")
    p.add_argument("--radius-arcmin", type=float, default=0.25)
    p.add_argument("--max-workers", type=int, default=4)
    a = p.parse_args()
    by = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workers = max(1, min(int(a.max_workers), len(SAMPLES)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(validate_one, s, base, a.radius_arcmin): s for s in SAMPLES}
            for f in as_completed(futs):
                spec = futs[f]
                try:
                    r = f.result()
                except Exception as exc:
                    r = error_row(spec, exc)
                by[spec["name"]] = r
                print(
                    f"{spec['name']}: expected={spec['truth_class']} blind={r['blind_class']} status={r['blind_status']}",
                    flush=True,
                )
    frame = pd.DataFrame([by[s["name"]] for s in SAMPLES])
    write_report(frame, a.out_dir)
    print(
        frame[["name", "truth_axis", "truth_class", "blind_class", "blind_status", "blind_match"]].to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
