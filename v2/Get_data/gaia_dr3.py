"""Gaia DR3 collector with layered TAP retrieval and independent VizieR fallback.

The primary path retrieves gaiadr3.gaia_source first, then optional products by
source_id.  If the Gaia TAP service fails completely, VizieR I/355 + I/358 is
used as a read-only fallback so transient archive outages do not erase base
astrometry or variability classification evidence.
"""

from __future__ import annotations
import time
from pathlib import Path
import pandas as pd

import sys

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from gaia_release import SLOT_CATALOG, current as _release, table as _table, RELEASES
from _catalog_utils import BASE, pick, save_csv, vizier_cone

# Pipeline slot name for every Gaia release (see gaia_release.py); each row
# records the release and epoch it really comes from.
CATALOG = SLOT_CATALOG
SOURCE = [
    "source_id",
    "designation",
    "ra",
    "dec",
    "ra_error",
    "dec_error",
    "parallax",
    "parallax_error",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "pmra_pmdec_corr",  # full proper-motion covariance for the zero-motion test (2.38.0; Li & Fynbo 2026)
    "ruwe",
    "phot_g_mean_flux",
    "phot_g_mean_flux_error",
    "phot_g_mean_mag",
    "phot_bp_mean_flux",
    "phot_bp_mean_flux_error",
    "phot_bp_mean_mag",
    "phot_rp_mean_flux",
    "phot_rp_mean_flux_error",
    "phot_rp_mean_mag",
    "bp_rp",
    "bp_g",
    "g_rp",
    "phot_bp_rp_excess_factor",
    "radial_velocity",
    "radial_velocity_error",
    "rv_nb_transits",
]
AP = [
    "teff_gspphot",
    "logg_gspphot",
    "mh_gspphot",
    "distance_gspphot",
    "ag_gspphot",
    "ebpminrp_gspphot",
    "mass_flame",
    "age_flame",
    "evolstage_flame",
    "flags_flame",
    "classprob_dsc_combmod_quasar",
    "classprob_dsc_combmod_galaxy",
    "classprob_dsc_combmod_star",
    "classprob_dsc_combmod_whitedwarf",
    "classprob_dsc_combmod_binarystar",
]
# Spectroscopic parameters: GSP-Spec from RVS spectra (Recio-Blanco et al.
# 2023) and the ESP-ELS emission-line class from BP/RP (Creevey et al. 2023).
# Same table as AP, fetched in the same query (column names checked against
# the archive metadata, 2026-10-10): a second query would leave one more
# abandoned daemon thread when TAP is slow, and abandoned threads crashed the
# interpreter at exit (scientific cross-validation, compact-pulsar shard).
# ESP-UCD (2.22.0): Teff of ultracool-dwarf candidates (< 2700 K, ~M7 and
# later) from the RP spectrum and its quality category (Sarro et al. 2023,
# A&A 669, A139); names checked against the archive (v2_new_targets.yml).
# Not in the VizieR fallback (left empty there).
SPEC_AP = [
    "teff_gspspec",
    "logg_gspspec",
    "mh_gspspec",
    "flags_gspspec",
    "classlabel_espels",
    "classlabel_espels_flag",
    "teff_espucd",
    "flags_espucd",
]
VAR_SUMMARY = [
    "in_vari_classification_result",
    "in_vari_rrlyrae",
    "in_vari_cepheid",
    "in_vari_long_period_variable",
    "in_vari_eclipsing_binary",
    "in_vari_rotation_modulation",
    "in_vari_agn",
    "in_vari_microlensing",
    "in_vari_compact_companion",
]

# Wall-clock budgets: a slow Gaia archive previously held a field for ~26 min
# in retries; past the budget the VizieR mirror fallback is used instead.
# From CI runners the ESA TAP rarely answers a cone search within 2 min while
# VizieR answers in seconds, so the base budget is short.  2.33.0: +20 s each,
# for the 3-5 s pause (throttle.py) before each of an async job's ~4-5
# requests (submit, status polls, results).
BASE_TAP_BUDGET_S = 50.0
OPTIONAL_TAP_BUDGET_S = 80.0
OPTIONAL_CHUNK = 2000
# All optional tables together stay well inside the 300 s controller budget
# (worst case was 50 + 3 tables x ceil(N/500) x 80 s, capped here).
OPTIONAL_TOTAL_BUDGET_S = 180.0
SYNC_MAX_ROWS = 2000


def _bounded(fn, budget_s, *args):
    # Daemon thread: an abandoned slow query must not block interpreter exit.
    # ``fn`` gets the deadline so an abandoned thread stops retrying instead
    # of running its remaining attempts in the background (2.19.0).
    import threading

    box = {}
    deadline = time.monotonic() + budget_s

    def target():
        try:
            box["value"] = fn(*args, deadline=deadline)
        except BaseException as exc:
            box["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(budget_s)
    if t.is_alive():
        raise TimeoutError(f"Gaia TAP exceeded {budget_s:.0f} s")
    if "error" in box:
        raise box["error"]
    return box["value"]


def _tap(query: str, retries: int = 4, deadline: float | None = None) -> pd.DataFrame:
    from astroquery.gaia import Gaia

    last = None
    expired = lambda: deadline is not None and time.monotonic() >= deadline
    for attempt in range(retries):
        try:
            return Gaia.launch_job_async(query).get_results().to_pandas()
        except Exception as exc:
            last = exc
            if expired():
                raise TimeoutError(f"Gaia TAP deadline passed; last={exc!r}") from exc
            if attempt + 1 < retries:
                time.sleep(min(8, 2**attempt))
    if expired():
        raise TimeoutError(f"Gaia TAP deadline passed; last={last!r}")
    try:
        df = Gaia.launch_job(query).get_results().to_pandas()
    except Exception as exc:
        raise RuntimeError(f"Gaia TAP failed after retries; async={last!r}; sync={exc!r}") from exc
    # Synchronous Gaia TAP jobs are capped at SYNC_MAX_ROWS (astroquery adds
    # TOP 2000).  A full page is a cut cone: fail so the caller falls back to
    # the complete VizieR copy instead of caching a truncated field (2.23.0).
    if len(df) >= SYNC_MAX_ROWS:
        raise RuntimeError(f"Gaia sync TAP result truncated at {SYNC_MAX_ROWS} rows; async={last!r}")
    return df


def _merge_optional(
    base: pd.DataFrame, table: str, columns: list[str], status_name: str, deadline: float | None = None
) -> pd.DataFrame:
    if base.empty:
        base[status_name] = pd.Series(dtype="string")
        return base
    ids = [str(int(x)) for x in pd.to_numeric(base["source_id"], errors="coerce").dropna().unique()]
    if not ids:
        base[status_name] = "missing_source_id"
        return base
    pieces = []
    try:
        # 2000 ids per query (sent by POST): with 500 a crowded field (6,966
        # sources at l = 182, b = +2, 2026-10-21) needed 14 queries, each also
        # paced 3-5 s, and lost every optional table (DSC included) to the
        # shared deadline.
        for start in range(0, len(ids), OPTIONAL_CHUNK):
            chunk = ids[start : start + OPTIONAL_CHUNK]
            select = "source_id," + ",".join(columns)
            # One shared deadline for all optional tables, so a slow archive
            # cannot push the base astrometry past the controller budget.
            left = (
                OPTIONAL_TAP_BUDGET_S if deadline is None else min(OPTIONAL_TAP_BUDGET_S, deadline - time.monotonic())
            )
            if left <= 0:
                raise TimeoutError("optional Gaia tables: shared deadline passed")
            pieces.append(_bounded(_tap, left, f"SELECT {select} FROM {table} WHERE source_id IN ({','.join(chunk)})"))
        opt = pd.concat(pieces, ignore_index=True, sort=False) if pieces else pd.DataFrame()
        if not opt.empty:
            opt["source_id"] = pd.to_numeric(opt["source_id"], errors="coerce").astype("Int64")
            base["source_id"] = pd.to_numeric(base["source_id"], errors="coerce").astype("Int64")
            base = base.merge(opt.drop_duplicates("source_id"), on="source_id", how="left")
        status = "ok"
    except Exception as exc:
        status = "error:" + type(exc).__name__
    for col in columns:
        if col not in base.columns:
            base[col] = pd.NA
    base[status_name] = status
    return base


# Astrometric fidelity (Rybizki et al. 2022, MNRAS 510, 2597): the
# probability that the EDR3 = DR3 astrometric solution is not spurious,
# served by GAVO's TAP (table gedr3spur.main, keyed by source_id).  Used by
# Stage 5 to trust proper motions inside bright nebulae, where the BP/RP
# excess C* is raised by the nebula rather than by a bad solution (2.42.0).
FIDELITY_TAP = "https://dc.zah.uni-heidelberg.de/tap"
FIDELITY_TABLE = "gedr3spur.main"


def _merge_fidelity(base: pd.DataFrame, deadline: float | None = None) -> pd.DataFrame:
    if base.empty:
        base["fidelity_v2"] = pd.Series(dtype="float")
        return base
    ids = [str(int(x)) for x in pd.to_numeric(base["source_id"], errors="coerce").dropna().unique()]
    status = "ok"
    try:
        import pyvo

        svc = pyvo.dal.TAPService(FIDELITY_TAP)
        pieces = []
        for start in range(0, len(ids), OPTIONAL_CHUNK):
            left = OPTIONAL_TAP_BUDGET_S if deadline is None else min(OPTIONAL_TAP_BUDGET_S, deadline - time.monotonic())
            if left <= 0:
                raise TimeoutError("fidelity: shared deadline passed")
            q = f"SELECT source_id, fidelity_v2 FROM {FIDELITY_TABLE} WHERE source_id IN ({','.join(ids[start:start + OPTIONAL_CHUNK])})"
            pieces.append(_bounded(lambda q=q, deadline=None: svc.run_sync(q).to_table().to_pandas(), left))
        opt = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
        if not opt.empty:
            opt["source_id"] = pd.to_numeric(opt["source_id"], errors="coerce").astype("Int64")
            base["source_id"] = pd.to_numeric(base["source_id"], errors="coerce").astype("Int64")
            base = base.merge(opt.drop_duplicates("source_id"), on="source_id", how="left")
    except Exception as exc:
        status = "error:" + type(exc).__name__
    if "fidelity_v2" not in base:
        base["fidelity_v2"] = pd.NA
    base["gaia_fidelity_query_status"] = status
    return base


def _vizier_fallback(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    src = vizier_cone(RELEASES["DR3"].vizier_source, ra, dec, radius_arcmin)
    if src is None:
        return pd.DataFrame()
    if src.empty:
        return src
    mapping = {
        "Source": "source_id",
        "RA_ICRS": "ra",
        "DE_ICRS": "dec",
        "e_RA_ICRS": "ra_error",
        "e_DE_ICRS": "dec_error",
        "Plx": "parallax",
        "e_Plx": "parallax_error",
        "pmRA": "pmra",
        "e_pmRA": "pmra_error",
        "pmDE": "pmdec",
        "e_pmDE": "pmdec_error",
        "pmRApmDEcor": "pmra_pmdec_corr",
        "RUWE": "ruwe",
        "Gmag": "phot_g_mean_mag",
        "BPmag": "phot_bp_mean_mag",
        "RPmag": "phot_rp_mean_mag",
        "BP-RP": "bp_rp",
        "E(BP/RP)": "phot_bp_rp_excess_factor",  # C* gates (WD locus, hot subdwarfs) need it (2.23.0)
        "RV": "radial_velocity",
        "e_RV": "radial_velocity_error",
        "Teff": "teff_gspphot",
        "logg": "logg_gspphot",
        "[Fe/H]": "mh_gspphot",
        "Dist": "distance_gspphot",
        # GSP-Phot extinction (used to deredden colours and absolute magnitudes downstream).
        "AG": "ag_gspphot",
        "E(BP-RP)": "ebpminrp_gspphot",
    }
    low = {str(x).lower(): x for x in src.columns}
    out = pd.DataFrame(index=src.index)
    for old, new in mapping.items():
        col = old if old in src.columns else low.get(old.lower())
        out[new] = src[col] if col is not None else pd.NA
    out["source_id"] = pd.to_numeric(out["source_id"], errors="coerce").astype("Int64")
    out["designation"] = "Gaia DR3 " + out["source_id"].astype("string")
    # Gaia DSC-Combmod class probabilities (astrophysical-parameter table).
    try:
        dsc = {
            "PQSO": "classprob_dsc_combmod_quasar",
            "PGal": "classprob_dsc_combmod_galaxy",
            "Pstar": "classprob_dsc_combmod_star",
            "PWD": "classprob_dsc_combmod_whitedwarf",
            "Pbin": "classprob_dsc_combmod_binarystar",
            # VizieR I/355/paramp names of the GSP-Spec and ESP-ELS columns.
            "Teff-S": "teff_gspspec",
            "logg-S": "logg_gspspec",
            "[M/H]-S": "mh_gspspec",
            "Flags": "flags_gspspec",
            "ClassELS": "classlabel_espels",
            "f_ClassELS": "classlabel_espels_flag",
        }
        ap = vizier_cone("I/355/paramp", ra, dec, radius_arcmin, ["Source", *dsc])
        if ap is not None and not ap.empty and "Source" in ap.columns:
            ap = ap[["Source", *[k for k in dsc if k in ap.columns]]].rename(columns={"Source": "source_id", **dsc})
            ap["source_id"] = pd.to_numeric(ap["source_id"], errors="coerce").astype("Int64")
            out = out.merge(ap.drop_duplicates("source_id"), on="source_id", how="left")
    except Exception:
        pass
    # Independent variability table fallback. A cone query is cheap for named-source validation.
    try:
        var = vizier_cone("I/358/vclassre", ra, dec, radius_arcmin)
        if var is not None and not var.empty:
            sid = pick(var, ["Source", "source_id"])
            cl = pick(var, ["Class", "best_class_name"])
            sc = pick(var, ["ClassSc", "best_class_score"])
            if sid:
                tmp = pd.DataFrame(
                    {
                        "source_id": pd.to_numeric(var[sid], errors="coerce").astype("Int64"),
                        "best_class_name": var[cl] if cl else pd.NA,
                        "best_class_score": pd.to_numeric(var[sc], errors="coerce") if sc else pd.NA,
                    }
                ).drop_duplicates("source_id")
                out = out.merge(tmp, on="source_id", how="left")
    except Exception:
        pass
    for col in AP + SPEC_AP + VAR_SUMMARY + ["best_class_name", "best_class_score"]:
        if col not in out.columns:
            out[col] = pd.NA
    out["gaia_base_query_status"] = "vizier_fallback"
    out["gaia_ap_query_status"] = "fallback_partial"
    out["gaia_vari_classifier_query_status"] = "vizier_fallback"
    out["gaia_vari_summary_query_status"] = "fallback_unavailable"
    return out


# GSP-Spec quality (Babusiaux et al. 2023): a parameter is usable when its
# flags_gspspec characters are 0 (1-based positions).  The 41-character flag
# string loses its leading zeros when VizieR serves it as a number and when a
# CSV is read back, so the decision is made here, on the zero-padded string,
# and stored as 0/1 columns.
GSPSPEC_FLAG_POS = {"teff": (1, 4, 8, 13), "logg": (2, 5, 8, 13), "mh": (3, 6, 8)}


def _gspspec_quality(df: pd.DataFrame) -> pd.DataFrame:
    def pad(v):
        s = str(v).strip() if v is not None and str(v).strip() not in ("", "nan", "<NA>", "None") else ""
        if "e" in s.lower():
            return None  # float notation: digits already lost, decision unknown
        s = s.split(".")[0]
        return s.zfill(41) if s.isdigit() else None

    flags = df["flags_gspspec"].map(pad) if "flags_gspspec" in df else pd.Series(None, index=df.index, dtype=object)
    for par, pos in GSPSPEC_FLAG_POS.items():
        df[f"gspspec_{par}_ok"] = flags.map(
            lambda f: int(all(f[i - 1] == "0" for i in pos)) if isinstance(f, str) else pd.NA
        ).astype("Int64")
    if "flags_gspspec" in df:
        df["flags_gspspec"] = flags.map(lambda f: "F" + f if isinstance(f, str) else None)  # text, keeps the zeros
    return df


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    rel = _release()
    used = rel
    select = ",".join(SOURCE)
    q = f"""SELECT {select} FROM {_table(rel,'gaia_source')} WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{float(ra):.10f},{float(dec):.10f},{float(radius_arcmin)/60.0:.10f}))"""
    try:
        df = _bounded(_tap, BASE_TAP_BUDGET_S, q)
        df["gaia_base_query_status"] = "tap"
        if not df.empty:
            opt_deadline = time.monotonic() + OPTIONAL_TOTAL_BUDGET_S
            df = _merge_optional(
                df, _table(rel, "astrophysical_parameters"), AP + SPEC_AP, "gaia_ap_query_status", opt_deadline
            )
            df = _merge_optional(
                df,
                _table(rel, "vari_classifier_result"),
                ["best_class_name", "best_class_score"],
                "gaia_vari_classifier_query_status",
                opt_deadline,
            )
            df = _merge_optional(
                df, _table(rel, "vari_summary"), VAR_SUMMARY, "gaia_vari_summary_query_status", opt_deadline
            )
            if rel.name == "DR3":  # the classifier was trained on (E)DR3 solutions
                df = _merge_fidelity(df, opt_deadline)
    except Exception:
        # The VizieR mirror is DR3: label the rows DR3 (epoch 2016.0) even
        # when another release was requested, so propagation stays correct.
        df = _vizier_fallback(ra, dec, radius_arcmin)
        used = RELEASES["DR3"]
    if df.empty:
        return pd.DataFrame(
            columns=BASE + SOURCE[2:] + AP + SPEC_AP + ["best_class_name", "best_class_score"] + VAR_SUMMARY
        )
    df.insert(0, "catalog", CATALOG)
    sid = pd.to_numeric(df["source_id"], errors="coerce").astype("Int64").astype("string")
    df.insert(1, "catalog_object_id", sid)
    df.insert(
        2,
        "object_name",
        df.get("designation", pd.Series(used.designation_prefix + " " + sid, index=df.index)).astype("string"),
    )
    df["query_radius_arcmin"] = float(radius_arcmin)
    df["gaia_release"] = used.name
    df["ref_epoch"] = used.ref_epoch
    df["entity_kind"] = "persistent_source"
    df["psf_fwhm_arcsec"] = 0.18
    df = _gspspec_quality(df)
    # Native RA/Dec errors are mas; Stage-1 performs the conversion.
    return df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)


def save(df: pd.DataFrame, path) -> None:
    save_csv(df, path, "Gaia")
