#!/usr/bin/env python3
"""NED and SIMBAD rows of the 26 deep COSMOS fields, with the position uncertainties the two databases state themselves (2.62.7, task "더").

    python collect_deep_cosmos_literature.py probe  --out DIR
    python collect_deep_cosmos_literature.py collect --out DIR [--set first|second|all] [--fields a,b] [--fields-file deep_cosmos_fields_2.csv]

Why.  The deep COSMOS bundles (``v2_deep_cosmos.yml``) are blind: no spectroscopic and no literature collector.  Everything this project measured about NED / SIMBAD rows
(WORK_REPORT_2026-11-28b.md) comes from ONE field, the real-use COSMOS 2' cone, where 71 % of the objects are made of literature rows only.  This collects the two databases for the 26
fields and nothing else, so that the same measurements can be made on 26 fields (``merge_deep_cosmos_literature.py`` puts the rows next to the stored blind rows, offline).

What is collected per field (all 6' cones, the radius of ``collect_deep_cosmos.py``):

* SIMBAD     the rows of the normal collector (``Get_data/simbad.py:fetch``: the same cone query, the same columns, ``coo_err_maj/min/angle`` in mas, ``coo_wavelength``,
             ``coo_bibcode``, ``otype``, the references) + two columns the collector does not ask for: ``coo_qual`` (CHAR(1), quality of the coordinates) and ``otypes`` (every type, ``|``
             separated; the ``alltypes`` view).  One more request.  The default collector is NOT changed: its output stays what it was.
* NED        the rows of the normal collector (cone search) + the position-uncertainty ellipse of ``NEDTAP.objdir`` (``uncmaja``, ``uncmina`` in arcsec, ``uncposa`` in degrees,
             East of North), attached by object name (``prefname``), by position (0.3'') for names that do not match; ``ned_unc_source`` says which.

Schema facts (read from the services' own table lists by an agent on 2026-11-28; not from memory):
  NED  https://ned.ipac.caltech.edu/tap/tables : ``NEDTAP.objdir`` (view): ``prefname`` CHAR(30), ``ra`` / ``dec`` deg, ``uncmaja`` / ``uncmina`` arcsec "Uncertainty Ellipse, Semimajor /
       Semiminor Axis in arcseconds", ``uncposa`` deg "PA in degrees (East of North)".  NOT stated on that page: the confidence level of the ellipse (an earlier literature check of the
       NED FAQ said 95 %; not re-read), that ``prefname`` equals the 'Object Name' of the cone search, and the sync URL (``NED_TAP_SYNC`` below is the standard path, unverified).
  SIMBAD https://simbad.harvard.edu/simbad/sim-tap/tables (the CDS host answered 404 that day): ``basic.coo_err_maj`` / ``coo_err_min`` REAL mas, ``coo_err_angle`` SMALLINT deg,
       ``coo_qual`` CHAR(1), ``coo_wavelength`` CHAR(1) (R, I, V, U, X, G), ``coo_bibcode`` CHAR(19); ``otypes`` is a TABLE (``oidref`` -> ``basic.oid``), the view ``alltypes``
       has one row per object with ``otypes`` concatenated with pipes.
``probe`` reads the same two table lists and FAILS when a column the collection needs is missing, so a changed schema stops the run before 26 fields are asked.

Requests wait 3-5 s each (``Get_data/throttle.py``).  ~6 requests per field.  Nothing here writes to any other directory than ``--out``.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
BENCH = Path(__file__).resolve().parent
RADIUS_ARCMIN = 6.0
NED_TAP_SYNC = "https://ned.ipac.caltech.edu/tap/sync"
NED_TAP_TABLES = "https://ned.ipac.caltech.edu/tap/tables"
SIMBAD_TABLES = ("https://simbad.cds.unistra.fr/simbad/sim-tap/tables", "https://simbad.harvard.edu/simbad/sim-tap/tables")
NED_COLUMNS = ("prefname", "ra", "dec", "uncmaja", "uncmina", "uncposa")
SIMBAD_BASIC_COLUMNS = ("coo_err_maj", "coo_err_min", "coo_err_angle", "coo_qual", "coo_wavelength", "coo_bibcode", "otype")
POSITION_MATCH_ARCSEC = 0.3
BATCH = 150  # names per request when the cone query of the NED table is refused


def load_module(path: Path, name: str):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fields(which: str = "all", fields_file: Path | None = None, only: str = "") -> dict[str, tuple[float, float]]:
    """The 26 fields: the nine of ``collect_deep_cosmos.FIELDS`` (read from its source without importing the collectors) and the 17 of ``deep_cosmos_fields_2.csv``."""
    out: dict[str, tuple[float, float]] = {}
    if which in ("first", "all"):
        for node in ast.parse((BENCH / "collect_deep_cosmos.py").read_text()).body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "FIELDS" for t in node.targets):
                out.update(ast.literal_eval(node.value))
    if which in ("second", "all"):
        t = pd.read_csv(fields_file or BENCH / "deep_cosmos_fields_2.csv")
        assert (t.r.astype(float) == RADIUS_ARCMIN).all(), "every field must have radius 6'"
        out.update({r.name: (float(r.ra), float(r.dec)) for r in t.itertuples()})
    if only:
        names = [n.strip() for n in only.replace(",", " ").split() if n.strip()]
        unknown = [n for n in names if n not in out]
        if unknown:
            raise SystemExit(f"not in the field list: {unknown}")
        out = {n: out[n] for n in names}
    return out


def tag(ra: float, dec: float, radius: float = RADIUS_ARCMIN) -> str:
    """The directory name the controller gives a cone (``Get_data/controller.py:_tag``)."""
    return load_module(V2 / "Get_data" / "controller.py", "dcl_controller")._tag(ra, dec, radius)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# schema probe
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def _columns_of(xml_text: str, table_suffix: str) -> dict[str, dict]:
    """{column name: {datatype, unit}} of the table whose name ends with ``table_suffix`` in a VOSI tableset document."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    cols: dict[str, dict] = {}
    for t in root.iter():
        if t.tag.split("}")[-1] != "table":
            continue
        name = next((c.text for c in t if c.tag.split("}")[-1] == "name"), "") or ""
        if name == table_suffix or name.endswith("." + table_suffix):
            for c in t:
                if c.tag.split("}")[-1] == "column":
                    d = {x.tag.split("}")[-1]: (x.text or "") for x in c}
                    cols[d.get("name", "")] = d
    return cols


def probe(out: Path, http_get=None) -> dict:
    """Read the two table lists; ``ok`` only when every column the collection needs is there."""
    import requests

    get = http_get or (lambda url: requests.get(url, timeout=(10, 60)))
    res = {"ned": {"url": NED_TAP_TABLES}, "simbad": {}, "ok": False}
    try:
        r = get(NED_TAP_TABLES)
        cols = _columns_of(r.text, "objdir")
        res["ned"].update(status=r.status_code, table="objdir", columns=sorted(cols), missing=[c for c in NED_COLUMNS if c not in cols],
                          units={c: cols[c].get("unit", "") for c in ("uncmaja", "uncmina", "uncposa") if c in cols})  # fmt: skip
    except Exception as exc:
        res["ned"].update(error=f"{type(exc).__name__}: {str(exc)[:160]}", missing=list(NED_COLUMNS))
    for url in SIMBAD_TABLES:
        try:
            r = get(url)
            if r.status_code != 200:
                res["simbad"][url] = {"status": r.status_code}
                continue
            basic, alltypes = _columns_of(r.text, "basic"), _columns_of(r.text, "alltypes")
            res["simbad"][url] = {"status": 200, "missing_basic": [c for c in SIMBAD_BASIC_COLUMNS if c not in basic], "alltypes_has_otypes": "otypes" in alltypes,
                                  "units": {c: basic[c].get("unit", "") for c in ("coo_err_maj", "coo_err_min") if c in basic}}  # fmt: skip
        except Exception as exc:
            res["simbad"][url] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    s_ok = any(v.get("status") == 200 and not v["missing_basic"] and v["alltypes_has_otypes"] and all(u == "mas" for u in v["units"].values()) for v in res["simbad"].values())
    res["ok"] = bool(s_ok and not res["ned"].get("missing") and all(u in ("arcsec", "deg") for u in res["ned"].get("units", {}).values()) and res["ned"].get("units"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "schema_probe.json").write_text(json.dumps(res, indent=1))
    return res


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# SIMBAD extra columns
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def simbad_extra_adql(c_ra: float, c_dec: float, r_deg: float) -> str:
    return (
        'SELECT b.main_id, b.coo_qual, a.otypes FROM basic AS b LEFT JOIN alltypes AS a ON a.oidref = b.oid '
        f"WHERE CONTAINS(POINT('ICRS', b.ra, b.dec), CIRCLE('ICRS', {c_ra}, {c_dec}, {r_deg})) = 1"
    )


def simbad_with_extras(sm, ra: float, dec: float, radius: float, tap=None) -> pd.DataFrame:
    """The normal collector's rows plus ``coo_qual`` and ``otypes`` (one more request).  ``tap(server, adql) -> (table, overflow)`` is injectable for the tests."""
    df = sm.fetch(ra, dec, radius)
    if not len(df):
        df["coo_qual"], df["otypes"] = pd.Series(dtype=object), pd.Series(dtype=object)
        return df
    c_ra, c_dec, r_deg = sm._cone_numbers(ra, dec, radius)
    tap = tap or sm._tap_sync
    extra = None
    for server in sm._ordered_servers():
        try:
            table, overflow = tap(server, simbad_extra_adql(c_ra, c_dec, r_deg))
            if overflow:
                raise RuntimeError("SIMBAD cone has more objects than the row limit")
            extra = table.to_pandas()
            break
        except Exception as exc:  # server failed: its mirror; the extras stay empty when both fail (noted in the state file)
            print(f"[simbad extras] {server}: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
    if extra is None or "main_id" not in extra:
        df["coo_qual"], df["otypes"] = np.nan, np.nan
        df.attrs["extras"] = "failed"
        return df
    extra = extra.drop_duplicates("main_id").set_index("main_id")
    key = df["catalog_object_id"].astype(str).str.strip() if "catalog_object_id" in df else df["main_id"].astype(str).str.strip()
    df["coo_qual"] = key.map(extra["coo_qual"].astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "--": np.nan}))
    df["otypes"] = key.map(extra["otypes"].astype(str).str.strip().replace({"": np.nan, "nan": np.nan}))
    df.attrs["extras"] = "ok"
    return df


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# NED uncertainty ellipse
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def _ned_tap(adql: str) -> pd.DataFrame:
    import requests
    from astropy.io.votable import parse

    resp = requests.post(NED_TAP_SYNC, data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": adql}, timeout=(10, 120))
    resp.raise_for_status()
    vot = parse(io.BytesIO(resp.content))
    for r in vot.resources:  # a TAP error comes as a VOTable with QUERY_STATUS=ERROR
        for i in r.infos:
            if str(i.name) == "QUERY_STATUS" and str(i.value) == "ERROR":
                raise RuntimeError(str(i.content or "NED TAP error")[:200])
    return vot.get_first_table().to_table(use_names_over_ids=True).to_pandas()


def norm_name(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip()).upper()


def ned_cone_adql(ra: float, dec: float, radius_arcmin: float) -> str:
    return (
        f"SELECT {', '.join(NED_COLUMNS)} FROM NEDTAP.objdir "
        f"WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.9f}, {dec:.8f}, {radius_arcmin / 60.0:.9f})) = 1"
    )


def ned_names_adql(names: list[str]) -> str:
    q = ", ".join("'" + n.replace("'", "''") + "'" for n in names)
    return f"SELECT {', '.join(NED_COLUMNS)} FROM NEDTAP.objdir WHERE prefname IN ({q})"


def ned_uncertainties(rows: pd.DataFrame, ra: float, dec: float, radius_arcmin: float, tap=None) -> tuple[pd.DataFrame, dict]:
    """The NED cone rows with ``ned_unc_maj_arcsec``, ``ned_unc_min_arcsec``, ``ned_unc_pa_deg`` and ``ned_unc_source`` (``name`` / ``position`` / empty).

    The cone query of the table is tried first (one request); when NED refuses it (view without a position index, a rejected predicate) the names of the cone rows go in batches of
    ``BATCH`` (``prefname IN (...)``).  ``tap(adql) -> DataFrame`` is injectable for the tests."""
    tap = tap or _ned_tap
    state = {"method": "cone", "requests": 0, "tap_rows": 0}
    rows = rows.copy()
    for c in ("ned_unc_maj_arcsec", "ned_unc_min_arcsec", "ned_unc_pa_deg"):
        rows[c] = np.nan
    rows["ned_unc_source"] = ""
    if not len(rows):
        return rows, state
    try:
        state["requests"] += 1
        t = tap(ned_cone_adql(ra, dec, radius_arcmin))
    except Exception as exc:
        print(f"[ned tap] cone query refused ({type(exc).__name__}: {str(exc)[:120]}); names in batches", flush=True)
        state["method"] = "names"
        names = [str(n) for n in rows["object_name"].dropna().unique()]
        parts = []
        for i in range(0, len(names), BATCH):
            state["requests"] += 1
            parts.append(tap(ned_names_adql(names[i : i + BATCH])))
        t = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=list(NED_COLUMNS))
    t = t.rename(columns=str.lower)
    state["tap_rows"] = int(len(t))
    by_name = {norm_name(r.prefname): r for r in t.itertuples()}
    cosd = max(np.cos(np.radians(dec)), 1e-6)
    tra, tde = pd.to_numeric(t.get("ra"), errors="coerce").to_numpy(float), pd.to_numeric(t.get("dec"), errors="coerce").to_numpy(float)
    for i, r in rows.iterrows():
        hit, how = by_name.get(norm_name(r.get("object_name", ""))), "name"
        if hit is None and len(t):
            d = np.hypot((tra - float(r["ra"])) * cosd, tde - float(r["dec"])) * 3600.0
            j = int(np.nanargmin(d)) if np.isfinite(d).any() else -1
            if j >= 0 and d[j] <= POSITION_MATCH_ARCSEC:
                hit, how = t.iloc[j], "position"
                hit = type("Hit", (), {k: hit[k] for k in ("uncmaja", "uncmina", "uncposa")})()
        if hit is not None:
            rows.at[i, "ned_unc_maj_arcsec"], rows.at[i, "ned_unc_min_arcsec"], rows.at[i, "ned_unc_pa_deg"] = (float(getattr(hit, k)) if getattr(hit, k) is not None else np.nan for k in ("uncmaja", "uncmina", "uncposa"))
            rows.at[i, "ned_unc_source"] = how
    state["rows"] = int(len(rows))
    state["with_uncertainty"] = int(rows.ned_unc_maj_arcsec.notna().sum())
    state["matched_by_name"] = int((rows.ned_unc_source == "name").sum())
    state["matched_by_position"] = int((rows.ned_unc_source == "position").sum())
    return rows, state


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def collect_field(name: str, ra: float, dec: float, out: Path, sm=None, nd=None, tap_simbad=None, tap_ned=None) -> dict:
    """``out/<name>/{simbad_<tag>.csv, ned_<tag>.csv, literature_state.json}``.  A finished field (its state file says ok) is not collected again."""
    fdir = out / name
    state_file = fdir / "literature_state.json"
    if state_file.exists() and json.loads(state_file.read_text()).get("ok"):
        return json.loads(state_file.read_text())
    sm = sm or load_module(V2 / "Get_data" / "simbad.py", "dcl_simbad")
    nd = nd or load_module(V2 / "Get_data" / "ned.py", "dcl_ned")
    t = tag(ra, dec)
    fdir.mkdir(parents=True, exist_ok=True)
    state = {"field": name, "ra": ra, "dec": dec, "radius_arcmin": RADIUS_ARCMIN, "tag": t, "ok": False}
    s = simbad_with_extras(sm, ra, dec, RADIUS_ARCMIN, tap=tap_simbad)
    s.to_csv(fdir / f"simbad_{t}.csv", index=False)
    state["simbad_rows"], state["simbad_extras"] = int(len(s)), s.attrs.get("extras", "empty")
    state["simbad_coo_err_maj_filled"] = int(pd.to_numeric(s.get("coo_err_maj"), errors="coerce").notna().sum()) if len(s) else 0
    state["simbad_coo_qual_filled"] = int(s["coo_qual"].notna().sum()) if "coo_qual" in s else 0
    n = nd.fetch(ra, dec, RADIUS_ARCMIN)
    n, ned_state = ned_uncertainties(n, ra, dec, RADIUS_ARCMIN, tap=tap_ned)
    n.to_csv(fdir / f"ned_{t}.csv", index=False)
    state["ned_rows"], state["ned_tap"] = int(len(n)), ned_state
    state["ok"] = state["simbad_extras"] in ("ok", "empty") and (state["ned_rows"] == 0 or ned_state["with_uncertainty"] > 0)
    state_file.write_text(json.dumps(state, indent=1))
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["probe", "collect"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--set", default="all", choices=["first", "second", "all"])
    ap.add_argument("--fields", default="", help="comma or space separated field names (default: every field of the set)")
    ap.add_argument("--fields-file", type=Path, default=None)
    a = ap.parse_args()
    sys.path.insert(0, str(BENCH))
    import run_info as RI

    t0 = RI.start()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.action == "probe":
        res = probe(a.out)
        print(json.dumps(res, indent=1))
        RI.write(a.out, [], t0=t0, status="ok" if res["ok"] else "failed", note="schema probe of NED TAP objdir and SIMBAD basic / alltypes")
        return 0 if res["ok"] else 3
    load_module(V2 / "Get_data" / "throttle.py", "dcl_throttle").install()  # 3-5 s before every request (also the direct ``requests`` of this script)
    states, failed = [], False
    flds = fields(a.set, a.fields_file, a.fields)
    RI.write(a.out, [], t0=t0, status="running", note=f"literature rows of {len(flds)} deep COSMOS fields")
    for name, (ra, dec) in flds.items():
        st = collect_field(name, ra, dec, a.out)
        states.append(st)
        failed |= not st["ok"]
        print(json.dumps({k: v for k, v in st.items() if k != "ned_tap"}), flush=True)
    (a.out / "collection_state.json").write_text(json.dumps(states, indent=1))
    RI.write(a.out, [], t0=t0, status="failed" if failed else "ok", note=f"literature rows of {len(flds)} deep COSMOS fields")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
