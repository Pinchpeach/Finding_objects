"""Independent checks of the 2.22.0 target rules (run from GitHub Actions).

HOT_SUBDWARF  (Classifier/axes/physical.py hot_subdwarf_evidence)
  completeness: Culpan+2022 catalogue of *known* (spectroscopically
    classified) hot subdwarfs, J/A+A/662/A40, with Gaia DR3 astrometry;
    fraction selected among those with parallax_over_error > 5.
  purity: random Gaia DR3 sample passing the rule (sky-random via
    random_index) cross-matched to SIMBAD; object types and spectral types of
    the matched ones are tallied (hot subdwarf / WD / MS A-B / cooler).
ULTRACOOL_DWARF  (ultracool_evidence)
  Best+2018 (J/ApJS/234/1) spectroscopic M/L/T dwarfs matched (5") to the
  Gaia DR3 ESP-UCD candidates: per adopted spectral type, the fraction the
  rule selects, and the spectral-type distribution of the selected ones.
Writes CSV / JSON summaries into --out.
"""
from __future__ import annotations
import argparse, importlib.util, json, sys, traceback
from pathlib import Path
import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("phys_truth", V2 / "Classifier" / "axes" / "physical.py")
PHYS = importlib.util.module_from_spec(spec); spec.loader.exec_module(PHYS)
GAIA_COLS = "source_id, ra, dec, parallax, parallax_error, phot_g_mean_mag, bp_rp, phot_bp_rp_excess_factor, pmra, pmdec"


def gaia_job(q):
    from astroquery.gaia import Gaia
    Gaia.ROW_LIMIT = -1
    return Gaia.launch_job_async(q).get_results().to_pandas()


def gaia_by_ids(ids):
    from astroquery.gaia import Gaia
    from astropy.table import Table
    t = Table({"sid": np.asarray(ids, dtype=np.int64)})
    q = (f"SELECT g.source_id, g.ra, g.dec, g.parallax, g.parallax_error, g.phot_g_mean_mag, g.bp_rp, "
         f"g.phot_bp_rp_excess_factor FROM gaiadr3.gaia_source AS g JOIN tap_upload.ids AS u ON g.source_id = u.sid")
    return Gaia.launch_job_async(q, upload_resource=t, upload_table_name="ids").get_results().to_pandas()


def rows_pass(df, fn):
    keep = []
    for r in df.to_dict("records"):
        keep.append(fn({f"gaia_dr3__{k}": v for k, v in r.items()}) is not None)
    return np.array(keep, dtype=bool)


def hot_subdwarfs(out, say):
    from astroquery.vizier import Vizier
    cats = Vizier(columns=["**"], row_limit=-1).get_catalogs("J/A+A/662/A40")
    say("J/A+A/662/A40 tables:", {k: (len(cats[k]), cats[k].colnames[:30]) for k in cats.keys()})
    key = next((k for k in cats.keys() if "known" in k.lower()), None)
    if key is None:
        say("no known-hot-subdwarf table found"); return
    k = cats[key].to_pandas()
    sid = next((c for c in k.columns if c.lower() in ("gaiaedr3", "source", "source_id", "gaia", "edr3")), None)
    say("known table", key, len(k), "id column", sid, "class columns", [c for c in k.columns if "cl" in c.lower() or "sp" in c.lower()])
    if sid is None:
        return
    k = k.dropna(subset=[sid]); k[sid] = pd.to_numeric(k[sid], errors="coerce"); k = k.dropna(subset=[sid])
    g = gaia_by_ids(k[sid].astype(np.int64).values)
    good = g[(g.parallax > 0) & (g.parallax / g.parallax_error > PHYS.HSD_MIN_PLX_SNR)].copy()
    good["selected"] = rows_pass(good, PHYS.hot_subdwarf_evidence)
    cls = next((c for c in k.columns if c.lower() in ("spclass", "sptype", "class", "spc")), None)
    if cls:
        good = good.merge(k[[sid, cls]].rename(columns={sid: "source_id", cls: "spclass"}).drop_duplicates("source_id"), on="source_id", how="left")
    good.to_csv(out / "hsd_known_selection.csv.gz", index=False)
    res = {"known_with_gaia": int(len(g)), "plx_snr_gt5": int(len(good)), "selected": int(good.selected.sum()),
           "completeness": round(float(good.selected.mean()), 4) if len(good) else None}
    if cls:
        res["completeness_by_class"] = good.groupby(good.spclass.astype(str).str.strip().str[:4])["selected"].agg(["size", "mean"]).round(3).query("size >= 20").to_dict("index")
    say("HSD completeness", res)

    # purity: rule applied in ADQL (Culpan Table 1 criteria 1-4) on a sky-random subset
    q = (f"SELECT TOP 4000 {GAIA_COLS} FROM gaiadr3.gaia_source WHERE parallax > 0 AND parallax_over_error > 5 "
         "AND bp_rp BETWEEN -0.7 AND 0.7 AND phot_g_mean_mag + 5*LOG10(parallax) - 10 BETWEEN -5 AND 7 "
         "AND phot_g_mean_mag + 5*LOG10(parallax) - 10 > 17.7*POWER(bp_rp,3) - 6.9*POWER(bp_rp,2) + 7.35*bp_rp + 1.95 "
         "AND random_index < 400000000 ORDER BY random_index")
    s = gaia_job(q)
    s["selected"] = rows_pass(s, PHYS.hot_subdwarf_evidence)
    s = s[s.selected]
    say("purity sample after the full rule (C* cut):", len(s))
    from astroquery.simbad import Simbad
    from astropy.table import Table
    t = Table({"gid": ["Gaia DR3 " + str(int(x)) for x in s.source_id]})
    sim = Simbad().query_tap("SELECT i.id AS gid, b.otype, b.sp_type FROM ident AS i JOIN basic AS b ON b.oid = i.oidref "
                             "JOIN TAP_UPLOAD.ids AS u ON i.id = u.gid", ids=t).to_pandas()
    sim.to_csv(out / "hsd_purity_simbad.csv", index=False)
    sp = sim.sp_type.astype(str).str.strip()
    def bucket(o, s_):
        s_ = s_ if s_ not in ("", "nan", "None") else ""
        if o in ("HS*",) or s_.lower().startswith(("sd", "he-sd")):
            return "hot_subdwarf"
        if o in ("WD*", "WD?") or s_.startswith("D"):
            return "white_dwarf"
        if o in ("HB*", "BH*") or "HB" in s_:
            return "horizontal_branch"
        if s_[:1] in ("O", "B", "A"):
            return "OBA_type"
        if s_[:1] in ("F", "G", "K", "M"):
            return "cooler_FGKM"
        if o in ("CV*", "No*", "PN"):
            return "CV_or_PN"
        return "no_type_info"
    sim["bucket"] = [bucket(o, x) for o, x in zip(sim.otype.astype(str), sp)]
    pur = {"sample": int(len(s)), "in_simbad": int(len(sim)), "buckets": sim.bucket.value_counts().to_dict(),
           "otypes": sim.otype.astype(str).value_counts().head(15).to_dict()}
    say("HSD purity", pur)
    json.dump({"completeness": res, "purity": pur}, open(out / "hsd_summary.json", "w"), indent=1, default=str)


def ultracool(out, say):
    from astroquery.vizier import Vizier
    b = Vizier(columns=["Name", "SpT", "Type", "RAJ2000", "DEJ2000", "_RAJ2000", "_DEJ2000", "Binary", "Young"], row_limit=-1).get_catalogs("J/ApJS/234/1/dwarfs")[0].to_pandas()
    say("Best+2018", len(b), list(b.columns))
    ra = pd.to_numeric(b.get("_RAJ2000", b.get("RAJ2000")), errors="coerce"); de = pd.to_numeric(b.get("_DEJ2000", b.get("DEJ2000")), errors="coerce")
    b = b.assign(ra=ra, dec=de).dropna(subset=["ra", "dec"])
    u = gaia_job("SELECT a.source_id, a.teff_espucd, a.flags_espucd, g.ra, g.dec, g.pmra, g.pmdec FROM gaiadr3.astrophysical_parameters AS a "
                 "JOIN gaiadr3.gaia_source AS g ON g.source_id = a.source_id WHERE a.teff_espucd IS NOT NULL")
    say("ESP-UCD rows", len(u), "flags", u.flags_espucd.astype(str).value_counts().head(12).to_dict())
    from astropy.coordinates import SkyCoord
    import astropy.units as un
    cb = SkyCoord(b.ra.values * un.deg, b.dec.values * un.deg)
    cu = SkyCoord(u.ra.values * un.deg, u.dec.values * un.deg)
    idx, d2, _ = cb.match_to_catalog_sky(cu)
    b["ucd_match"] = d2.arcsec < 5.0
    b["teff_espucd"] = np.where(b.ucd_match, u.teff_espucd.values[idx], np.nan)
    b["flags_espucd"] = np.where(b.ucd_match, u.flags_espucd.astype(str).values[idx], None)
    b["selected"] = [PHYS.ultracool_evidence({"gaia_dr3__teff_espucd": t, "gaia_dr3__flags_espucd": f}) is not None
                     for t, f in zip(b.teff_espucd, b.flags_espucd)]
    b["Type"] = pd.to_numeric(b["Type"], errors="coerce")
    b.to_csv(out / "ucd_best2018_match.csv.gz", index=False)
    by = b.groupby(np.floor(b.Type)).agg(n=("selected", "size"), matched=("ucd_match", "mean"), selected=("selected", "mean")).round(3)
    sel = b[b.selected]
    res = {"best_rows": int(len(b)), "matched_espucd": int(b.ucd_match.sum()), "selected": int(len(sel)),
           "selected_type_ge_M7": round(float((sel.Type >= 7).mean()), 4) if len(sel) else None,
           "by_numeric_type": by.to_dict("index")}
    say("UCD", res)
    json.dump(res, open(out / "ucd_summary.json", "w"), indent=1, default=str)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log = open(out / "build_log.txt", "w", encoding="utf-8")
    def say(*x):
        print(*x, flush=True); print(*x, file=log, flush=True)
    for name, fn in (("hot_subdwarfs", hot_subdwarfs), ("ultracool", ultracool)):
        try:
            fn(out, say)
        except Exception:
            say(name, "ERROR", traceback.format_exc()[-2000:])
    log.close()


if __name__ == "__main__":
    sys.exit(main())
