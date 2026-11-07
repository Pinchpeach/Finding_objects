#!/usr/bin/env python3
"""Reference objects of confirmed nature, per class and sub-class (2.46.1).

For every class and sub-class the classifier can report, a sample of objects
whose nature is settled in the literature: spectroscopic classifications,
expert visual classifications, or catalogues compiled from published
identifications.  Each row gives the object's name (catalogue designation),
its type and the paper the identification comes from.

Sources are of two kinds:

* local truth files already in this repository (built from the cited
  catalogues by earlier workflows);
* VizieR catalogues of the cited papers (fetched here; the cloud session
  cannot reach VizieR, so this runs on GitHub Actions).

Only entries the source itself marks as certain are kept (e.g. ASAS-SN class
probability > 0.95, Abell richness class >= 1, no ':' uncertainty flags).
Up to PER_TYPE objects per type are drawn at random (seed 1); a type with
fewer than MIN_TYPE certain objects is reported, not padded.

    python v2/benchmark/build_reference_objects.py [--only KEY ...]

Output: v2/reference_objects/reference_objects.csv.gz and SUMMARY.md
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parent
V2 = BENCH.parent
OUT = V2 / "reference_objects"
PER_TYPE = 300
MIN_TYPE = 100
SEED = 1

# --------------------------------------------------------------------------
# Papers (short citation, bibcode)
# --------------------------------------------------------------------------
P = {
    "sdss18": ("Almeida et al. 2023, ApJS 267, 44 (SDSS DR18); classes by Bolton et al. 2012, AJ 144, 144", "2023ApJS..267...44A"),
    "bpt": ("Bolton et al. 2012, AJ 144, 144 (SDSS spectral sub-class from BPT, Brinchmann et al. 2004)", "2012AJ....144..144B"),
    "guo22": ("Guo et al. 2022, MNRAS 509, 2674 (LAMOST DR5 white dwarfs, visual spectral types)", "2022MNRAS.509.2674G"),
    "suh21": ("Suh 2021, ApJS 256, 43 (catalogue of AGB stars, C-rich / O-rich from IR spectra and photometry)", "2021ApJS..256...43S"),
    "asassn": ("Jayasinghe et al. 2019-2021 (ASAS-SN variable stars; VizieR II/366, Christy et al. 2023)", "2021MNRAS.503..200J"),
    "atnf": ("Manchester et al. 2005, AJ 129, 1993 (ATNF pulsar catalogue)", "2005AJ....129.1993M"),
    "apogee": ("Abdurro'uf et al. 2022, ApJS 259, 35 (SDSS DR17 APOGEE spectroscopic parameters)", "2022ApJS..259...35A"),
    "dr16q": ("Lyke et al. 2020, ApJS 250, 8 (SDSS DR16 quasar catalogue)", "2020ApJS..250....8L"),
    "vv10": ("Véron-Cetty & Véron 2010, A&A 518, A10 (quasars and active nuclei, 13th ed.)", "2010A&A...518A..10V"),
    "bzcat": ("Massaro et al. 2015, Ap&SS 357, 75 (Roma-BZCAT 5th edition)", "2015Ap&SS.357...75M"),
    "nair": ("Nair & Abraham 2010, ApJS 186, 427 (visual morphologies of 14,034 SDSS galaxies)", "2010ApJS..186..427N"),
    "arp": ("Arp 1966, ApJS 14, 1 (Atlas of Peculiar Galaxies)", "1966ApJS...14....1A"),
    "geier17": ("Geier et al. 2017, A&A 600, A50 (catalogue of known hot subdwarf stars)", "2017A&A...600A..50G"),
    "kirk21": ("Kirkpatrick et al. 2021, ApJS 253, 7 (20 pc census of L, T, Y dwarfs)", "2021ApJS..253....7K"),
    "esplin19": ("Esplin & Luhman 2019, AJ 158, 54 (spectroscopic members of Taurus)", "2019AJ....158...54E"),
    "acker92": ("Acker et al. 1992 (Strasbourg-ESO Catalogue of Galactic Planetary Nebulae; VizieR V/84)", "1992secg.book.....A"),
    "asiago": ("Barbon et al. 1999, A&AS 139, 531 (Asiago Supernova Catalogue, updated; VizieR B/sn)", "1999A&AS..139..531B"),
    "rk03": ("Ritter & Kolb 2003, A&A 404, 301 (catalogue of CVs, LMXBs and related objects, final ed. 7.24)", "2003A&A...404..301R"),
    "liu06": ("Liu, van Paradijs & van den Heuvel 2006, A&A 455, 1165 (catalogue of high-mass X-ray binaries)", "2006A&A...455.1165L"),
    "gcvs": ("Samus et al. 2017, Astron. Rep. 61, 80 (General Catalogue of Variable Stars, GCVS 5.1)", "2017ARep...61...80S"),
    "abell89": ("Abell, Corwin & Olowin 1989, ApJS 70, 1 (rich clusters of galaxies)", "1989ApJS...70....1A"),
}

# coarse class of each type (STAR / GALAXY / QSO / other)
COARSE = {}


def take(df: pd.DataFrame, key: str, typ: str, coarse: str, paper: str, name, ra, dec, catalog: str) -> pd.DataFrame:
    df = df.copy()
    name = df[name] if isinstance(name, str) else name(df)
    out = pd.DataFrame(
        {
            "name": name.astype(str).str.strip(),
            "type": typ,
            "coarse_class": coarse,
            "source": P[paper][0],
            "bibcode": P[paper][1],
            "catalog": catalog,
            "ra": pd.to_numeric(df[ra], errors="coerce") if isinstance(ra, str) else ra,
            "dec": pd.to_numeric(df[dec], errors="coerce") if isinstance(dec, str) else dec,
        }
    )
    out = out[out.name.ne("") & out.name.ne("nan")].drop_duplicates("name")
    n = len(out)
    out = out.sample(min(n, PER_TYPE), random_state=SEED) if n else out
    print(f"  {key:>14s} {typ:<28s} available {n:6d} -> {len(out)}" + ("   ** fewer than %d" % MIN_TYPE if len(out) < MIN_TYPE else ""), flush=True)
    return out


# --------------------------------------------------------------------------
# Local truth files
# --------------------------------------------------------------------------
def local_sources():
    parts = []
    gt = pd.read_csv(BENCH / "truth_data" / "ground_truth.csv", low_memory=False)
    zw = pd.to_numeric(gt.get("zwarning", 0), errors="coerce").fillna(0) if "zwarning" in gt else 0
    gt = gt[np.asarray(zw == 0)] if not np.isscalar(zw) else gt
    sdss = lambda d: "SDSS spec " + d.specobjid.astype("int64").astype(str)  # noqa: E731
    for cls in ("STAR", "GALAXY", "QSO"):
        parts.append(take(gt[gt["class"] == cls], "sdss18", cls, cls, "sdss18", sdss, "ra", "dec", "SDSS DR18 specObj"))
    sl = pd.read_csv(BENCH / "spectro_truth" / "sdss_galaxy_lines.csv.gz", low_memory=False)
    pos = gt.set_index("specobjid")[["ra", "dec"]]
    sl = sl.join(pos, on="specobjid")
    # (the SDSS AGN / BROADLINE sub-classes have < 100 objects here; Seyferts come from Veron-Cetty & Veron)
    for sub, typ in (("STARFORMING", "GALAXY_STAR_FORMING"), ("STARBURST", "GALAXY_STARBURST")):
        d = sl[sl.subclass.astype(str).str.strip().eq(sub)]
        parts.append(take(d, "bpt", typ, "GALAXY", "bpt", sdss, "ra", "dec", "SDSS DR18 specObj subclass"))
    wd = pd.read_csv(V2 / "Classifier" / "wd_subtype_truth.csv")
    for sub in ("DA", "DB"):
        parts.append(take(wd[wd.wd_subtype == sub], "guo22", f"WHITE_DWARF_{sub}", "STAR", "guo22", lambda d: "LAMOST " + d.external_id.astype(str), "ra", "dec", "J/MNRAS/509/2674"))
    agb = pd.read_csv(BENCH / "agb_truth" / "agb_chemistry_truth.csv.gz", low_memory=False)
    def nm(d):
        tm = d["suh_2MASS"].astype(str).str.strip().str.lstrip("J")
        wa = d["suh_WISEA"].astype(str).str.strip().str.lstrip("J")
        return ("2MASS J" + tm).where(d["suh_2MASS"].notna(), "WISEA J" + wa)

    for chem, typ in (("C", "AGB_CARBON_RICH"), ("O", "AGB_OXYGEN_RICH")):
        parts.append(take(agb[agb.chem == chem], "suh21", typ, "STAR", "suh21", nm, "ra", "dec", "J/ApJS/256/43"))
    var = pd.concat(
        [pd.read_csv(BENCH / "rr_ew_truth" / "asassn_ztf.csv.gz", low_memory=False), pd.read_csv(BENCH / "mira_truth" / "asassn_gaia_lpv.csv.gz", low_memory=False)],
        ignore_index=True,
    )
    var = var[pd.to_numeric(var.Prob, errors="coerce") > 0.95]
    for t, typ in (("RRAB", "RR_LYRAE_AB"), ("RRC", "RR_LYRAE_C"), ("EA", "ECLIPSING_ALGOL"), ("EW", "ECLIPSING_W_UMA"), ("M", "MIRA"), ("SR", "SEMIREGULAR_VARIABLE")):
        parts.append(take(var[var.Type == t], "asassn", typ, "STAR", "asassn", lambda d: "ASASSN-V " + d["ASASSN-V"].astype(str).str.replace("ASASSN-V", "").str.strip(), "ra", "dec", "II/366/catv2021"))
    psr = pd.read_csv(BENCH / "pulsar_truth" / "radio_sample.csv.gz", low_memory=False)
    parts.append(take(psr[psr.is_pulsar == 1], "atnf", "PULSAR", "STAR", "atnf", lambda d: "PSR " + d.name.astype(str).str.replace("PSR ", ""), "ra", "dec", "ATNF psrcat"))
    apo = pd.read_csv(BENCH / "bright_truth" / "apogee.csv.gz", low_memory=False)
    t, g, s = (pd.to_numeric(apo[c], errors="coerce") for c in ("apo_teff", "apo_logg", "apo_snr"))
    giant = apo[(g < 3.5) & (t < 5300) & (s >= 100)]
    parts.append(take(giant, "apogee", "RED_GIANT", "STAR", "apogee", lambda d: "2MASS J" + d.apo_id.astype(str).str.replace("^2M", "", regex=True), "ra", "dec", "APOGEE DR17 allStar"))
    return parts


# --------------------------------------------------------------------------
# VizieR catalogues
# --------------------------------------------------------------------------
def first_col(df, *cands):
    for c in cands:
        if c in df.columns:
            return c
    low = {c.lower(): c for c in df.columns}
    for c in cands:
        if c.lower() in low:
            return low[c.lower()]
    return None


def radec(df):
    ra = first_col(df, "RAJ2000", "_RAJ2000", "RA_ICRS", "RAdeg", "RA", "ra")
    de = first_col(df, "DEJ2000", "_DEJ2000", "DE_ICRS", "DEdeg", "DEC", "Dec", "dec")
    if ra is None or de is None:
        return pd.Series(np.nan, index=df.index), pd.Series(np.nan, index=df.index)
    r, d = df[ra], df[de]
    if r.dtype == object:  # sexagesimal
        from astropy.coordinates import SkyCoord
        import astropy.units as u

        c = SkyCoord(r.astype(str).values, d.astype(str).values, unit=(u.hourangle, u.deg))
        return pd.Series(c.ra.deg, index=df.index), pd.Series(c.dec.deg, index=df.index)
    return pd.to_numeric(r, errors="coerce"), pd.to_numeric(d, errors="coerce")


def fetch(catalog, filters=None, limit=20000, need=()):
    from astroquery.vizier import Vizier

    v = Vizier(columns=["**", "_RAJ2000", "_DEJ2000"], column_filters=filters or {}, row_limit=limit)
    for i in range(4):
        try:
            t = v.get_catalogs(catalog)
            break
        except Exception as exc:
            print(f"    {catalog}: attempt {i + 1} {type(exc).__name__}: {str(exc)[:150]}", flush=True)
            time.sleep(20 * (i + 1))
    else:
        return None
    if not len(t):
        print(f"    {catalog}: no table", flush=True)
        return None
    tabs = list(t)
    pick = next((x for x in tabs if not need or any(c in x.colnames for c in need)), None)
    if pick is None:
        print(f"    {catalog}: no table with {need}; tables {[x.colnames[:8] for x in tabs]}", flush=True)
        return None
    df = pick.to_pandas()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda x: x.decode() if isinstance(x, bytes) else x)
    print(f"    {catalog}: {len(df)} rows; columns {list(df.columns)[:40]}", flush=True)
    return df


def remote_sources(only=None):
    parts = []

    def want(k):
        return not only or k in only

    def add(key, df, typ, coarse, paper, namecol, catalog, mask=None):
        if df is None:
            print(f"  {key:>14s} {typ:<28s} FETCH FAILED", flush=True)
            return
        if mask is not None:
            df = df[mask(df)]
        ra, de = radec(df)
        nc = first_col(df, *namecol) if isinstance(namecol, (tuple, list)) else None
        if isinstance(namecol, (tuple, list)) and nc is None:
            print(f"  {key:>14s} {typ:<28s} no name column among {namecol}", flush=True)
            return
        name = df[nc] if nc else namecol(df)
        parts.append(take(df.assign(_n=name, _ra=ra, _de=de), key, typ, coarse, paper, "_n", "_ra", "_de", catalog))

    def col_has(df, cands, pattern, flags=0):
        c = first_col(df, *cands)
        if c is None:
            print(f"    no column among {cands}", flush=True)
            return pd.Series(False, index=df.index)
        return df[c].astype(str).str.strip().str.match(pattern, flags=flags)

    if want("dr16q"):
        d = fetch("VII/289/dr16q", limit=6000)
        add("dr16q", d, "QSO_SPECTROSCOPIC", "QSO", "dr16q", ("SDSS", "SDSSJ", "Name"), "VII/289", lambda d: pd.to_numeric(d[first_col(d, "z", "Z")], errors="coerce") > 0)
    if want("vv10"):
        # Veron-Cetty & Veron class A (AGN) with spectral type: S1.x = Seyfert 1, S2 = Seyfert 2, S3 = LINER
        for sp, typ in (("S1*", "SEYFERT_1"), ("=S2", "SEYFERT_2"), ("S3*", "LINER")):
            d = fetch("VII/258/vv10", {"Cl": "=A", "Sp": sp}, limit=20000, need=("Sp",))
            add("vv10", d, typ, "GALAXY", "vv10", ("Name",), "VII/258")
    if want("bzcat"):
        d = fetch("VII/274/bzcat5", limit=5000)
        if d is not None:
            add("bzcat", d, "BLAZAR_BL_LAC", "QSO", "bzcat", ("Name", "BZCAT5", "5BZCAT"), "VII/274", lambda d: col_has(d, ("Class", "Type"), r"^BL Lac$|^BZB", re.I) | col_has(d, ("Name", "BZCAT5"), r"^5BZB"))
            add("bzcat", d, "BLAZAR_FSRQ", "QSO", "bzcat", ("Name", "BZCAT5", "5BZCAT"), "VII/274", lambda d: col_has(d, ("Class", "Type"), r"^QSO RLoud flat|^BZQ", re.I) | col_has(d, ("Name", "BZCAT5"), r"^5BZQ"))
    if want("nair"):
        d = fetch("J/ApJS/186/427", limit=15000, need=("SDSS",))
        if d is not None:
            print("    Nair columns:", list(d.columns), flush=True)
        if d is not None:
            tt = lambda d: pd.to_numeric(d[first_col(d, "TType", "TT", "T", "ttype", "Ttype")], errors="coerce")  # noqa: E731
            nm = ("SDSS", "Name", "JID", "ID")
            add("nair", d, "GALAXY_ELLIPTICAL", "GALAXY", "nair", nm, "J/ApJS/186/427", lambda d: tt(d) <= -5)
            add("nair", d, "GALAXY_LENTICULAR", "GALAXY", "nair", nm, "J/ApJS/186/427", lambda d: tt(d).between(-3, 0))
            add("nair", d, "GALAXY_SPIRAL", "GALAXY", "nair", nm, "J/ApJS/186/427", lambda d: tt(d).between(1, 9))
    if want("arp"):
        d = fetch("VII/192/arplist", limit=1000)
        add("arp", d, "GALAXY_INTERACTING_PECULIAR", "GALAXY", "arp", lambda d: "Arp " + d[first_col(d, "Arp", "Seq", "No")].astype(str), "VII/192")
    if want("geier17"):
        d = fetch("J/A+A/600/A50", limit=6000, need=("SpClass",))
        if d is not None:
            sp = ("SpClass", "SpType", "Class")
            nm = ("Name", "ID", "Simbad")
            add("geier17", d, "HOT_SUBDWARF_SDB", "STAR", "geier17", nm, "J/A+A/600/A50", lambda d: col_has(d, sp, r"^sdB$"))
            add("geier17", d, "HOT_SUBDWARF_SDO", "STAR", "geier17", nm, "J/A+A/600/A50", lambda d: col_has(d, sp, r"^(sdO|He-sdO)$"))
            add("geier17", d, "HOT_SUBDWARF_SDOB", "STAR", "geier17", nm, "J/A+A/600/A50", lambda d: col_has(d, sp, r"^(sdOB|He-sdOB)$"))
    if want("kirk21"):
        d = fetch("J/ApJS/253/7", limit=3000, need=("SpTO", "SpTIR"))
        if d is not None:
            # Numeric types: L0 = 0, T0 = 10, Y0 = 20 (checked: SDSS 0000+2554 T4.5 -> 14.5,
            # 2MASS 0036+1821 L3.5 -> 3.5, WISE 0005+3737 T9 -> 19).  Adopted type SpAd; only
            # objects with a measured optical or near-IR spectral type (not photometric estimates).
            num = lambda c: pd.to_numeric(d[c], errors="coerce")  # noqa: E731
            spec = num("SpTO").notna() | num("SpTIR").notna()
            ad = num("SpAd")
            for lo, hi, typ in ((0, 10, "ULTRACOOL_L_DWARF"), (10, 20, "ULTRACOOL_T_DWARF"), (20, 30, "ULTRACOOL_Y_DWARF")):
                add("kirk21", d, typ, "STAR", "kirk21", ("Name",), "J/ApJS/253/7", lambda d, lo=lo, hi=hi: spec & (ad >= lo) & (ad < hi))
    if want("esplin19"):
        d = fetch("J/AJ/158/54/table1", limit=2000, need=("2MASS",))
        add("esplin19", d, "YSO_TAURUS_MEMBER", "STAR", "esplin19", lambda d: ("2MASS J" + d["2MASS"].astype(str).str.strip()).where(d["2MASS"].astype(str).str.strip().ne(""), d["Gaia"].astype(str)), "J/AJ/158/54")
    for t, typ in (("DCEP", "CEPHEID_CLASSICAL"), ("CWA", "CEPHEID_TYPE_II_CWA"), ("CWB", "CEPHEID_TYPE_II_CWB"), ("HADS", "DELTA_SCUTI_HADS"), ("DSCT", "DELTA_SCUTI"), ("EB", "ECLIPSING_BETA_LYR"), ("ROT", "ROTATIONAL_VARIABLE"), ("YSO", "YSO_VARIABLE")):
        if want("asassn"):
            d = fetch("II/366/catv2021", {"Type": f"={t}", "Prob": ">0.95"}, limit=3000)
            add("asassn", d, typ, "STAR", "asassn", ("ASASSN-V", "Name"), "II/366/catv2021")
    if want("acker92"):
        d = fetch("V/84/main", limit=2000)
        add("acker92", d, "PLANETARY_NEBULA", "STAR", "acker92", lambda d: "PN G" + d[first_col(d, "PNG", "PN")].astype(str), "V/84")
    if want("asiago"):
        d = fetch("B/sn/sncat", limit=20000)
        if d is not None:
            ty = ("Type", "SNType")
            nm = lambda d: "SN " + d[first_col(d, "SN", "Name")].astype(str)  # noqa: E731
            # position: the supernova's own (offset from the host), else the host
            add("asiago", d, "SUPERNOVA_IA", "OTHER", "asiago", nm, "B/sn", lambda d: col_has(d, ty, r"^Ia$"))
            add("asiago", d, "SUPERNOVA_II", "OTHER", "asiago", nm, "B/sn", lambda d: col_has(d, ty, r"^II(P|L|n|b)?$"))
            add("asiago", d, "SUPERNOVA_IB_IC", "OTHER", "asiago", nm, "B/sn", lambda d: col_has(d, ty, r"^I(b|c|b/c)$"))
    if want("rk03"):
        d = fetch("B/cb/cbdata", limit=2000)
        if d is not None:
            ty = ("Type1", "Type", "Typ1")
            add("rk03", d, "CATACLYSMIC_DWARF_NOVA", "STAR", "rk03", ("Name",), "B/cb", lambda d: col_has(d, ty, r"^(DN|UG|SU|UGSU|UGSS|UGZ|ZC|SS|WZ)"))
            # (classical novae come from the GCVS below: only 21 here)
            anyt = lambda d: d[[c for c in ("Type1", "Type2", "Type3", "Type4") if c in d]].astype(str).agg(" ".join, axis=1)  # noqa: E731
            print("    CV types e.g.", anyt(d).value_counts().head(15).to_dict(), flush=True)
            add("rk03", d, "CATACLYSMIC_POLAR", "STAR", "rk03", ("Name",), "B/cb", lambda d: anyt(d).str.contains(r"\b(?:AM|IP|DQ)\b"))
        d = fetch("B/cb/lmxbdata", limit=1000)
        add("rk03", d, "X_RAY_BINARY_LOW_MASS", "STAR", "rk03", ("Name",), "B/cb/lmxbdata")
    if want("gcvs"):
        # classical novae of the General Catalogue of Variable Stars (Samus et al. 2017)
        d = fetch("B/gcvs/gcvs_cat", {"VarType": "N*"}, limit=3000, need=("VarType",))
        add("gcvs", d, "NOVA_CLASSICAL", "STAR", "gcvs", lambda d: d[first_col(d, "GCVS", "Name")].astype(str), "B/gcvs", lambda d: col_has(d, ("VarType",), r"^N[ABC]?:?$|^NR$") & ~col_has(d, ("VarType",), r".*:$"))
    if want("liu06"):
        d = fetch("J/A+A/455/1165", limit=1000, need=("Name",))
        add("liu06", d, "X_RAY_BINARY_HIGH_MASS", "STAR", "liu06", ("Name", "ID"), "J/A+A/455/1165")
    if want("abell89"):
        d = fetch("VII/110A/table3", limit=5000)
        if d is not None:
            add(
                "abell89",
                d,
                "GALAXY_CLUSTER",
                "OTHER",
                "abell89",
                lambda d: "Abell " + d[first_col(d, "ACO", "A", "Abell")].astype(str),
                "VII/110A",
                lambda d: pd.to_numeric(d[first_col(d, "Rich", "R")], errors="coerce") >= 1,
            )
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="remote source keys to fetch (default all)")
    ap.add_argument("--local-only", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(V2 / "Get_data"))
    print("local truth files:", flush=True)
    parts = local_sources()
    if not a.local_only:
        try:
            import throttle

            throttle.install()
        except Exception:
            pass
        print("VizieR:", flush=True)
        parts += remote_sources(a.only)
    ref = pd.concat(parts, ignore_index=True)
    ref = ref[["name", "type", "coarse_class", "source", "bibcode", "catalog", "ra", "dec"]]
    OUT.mkdir(parents=True, exist_ok=True)
    ref.to_csv(OUT / "reference_objects.csv.gz", index=False)
    s = ref.groupby(["coarse_class", "type", "source"], sort=False).size().reset_index(name="n")
    lines = ["# Reference objects of confirmed nature", "", f"{len(ref)} objects, {s.type.nunique()} types (`build_reference_objects.py`).", "", "| coarse | type | n | source |", "|---|---|---|---|"]
    lines += [f"| {r.coarse_class} | {r.type} | {r.n} | {r.source} |" for r in s.itertuples()]
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
