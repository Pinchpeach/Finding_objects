"""Diagnostics for the practical-use fixes of 2.54.0 (run in GitHub Actions:
the development container cannot reach the archives).

    python practical_probe.py vizier            # how each VizieR mirror answers
    python practical_probe.py simbad            # SIMBAD at CDS and at the Harvard mirror
    python practical_probe.py ps1               # MAST PS1 DR2 MeanObject vs VizieR II/349 (PS1 DR1)
    python practical_probe.py httplog LOG SUMMARY   # per-collector request breakdown of a V2_HTTP_LOG run
"""

from __future__ import annotations

import re
import sys
import time

COSMOS = (150.1191, 2.2058)
VIZIER_HOSTS = (
    "vizier.cds.unistra.fr",
    "vizier.cfa.harvard.edu",
    "vizier.nao.ac.jp",
    "vizier.iucaa.in",
    "vizier.china-vo.org",
    "vizier.idia.ac.za",
)


def vizier():
    """A catalogue with rows, the same catalogue in an empty cone, and an
    unknown catalogue, at every mirror: can an empty cone be told apart from a
    mirror that lacks the catalogue?"""
    import requests

    cases = {
        "rows (AllWISE 0.5')": ("II/328/allwise", 30.0),
        "empty cone (NVSS 2\")": ("VIII/65/nvss", 2.0),
        "empty cone (Suh AGB t9 2\")": ("J/ApJS/256/43/table9", 2.0),
        "unknown catalogue": ("J/XXX/999/nosuch", 30.0),
    }
    for host in VIZIER_HOSTS:
        for label, (cat, rs) in cases.items():
            url = f"https://{host}/viz-bin/votable"
            params = {"-source": cat, "-c": f"{COSMOS[0]} {COSMOS[1]}", "-c.rs": rs, "-out": "_RAJ2000,_DEJ2000", "-out.max": 50}
            t0 = time.monotonic()
            try:
                r = requests.get(url, params=params, timeout=(10, 40))
                text = r.text
                infos = re.findall(r"<INFO[^>]*>", text)[:6]
                res = re.findall(r"<RESOURCE[^>]*>", text)[:3]
                rows = text.count("<TR>")
                print(
                    f"{host:24s} {label:28s} {r.status_code} {time.monotonic() - t0:5.1f}s len={len(text):6d} "
                    f"table={'<TABLE' in text.upper()} rows={rows}\n    RESOURCE={res}\n    INFO={infos}",
                    flush=True,
                )
            except Exception as exc:
                print(f"{host:24s} {label:28s} {type(exc).__name__} {time.monotonic() - t0:5.1f}s {str(exc)[:120]}", flush=True)


def vizier_mini():
    """astroquery's own request body (-out.form=mini) for an empty cone and an
    unknown catalogue at the working mirrors, then the same without the mini
    form and one row: the confirmation throttle.py makes (2.54.0)."""
    import requests

    body = "-source={cat}\n-out.max=unlimited\n-out.all\n-c=150.11910623+2.20579505\n-c.rs=2.0\n-out.meta=huUD\n-out.form=mini\n-oc.form=d"
    for host in ("vizier.cds.unistra.fr", "vizier.cfa.harvard.edu", "vizier.idia.ac.za"):
        for cat in ("VIII/65/nvss", "J/ApJS/256/43/table9", "J/XXX/999/nosuch", "II/328/allwise"):
            for label, data in (("mini", body.format(cat=cat)),
                                ("confirm", "\n".join([l for l in body.format(cat=cat).splitlines() if not l.startswith(("-out.form=", "-out.max="))] + ["-out.max=1"]))):
                t0 = time.monotonic()
                try:
                    r = requests.post(f"https://{host}/viz-bin/votable", data=data, timeout=(10, 40))
                    t = r.text
                    print(f"{host:24s} {cat:22s} {label:8s} {r.status_code} {time.monotonic() - t0:4.1f}s table={'<TABLE' in t.upper()} tr={t.count('<TR>')} len={len(t)}", flush=True)
                except Exception as exc:
                    print(f"{host:24s} {cat:22s} {label:8s} {type(exc).__name__}", flush=True)


def simbad():
    from astroquery.simbad import Simbad
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    for server in ("simbad.cds.unistra.fr", "simbad.harvard.edu"):
        t0 = time.monotonic()
        try:
            s = Simbad()
            s.server = server
            s.add_votable_fields("otype", "sp", "plx", "pmra", "pmdec", "rvz_redshift")
            t = s.query_region(SkyCoord(COSMOS[0] * u.deg, COSMOS[1] * u.deg), radius=1 * u.arcmin)
            n = 0 if t is None else len(t)
            cols = [] if t is None else list(t.colnames)
            print(f"{server}: cone {n} rows {time.monotonic() - t0:.1f}s columns {cols}", flush=True)
            t1 = time.monotonic()
            od = s.query_tap("SELECT TOP 3 otype, label FROM otypedef")
            print(f"{server}: TAP otypedef {len(od)} rows {time.monotonic() - t1:.1f}s", flush=True)
        except Exception as exc:
            print(f"{server}: {type(exc).__name__} {time.monotonic() - t0:.1f}s {str(exc)[:200]}", flush=True)


def ps1():
    """Same cone from MAST (DR2 MeanObject) and VizieR II/349/ps1 (DR1, Chambers
    et al. 2016): columns, rows, and the magnitude differences of objects
    matched by objID."""
    from io import StringIO

    import numpy as np
    import pandas as pd
    import requests
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    for ra, dec, r in ((COSMOS[0], COSMOS[1], 2.0), (188.4155, 9.1751, 2.0), (283.3044, -3.5206, 1.0)):
        cols = ["objID", "raMean", "decMean", "nDetections", "qualityFlag", "objInfoFlag"] + [
            f"{b}Mean{k}Mag" for b in "grizy" for k in ("PSF", "Kron")
        ]
        t0 = time.monotonic()
        m = requests.get(
            "https://catalogs.mast.stsci.edu/api/v0.1/panstarrs/dr2/mean.csv",
            params={"ra": ra, "dec": dec, "radius": r / 60, "nDetections.gte": 2, "columns": "[" + ",".join(cols) + "]"},
            timeout=120,
        )
        mast = pd.read_csv(StringIO(m.text), dtype={"objID": "string"}) if m.text.strip() else pd.DataFrame()
        tm = time.monotonic() - t0
        t0 = time.monotonic()
        v = Vizier(columns=["**"], row_limit=-1).query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=r * u.arcmin, catalog="II/349/ps1")
        tv = time.monotonic() - t0
        viz = v[0].to_pandas() if v else pd.DataFrame()
        print(f"\n== cone {ra} {dec} r={r}': MAST {m.status_code} {len(mast)} rows {tm:.1f}s; VizieR {len(viz)} rows {tv:.1f}s")
        print("VizieR II/349/ps1 columns:", list(viz.columns))
        if mast.empty or viz.empty:
            continue
        viz["objID"] = viz["objID"].astype("Int64").astype("string")
        nd = next((c for c in ("Nd", "nDetections") if c in viz), None)
        if nd:
            print("VizieR rows with Nd >= 2:", int(pd.to_numeric(viz[nd], errors="coerce").ge(2).sum()))
        j = mast.merge(viz, on="objID", how="inner")
        print(f"matched by objID: {len(j)} of MAST {len(mast)} / VizieR {len(viz)}")
        for b in "grizy":
            for mk, vk in ((f"{b}MeanPSFMag", f"{b}mag"), (f"{b}MeanKronMag", f"{b}Kmag")):
                if mk in j and vk in j:
                    x = pd.to_numeric(j[mk], errors="coerce").where(lambda s: s > -900)
                    y = pd.to_numeric(j[vk], errors="coerce")
                    d = (x - y).dropna()
                    if len(d):
                        print(
                            f"  {mk:16s} - {vk:6s}: n={len(d):4d} median={d.median():+.4f} "
                            f"p95|d|={d.abs().quantile(0.95):.4f} max|d|={d.abs().max():.4f}"
                        )
        if nd:
            dn = pd.to_numeric(j["nDetections"], errors="coerce") - pd.to_numeric(j[nd], errors="coerce")
            print("  nDetections - Nd:", dn.describe().round(2).to_dict())
        for mk, vk in (("qualityFlag", "Qual"), ("objInfoFlag", "f_objID")):
            if mk in j and vk in j:
                same = (pd.to_numeric(j[mk], errors="coerce") == pd.to_numeric(j[vk], errors="coerce")).mean()
                print(f"  {mk} == {vk}: {100 * same:.1f} %")


def httplog(log_path, summary_path):
    import pandas as pd

    rows = []
    for line in open(log_path, encoding="utf-8", errors="replace"):
        m = re.match(r"\[http\] (\S+) (\S+) (.+) ([0-9.]+)s$", line.strip())
        if m:
            rows.append(dict(collector=m.group(1), host=m.group(2), outcome=m.group(3), seconds=float(m.group(4))))
    if not rows:
        print("no [http] lines")
        return
    h = pd.DataFrame(rows)
    s = pd.read_csv(summary_path)
    agg = h.groupby("collector").agg(requests=("host", "size"), request_s=("seconds", "sum"),
                                       hosts=("host", lambda x: ",".join(sorted(set(x)))),
                                       outcomes=("outcome", lambda x: ",".join(f"{k}x{v}" for k, v in x.value_counts().items())))
    out = s.set_index("collector")[["status", "rows", "elapsed_seconds", "cache"]].join(agg, how="left")
    out["pause_estimate_s"] = out.requests.fillna(0) * 4.0
    with pd.option_context("display.width", 250, "display.max_colwidth", 80, "display.max_rows", 100):
        print(out.sort_values("elapsed_seconds", ascending=False).to_string())


if __name__ == "__main__":
    {"vizier": vizier, "vizier_mini": vizier_mini, "simbad": simbad, "ps1": ps1}.get(sys.argv[1], lambda: httplog(*sys.argv[2:4]))()
