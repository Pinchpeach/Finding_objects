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
SAMPLE_COLLECTORS={
    "GD 71":("gaia_dr3","allwise","twomass"),
    "RR Lyr":("gaia_dr3",),
    "delta Cep":("gaia_dr3",),
    "Mira":("gaia_dr3","allwise","twomass","agb_suh2021"),
    "PSR B0531+21":("atnf_pulsar",),
    "M 57":(),
    "SN 2011fe":(),
    "3C 273":("gaia_dr3","allwise","sdss_dr18","sdss_spectroscopy"),
}

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
    # Always keep a target-centred SIMBAD row, but remove the physical type so
    # it cannot leak the reference label into blind classification.
    try:
        mod=load_module(GET/"simbad.py","realval_simbad")
        df=mod.fetch(sample["ra"],sample["dec"],radius_arcmin)
        if "otype" in df.columns: df["otype"]=pd.NA
        mod.save(df,raw/"simbad_masked.csv")
        logs.append({"collector":"simbad_masked","status":"ok" if len(df) else "empty","rows":len(df),"error":""})
    except Exception as exc:
        logs.append({"collector":"simbad_masked","status":"error","rows":0,"error":repr(exc)})

    for name in SAMPLE_COLLECTORS[sample["name"]]:
        mod=load_module(GET/f"{name}.py",f"realval_{name}")
        out=raw/f"{name}.csv"
        try:
            df=mod.fetch(sample["ra"],sample["dec"],radius_arcmin)
            mod.save(df,out)
            logs.append({"collector":name,"status":"ok" if len(df) else "empty","rows":len(df),"error":""})
        except Exception as exc:
            logs.append({"collector":name,"status":"error","rows":0,"error":repr(exc)})
    return logs

