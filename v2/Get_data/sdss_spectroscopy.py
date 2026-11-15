"""SDSS DR18 spectroscopy metadata collector. Spectra can be downloaded later by specobjid.

Galaxy spectra also get emission-line fluxes / equivalent widths and the 4000 A
break, used by the BPT / WHAN / Dn4000 rules of Classifier/subclass.py:

* Portsmouth emission-line fits (emissionLinesPort; Thomas et al. 2013),
  which cover SDSS-I/II and BOSS spectra (100 % of the benchmark galaxies);
* MPA-JHU (galSpecLine / galSpecIndx; Brinchmann et al. 2004, Kauffmann et
  al. 2003) for Dn4000, and for the lines when Portsmouth has none.  These
  cover SDSS-I/II spectra only (1.6 % of the benchmark galaxies).

Equivalent widths are stored positive in emission.  A failed line query leaves
the columns empty; it never drops the spectra.
"""

from pathlib import Path
import pandas as pd

CATALOG = "SDSS DR18 spectroscopy"
FIELDS = [
    "specobjid",
    "bestobjid",
    "ra",
    "dec",
    "plate",
    "mjd",
    "fiberid",
    "class",
    "subclass",
    "z",
    "zerr",
    "zwarning",
]
# generic name: (Portsmouth column, MPA-JHU column)
LINES = {
    "line_ha_flux": ("Flux_Ha_6562", "h_alpha_flux"),
    "line_ha_flux_err": ("Flux_Ha_6562_Err", "h_alpha_flux_err"),
    "line_hb_flux": ("Flux_Hb_4861", "h_beta_flux"),
    "line_hb_flux_err": ("Flux_Hb_4861_Err", "h_beta_flux_err"),
    "line_oiii5007_flux": ("Flux_OIII_5006", "oiii_5007_flux"),
    "line_oiii5007_flux_err": ("Flux_OIII_5006_Err", "oiii_5007_flux_err"),
    "line_nii6584_flux": ("Flux_NII_6583", "nii_6584_flux"),
    "line_nii6584_flux_err": ("Flux_NII_6583_Err", "nii_6584_flux_err"),
    "line_ha_ew": ("EW_Ha_6562", "h_alpha_eqw"),
    "line_nii6584_ew": ("EW_NII_6583", "nii_6584_eqw"),
    # 1-sigma EW errors (2.53.0: WHAN with errors, Classifier/subclass.py)
    "line_ha_ew_err": ("EW_Ha_6562_Err", "h_alpha_eqw_err"),
    "line_nii6584_ew_err": ("EW_NII_6583_Err", "nii_6584_eqw_err"),
}
# Queried without the EW errors if a release lacks them (the line fluxes and
# EWs must not be lost for two optional columns).
EW_ERR = ("line_ha_ew_err", "line_nii6584_ew_err")
LINE_FIELDS = [*LINES, "line_source", "port_bpt", "d4000_n"]
def _port_sql(lines):
    return "SELECT specObjID,BPT," + ",".join(p for p, _ in lines.values()) + " FROM emissionLinesPort WHERE specObjID IN ({ids})"


def _mpa_sql(lines):
    return (
        "SELECT l.specObjID," + ",".join("l." + m for _, m in lines.values()) + ",i.d4000_n FROM galSpecLine AS l "
        "LEFT JOIN galSpecIndx AS i ON i.specObjID=l.specObjID WHERE l.specObjID IN ({ids})"
    )


LINES_NO_ERR = {k: v for k, v in LINES.items() if k not in EW_ERR}
PORT_SQL, MPA_SQL = _port_sql(LINES), _mpa_sql(LINES)


def _sql(template: str, ids: list[str]) -> pd.DataFrame:
    from astroquery.sdss import SDSS

    parts = []
    for s in range(0, len(ids), 80):  # SkyServer answers 404 to over-long GET queries
        t = SDSS.query_sql(template.format(ids=",".join(ids[s : s + 80])), data_release=18)
        if t is not None and len(t):
            parts.append(t.to_pandas())
    if not parts:
        return pd.DataFrame(columns=["specobjid"])
    out = pd.concat(parts, ignore_index=True)
    out.columns = [c.lower() for c in out.columns]
    out["specobjid"] = out["specobjid"].astype("uint64").astype(str)
    return out.drop_duplicates("specobjid")


def _sql_with_fallback(template: str, fallback: str, ids: list[str]) -> pd.DataFrame:
    """The query with the EW-error columns; without them if that one fails."""
    try:
        return _sql(template, ids)
    except Exception as exc:
        print(f"[sdss_spectroscopy] retry without EW errors ({type(exc).__name__}: {str(exc)[:80]})")
        return _sql(fallback, ids)


def _clean(v: pd.Series) -> pd.Series:
    v = pd.to_numeric(v, errors="coerce")
    return v.where((v.abs() < 1e6) & (v > -999))  # -9999 / -999 and 1e38 fill values


def _lines(ids: list[str]) -> pd.DataFrame:
    out = pd.DataFrame({"specobjid": ids})
    status = "ok"  # recorded so the archive cache skips partial results
    try:
        port = _sql_with_fallback(PORT_SQL, _port_sql(LINES_NO_ERR), ids)
    except Exception as exc:
        print(f"[sdss_spectroscopy] Portsmouth line query failed: {type(exc).__name__}: {str(exc)[:120]}")
        port = pd.DataFrame(columns=["specobjid"])
        status = "error:portsmouth"
    try:
        mpa = _sql_with_fallback(MPA_SQL, _mpa_sql(LINES_NO_ERR), ids)
    except Exception as exc:
        print(f"[sdss_spectroscopy] MPA-JHU line query failed: {type(exc).__name__}: {str(exc)[:120]}")
        mpa = pd.DataFrame(columns=["specobjid"])
        status = "error:mpa_jhu"
    out = out.merge(port, on="specobjid", how="left").merge(mpa, on="specobjid", how="left", suffixes=("", "_mpa"))
    has_port = pd.Series(False, index=out.index)
    for g, (p, m) in LINES.items():
        pv = _clean(out[p.lower()]) if p.lower() in out else pd.Series(float("nan"), index=out.index)
        mv = _clean(out[m]) if m in out else pd.Series(float("nan"), index=out.index)
        if g.endswith("_ew"):
            mv = -mv  # MPA-JHU: negative in emission
        has_port |= pv.notna()
        out[g] = pv.where(pv.notna(), mv)
    out["line_source"] = pd.Series("Portsmouth", index=out.index).where(
        has_port, pd.Series("MPA-JHU", index=out.index).where(out["line_ha_flux"].notna())
    )
    out["port_bpt"] = out["bpt"] if "bpt" in out else pd.NA
    out["d4000_n"] = _clean(out["d4000_n"]) if "d4000_n" in out else pd.NA
    out["line_query_status"] = status
    return out[["specobjid", *LINE_FIELDS, "line_query_status"]]


def fetch(ra: float, dec: float, radius_arcmin: float) -> pd.DataFrame:
    from _catalog_utils import sdss_region, unique_positions

    t = sdss_region(ra, dec, radius_arcmin, spectro=True, specobj_fields=FIELDS, data_release=18)
    if t is None:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", *FIELDS, *LINE_FIELDS])
    df = t.to_pandas()
    df["specobjid"] = df["specobjid"].astype("uint64").astype(str)
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df["specobjid"])
    df.insert(2, "object_name", "SDSS spectrum " + df["specobjid"])
    df = df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)
    # Repeat spectra of one target (SDSS-I/II + BOSS re-observations) are one
    # object: keep a zwarning == 0 spectrum, the smallest-zerr one first, as
    # for LAMOST (2026-10-21).  1" is inside the 2-3" fibres.
    zw = pd.to_numeric(df["zwarning"], errors="coerce").fillna(1).eq(0) if "zwarning" in df else pd.Series(True, index=df.index)
    ze = pd.to_numeric(df["zerr"], errors="coerce").abs() if "zerr" in df else pd.Series(0.0, index=df.index)
    df = unique_positions(df, 1.0, zw.astype(float) - ze.fillna(1.0).clip(0, 0.99)).reset_index(drop=True)
    gal = df.loc[df["class"].astype(str).str.strip().str.upper().eq("GALAXY"), "specobjid"].tolist()
    lines = _lines(gal) if gal else pd.DataFrame(columns=["specobjid", *LINE_FIELDS])
    return df.merge(lines, on="specobjid", how="left")


def save(df, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)
