"""Evaluate the original serialized STAR model without fitting or tuning it."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import confusion_matrix, log_loss
from train_validate_star_wd import prepare, split_for

CLASSES = ['NORMAL_STAR', 'WHITE_DWARF']


def wilson(k, n):
    if not n:
        return [None, None]
    z = 1.959963984540054
    p = k/n
    mid = (p+z*z/(2*n))/(1+z*z/n)
    half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [float(mid-half), float(mid+half)]


def metrics(y, pred):
    y, pred = np.asarray(y), np.asarray(pred)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=CLASSES).ravel()
    n = len(y)
    return {'n': n, 'confusion': [[int(tn), int(fp)], [int(fn), int(tp)]],
            'accuracy': float((tn+tp)/n) if n else None,
            'accuracy_ci95': wilson(tn+tp, n),
            'wd_recall': float(tp/(tp+fn)) if tp+fn else None,
            'wd_recall_ci95': wilson(tp, tp+fn),
            'normal_specificity': float(tn/(tn+fp)) if tn+fp else None,
            'normal_specificity_ci95': wilson(tn, tn+fp),
            'wd_precision': float(tp/(tp+fp)) if tp+fp else None,
            'wd_precision_ci95': wilson(tp, tp+fp)}


def matrix(raw, features):
    x = prepare(raw)
    for name in features:
        if name not in x:
            if name.startswith('missing__'):
                base = name[len('missing__'):]
                x[name] = x[base].isna().astype(float) if base in x else 1.0
            else:
                raise ValueError(f'Frozen feature is unavailable: {name}')
    # Deliberately never select raw columns dynamically.
    if any(c in features for c in ('ra', 'dec', 'source_id', 'spectral_label', 'star_truth_class')):
        raise ValueError('Leakage in frozen feature schema')
    return x[features], x


def clean_external(ex, references):
    ex = ex.copy()
    for d in [ex, references]:
        if d.source_id.isna().any():
            raise ValueError('Missing Gaia ID prevents independence audit')
    audit = {'matched_rows': len(ex)}
    overlap = ex.source_id.isin(set(references.source_id))
    audit['reference_gaia_overlap_removed'] = int(overlap.sum())
    rejected = [ex.loc[overlap].assign(rejection_reason='reference_gaia_overlap')]
    ex = ex.loc[~overlap].copy()
    conflicting = ex.groupby('source_id').star_truth_class.nunique()
    bad = ex.source_id.isin(conflicting[conflicting > 1].index)
    audit['conflicting_label_rows_removed'] = int(bad.sum())
    rejected.append(ex.loc[bad].assign(rejection_reason='conflicting_truth'))
    ex = ex.loc[~bad].sort_values(['_sep_arcsec', 'benchmark_id'])
    dup = ex.source_id.duplicated()
    audit['duplicate_gaia_rows_removed'] = int(dup.sum())
    rejected.append(ex.loc[dup].assign(rejection_reason='duplicate_gaia'))
    ex = ex.loc[~dup].reset_index(drop=True)
    audit['unique_independent_rows'] = len(ex)
    return ex, pd.concat(rejected, ignore_index=True), audit


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--frozen', type=Path, required=True)
    p.add_argument('--sdss', type=Path, required=True)
    p.add_argument('--truth', type=Path, required=True)
    p.add_argument('--external', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    read = lambda f: pd.read_csv(f, dtype={'source_id': str, 'Source': str})
    sd, ex, previous, truth = map(read, (a.sdss, a.external, a.previous, a.truth))
    if truth.benchmark_id.duplicated().any() or ex.benchmark_id.duplicated().any():
        raise ValueError('Duplicate benchmark IDs')
    ex = ex.merge(truth[['benchmark_id', 'spectral_label', 'stratum']], on='benchmark_id', validate='one_to_one')
    ex, rejected, audit = clean_external(ex, pd.concat([sd, previous], ignore_index=True))
    rejected.to_csv(a.out/'rejected_matches.csv', index=False)
    if len(ex) <= 1000 or ex.star_truth_class.nunique() != 2:
        raise ValueError('Independent challenge set too small')
    frozen = joblib.load(a.frozen)
    model, features = frozen['model'], frozen['features']
    # Internal-test check establishes identity with the published model/run.
    internal = sd[sd.benchmark_id.map(split_for).eq('test')].reset_index(drop=True)
    xi, _ = matrix(internal, features)
    ip = model.predict(xi)
    im = metrics(internal.star_truth_class, ip)
    if im['n'] != 194 or sum(np.asarray(ip) == internal.star_truth_class.to_numpy()) != 183:
        raise ValueError(f'Original 183/194 baseline not reproduced: {im}')
    x, all_x = matrix(ex, features)
    prob = model.predict_proba(x)
    prediction = np.asarray(model.classes_)[prob.argmax(axis=1)]
    pwd = prob[:, list(model.classes_).index('WHITE_DWARF')]
    y = ex.star_truth_class.to_numpy()
    usable = (all_x.parallax_over_error > 1) & all_x.absolute_g.notna() & all_x.bp_rp.notna()
    baseline = np.where(usable & (all_x.absolute_g > 6+5*all_x.bp_rp), 'WHITE_DWARF', 'NORMAL_STAR')
    ex['prediction'] = prediction
    ex['p_white_dwarf'] = pwd
    ex['baseline_prediction'] = baseline
    ex['g_bin'] = pd.cut(all_x.g, [-np.inf, 16, 18, 20, np.inf], right=False).astype(str)
    ex['parallax_snr_bin'] = pd.cut(all_x.parallax_over_error, [-np.inf, 1, 5, 20, np.inf], right=False).astype(str)
    physical = [c for c in features if not c.startswith('missing__')]
    ex['has_missing_feature'] = x[physical].isna().any(axis=1)
    report = {'frozen_run': 36295747956, 'model_sha256': hashlib.sha256(a.frozen.read_bytes()).hexdigest(),
              'truth_sha256': hashlib.sha256(a.truth.read_bytes()).hexdigest(),
              'versions': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__, 'pandas': pd.__version__},
              'features': features, 'audit': audit, 'internal_reproduction': im,
              'truth_rows': len(truth), 'gaia_matched_rows_before_exclusions': len(read(a.external)),
              'learned': metrics(y, prediction), 'baseline': metrics(y, baseline),
              'baseline_usable_fraction': float(usable.mean()),
              'log_loss': float(log_loss(y, prob, labels=list(model.classes_))),
              'brier': float(np.mean((pwd-(y == 'WHITE_DWARF'))**2)), 'subgroups': {}}
    for col in ['stratum', 'g_bin', 'parallax_snr_bin', 'has_missing_feature']:
        report['subgroups'][col] = {str(k): metrics(q.star_truth_class, q.prediction) for k,q in ex.groupby(col, dropna=False)}
    non_da = ex[(ex.star_truth_class == 'WHITE_DWARF') & (ex.spectral_label != 'DA')]
    nd = metrics(non_da.star_truth_class, non_da.prediction)
    report['non_da'] = nd
    learned = report['learned']
    # Prospective research gate, not an assertion of universal physical validity.
    report['gate_definition'] = 'Overall WD recall and normal specificity lower 95% Wilson bounds >=0.90; non-DA n>=100 and recall lower bound >=0.90. No tuning on this set.'
    report['gate_passed'] = bool(learned['wd_recall_ci95'][0] >= .90 and learned['normal_specificity_ci95'][0] >= .90 and nd['n'] >= 100 and nd['wd_recall_ci95'][0] >= .90)
    coverage = truth.groupby('stratum').size().rename('truth_rows').to_frame()
    coverage['matched_rows'] = read(a.external).merge(truth[['benchmark_id','stratum']], on='benchmark_id').groupby('stratum').size()
    coverage['evaluated_rows'] = ex.groupby('stratum').size()
    coverage.fillna(0).to_csv(a.out/'coverage_by_stratum.csv')
    ex.to_csv(a.out/'predictions.csv', index=False)
    (a.out/'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
