#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np, pandas as pd

CLASSES=("STAR","GALAXY","QSO")

def split_for(bid:str)->str:
    x=int(hashlib.sha256(bid.encode()).hexdigest()[:8],16)%10
    return "train" if x<6 else ("calibration" if x<8 else "test")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--truth",type=Path,required=True); p.add_argument("--catalog-root",type=Path,required=True); p.add_argument("--out",type=Path,required=True); a=p.parse_args()
    truth=pd.read_csv(a.truth); a.out.mkdir(parents=True,exist_ok=True)
    if len(truth)==0 or set(truth.truth_class)!=set(CLASSES):
        raise AssertionError("truth set must be non-empty and contain exactly STAR/GALAXY/QSO")
    assert truth.benchmark_id.is_unique
    counts=truth.truth_class.value_counts().to_dict()
    if len(set(counts.values())) != 1:
        raise AssertionError(f"truth classes must be balanced; got {counts}")
    expected_per_class=len(truth)//len(CLASSES)
    if len(truth)%len(CLASSES) or counts!={c:expected_per_class for c in CLASSES}:
        raise AssertionError(f"truth set size/classes inconsistent; rows={len(truth)}, counts={counts}")
    manifest=truth[["benchmark_id","truth_class","ra","dec"]].copy(); manifest["split"]=manifest.benchmark_id.map(split_for)
    reports=[]; problems=[]; active_catalogs=[]; excluded_catalogs=[]
    files=sorted(a.catalog_root.rglob("*_trd.csv"))
    for f in files:
        cat=f.stem[:-4] if f.stem.endswith("_trd") else f.stem
        d=pd.read_csv(f)
        present=set(d.benchmark_id.astype(str)) if len(d) else set()
        manifest[f"has_{cat}"]=manifest.benchmark_id.astype(str).isin(present)
        dup=int(d.benchmark_id.duplicated().sum()) if len(d) else 0
        bad_class=int((~d.truth_class.isin(CLASSES)).sum()) if len(d) and "truth_class" in d else 0
        bad_coord=0; sep_bad=0; sep_max=np.nan
        if len(d):
            for c in ("truth_ra","truth_dec"):
                if c in d: bad_coord += int(pd.to_numeric(d[c],errors="coerce").isna().sum())
            if "_sep_arcsec" in d:
                s=pd.to_numeric(d._sep_arcsec,errors="coerce"); sep_max=float(s.max())
                if "match_threshold_arcsec" in d: sep_bad=int((s>pd.to_numeric(d.match_threshold_arcsec,errors="coerce")).sum())
        matched=len(d)
        coverage_fraction=(matched/len(truth)) if len(truth) else 0.0
        use_for_model_validation=(matched>0 and not (dup or bad_class or bad_coord or sep_bad))
        exclusion_reason="" if use_for_model_validation else ("zero_coverage" if matched==0 else "validation_problem")
        reports.append({"catalog":cat,"matched":matched,"coverage_fraction":coverage_fraction,
                        "use_for_model_validation":use_for_model_validation,"exclusion_reason":exclusion_reason,
                        "duplicates":dup,"bad_truth_class":bad_class,"bad_coordinates":bad_coord,
                        "separation_violations":sep_bad,"max_sep_arcsec":sep_max,
                        **{c:int((d.truth_class==c).sum()) if len(d) and "truth_class" in d else 0 for c in CLASSES}})
        if use_for_model_validation:
            active_catalogs.append(cat)
        else:
            excluded_catalogs.append({"catalog":cat,"reason":exclusion_reason,"matched":matched,"coverage_fraction":coverage_fraction})
        if dup or bad_class or bad_coord or sep_bad: problems.append(cat)
    pd.DataFrame(reports).to_csv(a.out/"catalog_validation.csv",index=False)
    manifest.to_csv(a.out/"benchmark_manifest.csv",index=False)
    split_counts=manifest.groupby(["split","truth_class"]).size().unstack(fill_value=0)
    split_counts.to_csv(a.out/"split_counts.csv")
    selection={"policy":"Catalogs with matched > 0 and no validation problem are used for model validation; zero-coverage catalogs are temporarily excluded.","active_catalogs":active_catalogs,"excluded_catalogs":excluded_catalogs}
    (a.out/"model_validation_catalogs.json").write_text(json.dumps(selection,indent=2)+"\n")
    meta={"truth_rows":len(truth),"catalog_files":len(files),"invalid_catalogs":problems,
          "model_validation_catalogs":active_catalogs,
          "temporarily_excluded_catalogs":[x["catalog"] for x in excluded_catalogs],
          "label_leakage_policy":"truth_class/truth_source and spectroscopy truth identifiers are targets/metadata only; never classifier features",
          "coverage_policy":"preserve observed catalog coverage; no fabricated or duplicated detections; zero-coverage catalogs are excluded from model validation until usable coverage is demonstrated"}
    (a.out/"validation_summary.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(pd.DataFrame(reports).to_string(index=False)); print(split_counts.to_string())
    if problems: raise SystemExit("Validation failed: "+", ".join(problems))
if __name__=="__main__": main()
