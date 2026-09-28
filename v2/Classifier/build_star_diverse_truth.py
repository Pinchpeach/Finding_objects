"""Build a larger, prospectively specified LAMOST challenge set, never using predictions.

All pure WD labels in Guo+2022 table3 are eligible. Normal-star candidates are
queried in four RA quadrants and seven MK families; capped candidate pools are
explicitly audited and are NOT claimed to be a random survey sample.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
from astroquery.vizier import Vizier

ROOT = Path(__file__).resolve().parent
PURE = {'DA', 'DB', 'DC', 'DQ', 'DZ', 'DO'}


def query(catalog, cache, filters=None, limit=-1):
    if cache.exists():
        return pd.read_csv(cache, dtype={'ObsID': str, 'Name': str})
    errors = []
    for server in ('vizier.cds.unistra.fr', 'vizier.cfa.harvard.edu'):
        try:
            v = Vizier(columns=['**'], row_limit=limit)
            v.VIZIER_SERVER = server
            v.TIMEOUT = 120
            tables = v.query_constraints(catalog=catalog, **(filters or {}))
            if not tables:
                raise RuntimeError('No table returned; refusing to treat service failure as empty sample')
            d = tables[0].to_pandas()
            d.columns = [str(c).strip() for c in d.columns]
            cache.parent.mkdir(parents=True, exist_ok=True)
            d.to_csv(cache, index=False)
            return d
        except Exception as exc:
            errors.append(f'{server}: {exc!r}')
    raise RuntimeError('; '.join(errors))


def first(d, names):
    return next(c for c in names if c in d)


def standardize(d, wd=False):
    ra = first(d, ['RAJ2000', 'RAdeg', 'RA_ICRS', 'RA'])
    dec = first(d, ['DEJ2000', 'DEdeg', 'DE_ICRS', 'DEC', 'Dec'])
    label = first(d, ['SpType', 'NType', 'Type']) if wd else first(d, ['SubClass'])
    ident = first(d, ['Name', 'ObsID', 'GroupID']) if wd else first(d, ['ObsID'])
    q = pd.DataFrame({
        'external_id': d[ident].astype(str),
        'ra': pd.to_numeric(d[ra], errors='coerce'),
        'dec': pd.to_numeric(d[dec], errors='coerce'),
        'spectral_label': d[label].fillna('').astype(str).str.strip().str.upper(),
    })
    q['star_truth_class'] = 'WHITE_DWARF' if wd else 'NORMAL_STAR'
    q['truth_source'] = 'LAMOST_GUO2022_TABLE3' if wd else 'LAMOST_DR5_PIPELINE'
    q['truth_quality'] = 'PUBLISHED_PURE_WD_TYPE' if wd else 'PIPELINE_MK_LABEL'
    q['stratum'] = q.spectral_label if wd else q.spectral_label.str[0]
    if wd:
        q = q[q.spectral_label.isin(PURE)]
    else:
        q = q[q.spectral_label.str.fullmatch(r'[OBAFGKM](?:[0-9](?:\.[0-9])?)?(?:[IV]+)?')]
        if 'Class' in d:
            q = q[d.loc[q.index, 'Class'].astype(str).str.strip().str.upper().eq('STAR')]
    return q[np.isfinite(q.ra) & np.isfinite(q.dec)].copy()


def independent(d, reference):
    if d.empty or reference.empty:
        return d.copy()
    c = SkyCoord(d.ra.to_numpy()*u.deg, d.dec.to_numpy()*u.deg)
    r = SkyCoord(reference.ra.to_numpy()*u.deg, reference.dec.to_numpy()*u.deg)
    _, sep, _ = c.match_to_catalog_sky(r)
    return d.loc[sep.arcsec > 2.0].copy()


def hash_sample(d, n):
    q = d.copy()
    q['_order'] = q.external_id.map(lambda s: hashlib.sha256(('star-external-v2:'+str(s)).encode()).hexdigest())
    return q.sort_values('_order').head(n).drop(columns='_order')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--per-stratum', type=int, default=100)
    ap.add_argument('--candidate-cap', type=int, default=2000)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    # Exclude all original SDSS partitions and previously inspected LAMOST sets.
    refs = [pd.read_csv(ROOT/f) for f in ('star_truth.csv', 'lamost_star_external_truth.csv', 'wd_subtype_truth.csv')]
    reference = pd.concat(refs, ignore_index=True)[['ra', 'dec']].dropna()
    audit = {'design': 'all pure table3 WDs; SHA256 sample within MK-family x RA-quadrant capped candidate pools',
             'reference_rows': len(reference), 'coordinate_exclusion_arcsec': 2.0, 'queries': []}
    raw = query('J/MNRAS/509/2674/table3', a.cache/'wd_table3.csv')
    wd = standardize(raw, wd=True).drop_duplicates('external_id').drop_duplicates(['ra', 'dec'])
    audit['wd_raw_rows'] = len(raw)
    audit['wd_pure_unique_before_exclusion'] = len(wd)
    wd = independent(wd, reference)
    audit['wd_after_exclusion'] = len(wd)
    parts = [wd]
    # Also prevent pipeline-labelled normals from contradicting known WD truth.
    all_wd = standardize(raw, wd=True)
    normal_reference = pd.concat([reference, all_wd[['ra', 'dec']]], ignore_index=True)
    for fam in 'OBAFGKM':
        for quadrant in range(4):
            lo, hi = quadrant*90, (quadrant+1)*90
            d = query('V/164/dr5', a.cache/f'normal_{fam}_{quadrant}.csv',
                      {'SubClass': fam+'*', 'RAJ2000': f'{lo}..{hi}'}, a.candidate_cap)
            q = standardize(d)
            q = q[(q.ra >= lo) & (q.ra < hi) & q.stratum.eq(fam)]
            q = independent(q.drop_duplicates('external_id').drop_duplicates(['ra', 'dec']), normal_reference)
            selected = hash_sample(q, a.per_stratum)
            audit['queries'].append({'family': fam, 'ra_min': lo, 'ra_max': hi,
                                     'returned': len(d), 'cap_reached': len(d) >= a.candidate_cap,
                                     'eligible': len(q), 'selected': len(selected)})
            parts.append(selected)
            print(json.dumps(audit['queries'][-1]), flush=True)
    out = pd.concat(parts, ignore_index=True).drop_duplicates(['ra', 'dec'])
    out['benchmark_id'] = [f'DIVERSE_{hashlib.sha256((s+":"+i).encode()).hexdigest()[:20]}'
                           for s, i in zip(out.truth_source, out.external_id)]
    if out.benchmark_id.duplicated().any():
        raise ValueError('Duplicate source keys')
    if len(out) <= 1000 or out.star_truth_class.value_counts().min() < 500:
        raise ValueError('Insufficient enlarged challenge set')
    out.to_csv(a.out/'truth.csv', index=False)
    audit['counts'] = out.groupby(['star_truth_class', 'stratum']).size().to_dict()
    audit['counts'] = {'/'.join(k): int(v) for k,v in audit['counts'].items()}
    audit['truth_sha256'] = hashlib.sha256((a.out/'truth.csv').read_bytes()).hexdigest()
    (a.out/'selection_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
