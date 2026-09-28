#!/usr/bin/env python3
"""Blind-style validation on named real astronomical sources.

SIMBAD is used to resolve coordinates and provide an external reference type.
For the blind pipeline, the SIMBAD otype is masked before Preprocess/Classifier,
so successful routes must come from independent catalog measurements.
"""
from __future__ import annotations
import argparse, importlib.util, json, math, subprocess, sys, tempfile
from pathlib import Path
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.simbad import Simbad

ROOT=Path(__file__).resolve().parents[1]
GET=ROOT/"Get_data"
PRE=ROOT/"Preprocess"
CLS=ROOT/"Classifier"

SAMPLES=[
    {"name":"GD 71","truth_axis":"physical","truth_class":"WD"},
    {"name":"RR Lyr","truth_axis":"variability","truth_class":"RR_LYRAE"},
    {"name":"delta Cep","truth_axis":"variability","truth_class":"CEPHEID"},
    {"name":"Mira","truth_axis":"physical","truth_class":"AGB"},
    {"name":"PSR B0531+21","truth_axis":"compact","truth_class":"PULSAR"},
    {"name":"M 57","truth_axis":"phenomenon","truth_class":"PN"},
    {"name":"SN 2011fe","truth_axis":"phenomenon","truth_class":"SN"},
    {"name":"3C 273","truth_axis":"extragalactic","truth_class":"QSO"},
]
COLLECTORS=("gaia_dr3","sdss_dr18","sdss_spectroscopy","allwise","twomass","agb_suh2021","atnf_pulsar")

def load_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None: raise ImportError(path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def text(v):
    if v is None:return None
    s=str(v).strip()
    return None if not s or s.lower()=="nan" else s

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def resolve(name:str):
    s=Simbad(); s.add_votable_fields("otype","sp")
    t=s.query_object(name)
    if t is None or len(t)==0: raise RuntimeError(f"SIMBAD cannot resolve {name}")
    d=t.to_pandas().iloc[0]
    low={str(k).lower():k for k in d.index}
    rac=low.get("ra"); decc=low.get("dec"); oc=low.get("otype"); mc=low.get("main_id"); spc=low.get("sp")
    ra=num(d[rac]); dec=num(d[decc])
    if ra is None or dec is None:
        c=SkyCoord(str(d[rac]),str(d[decc]),unit=(u.hourangle,u.deg))
        ra,dec=float(c.ra.deg),float(c.dec.deg)
    return {
        "resolved_name":text(d[mc]) if mc else name,
        "ra":ra,"dec":dec,
        "truth_otype":text(d[oc]) if oc else None,
        "truth_sp":text(d[spc]) if spc else None,
    }

def run_cmd(args):
    p=subprocess.run([sys.executable,*map(str,args)],text=True,capture_output=True)
    if p.returncode!=0:
        raise RuntimeError(f"command failed: {' '.join(map(str,args))}\nSTDOUT={p.stdout[-2000:]}\nSTDERR={p.stderr[-4000:]}")
    return p

def collect(sample,raw:Path,radius_arcmin:float):
    logs=[]
    for name in COLLECTORS:
        mod=load_module(GET/f"{name}.py",f"realval_{name}")
        out=raw/f"{name}.csv"
        try:
            df=mod.fetch(sample["ra"],sample["dec"],radius_arcmin)
            mod.save(df,out)
            logs.append({"collector":name,"status":"ok" if len(df) else "empty","rows":len(df),"error":""})
        except Exception as exc:
            logs.append({"collector":name,"status":"error","rows":0,"error":repr(exc)})
    return logs

def science_snapshot(row:pd.Series):
    exact=[
        "ra","dec","parallax","parallax_error","pmra","pmdec","ruwe",
        "phot_g_mean_mag","phot_bp_mean_mag","phot_rp_mean_mag","bp_rp",
        "teff_gspphot","logg_gspphot","mh_gspphot","mass_flame","age_flame","evolstage_flame",
        "best_class_name","best_class_score","agb_subclass",
    ]
    out={}
    for c in exact:
        if c in row.index and pd.notna(row[c]):
            v=row[c]; out[c]=v.item() if hasattr(v,"item") else v
    for c in row.index:
        lc=str(c).lower()
        if any(k in lc for k in ("period","p0","pdot","dispersion","__dm")) and c not in out and pd.notna(row[c]):
            v=row[c]; out[c]=v.item() if hasattr(v,"item") else v
    return out

def nearest(df:pd.DataFrame,ra:float,dec:float):
    r=pd.to_numeric(df["ra"],errors="coerce"); d=pd.to_numeric(df["dec"],errors="coerce")
    dra=(r-ra)*math.cos(math.radians(dec)); dde=d-dec
    sep=3600*(dra*dra+dde*dde)**0.5
    i=sep.idxmin()
    return df.loc[i],float(sep.loc[i])

def classify_assisted(row:pd.Series,otype):
    axes=load_module(CLS/"control_axes.py","realval_axes")
    q=pd.DataFrame([row.to_dict()]); q["otype"]=otype
    return axes.annotate(q).iloc[0]

def validate_one(spec,base:Path,radius_arcmin:float):
    resolved=resolve(spec["name"]); sample={**spec,**resolved}
    sdir=base/spec["name"].replace(" ","_").replace("/","_")
    raw=sdir/"raw"; pre=sdir/"pre"; cls=sdir/"cls"
    raw.mkdir(parents=True,exist_ok=True); pre.mkdir(); cls.mkdir()
    logs=collect(sample,raw,radius_arcmin)

    run_cmd([PRE/"01_source_association.py","--raw-dir",raw,"--out",pre/"source_association.csv"])
    run_cmd([PRE/"02_integrate_objects.py","--associations",pre/"source_association.csv","--raw-dir",raw,"--out",pre/"integrated_objects.csv"])
    run_cmd([PRE/"03_extract_features.py","--objects",pre/"integrated_objects.csv","--rules",PRE/"classification_rules.csv","--out",pre/"features.csv"])
    run_cmd([PRE/"04_build_evidence.py","--features",pre/"features.csv","--rules",PRE/"classification_rules.csv","--out",pre/"evidence.csv"])
    run_cmd([PRE/"05_likelihood_vectors.py","--evidence",pre/"evidence.csv","--out",pre/"likelihood_vectors.csv"])
    run_cmd([CLS/"01_prepare_input.py","--input",pre/"likelihood_vectors.csv","--out",cls/"classifier_input.csv"])
    run_cmd([CLS/"control.py","--input",cls/"classifier_input.csv","--out",cls/"classified.csv"])

    d=pd.read_csv(cls/"classified.csv")
    row,sep=nearest(d,sample["ra"],sample["dec"])
    axis=sample["truth_axis"]; blind=text(row.get(f"{axis}_class")) or "UNKNOWN"
    status=text(row.get(f"{axis}_status"))
    assisted=classify_assisted(row,sample["truth_otype"])
    assisted_label=text(assisted.get(f"{axis}_class")) or "UNKNOWN"
    return {
        **sample,
        "nearest_sep_arcsec":sep,
        "primary_class":text(row.get("primary_class")),
        "blind_class":blind,
        "blind_status":status,
        "blind_match":blind==sample["truth_class"],
        "catalog_assisted_class":assisted_label,
        "catalog_assisted_match":assisted_label==sample["truth_class"],
        "science_json":json.dumps(science_snapshot(row),ensure_ascii=False,default=str),
        "collector_json":json.dumps(logs,ensure_ascii=False),
    }

def write_report(df:pd.DataFrame,out_dir:Path):
    out_dir.mkdir(parents=True,exist_ok=True)
    csv=out_dir/"real_sample_validation.csv"; df.to_csv(csv,index=False)
    independent=df["blind_match"].astype(bool)
    md=[
        "# Real-sample multi-axis validation","",
        "SIMBAD was used only for coordinate resolution and external reference type. Its otype was excluded from the blind pipeline.",
        "Catalog-assisted results are shown separately and are not counted as independent validation.","",
        f"- samples: **{len(df)}**",
        f"- blind exact-axis matches: **{int(independent.sum())}/{len(df)} ({independent.mean():.1%})**","",
        "| sample | SIMBAD reference | axis | expected | blind | status | sep (") | assisted |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for _,r in df.iterrows():
        md.append(f"| {r['name']} | {r['truth_otype']} | {r['truth_axis']} | {r['truth_class']} | {r['blind_class']} | {r['blind_status']} | {r['nearest_sep_arcsec']:.3f} | {r['catalog_assisted_class']} |")
    md += ["","## Scientific measurements",""]
    for _,r in df.iterrows():
        md.append(f"### {r['name']}")
        md.append("")
        md.append(f"- coordinates: RA={r['ra']:.8f} deg, Dec={r['dec']:.8f} deg")
        md.append(f"- spectral type/reference: {r['truth_sp']}")
        md.append(f"- measured fields: {r['science_json']}")
        md.append("")
    md += ["## Interpretation rules","",
        "- A blind success means the expected axis class was recovered without feeding SIMBAD otype into the classifier.",
        "- UNKNOWN is preferable to a fabricated label when required evidence is absent.",
        "- PN/SN catalog-assisted success alone is not independent physical validation.",
    ]
    (out_dir/"REAL_SAMPLE_VALIDATION.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    return csv

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,default=CLS/"validation")
    p.add_argument("--radius-arcmin",type=float,default=0.25)
    a=p.parse_args()
    with tempfile.TemporaryDirectory() as td:
        base=Path(td); rows=[]
        for spec in SAMPLES:
            try:
                r=validate_one(spec,base,a.radius_arcmin)
            except Exception as exc:
                r={**spec,"resolved_name":None,"ra":math.nan,"dec":math.nan,"truth_otype":None,"truth_sp":None,
                   "nearest_sep_arcsec":math.nan,"primary_class":None,"blind_class":"ERROR","blind_status":repr(exc),
                   "blind_match":False,"catalog_assisted_class":"ERROR","catalog_assisted_match":False,
                   "science_json":"{}","collector_json":"[]"}
            rows.append(r); print(spec["name"],r["blind_class"],r["blind_status"],flush=True)
    df=pd.DataFrame(rows); write_report(df,a.out_dir)
    print(df[["name","truth_axis","truth_class","blind_class","blind_status","blind_match"]].to_string(index=False))
if __name__=="__main__": main()
