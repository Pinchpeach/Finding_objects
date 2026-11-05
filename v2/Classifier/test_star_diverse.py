import numpy as np
import pandas as pd
from evaluate_star_diverse import clean_external, matrix, wilson
from train_validate_star_wd import prepare


def test_source_identity_overlap_and_conflicting_truth():
    ex = pd.DataFrame({'source_id': ['1234567890123456789','2','2','3','3','4'],
        'benchmark_id': list('abcdef'), '_sep_arcsec': [.1,.2,.1,.1,.2,.1],
        'star_truth_class': ['WHITE_DWARF','WHITE_DWARF','NORMAL_STAR','WHITE_DWARF','WHITE_DWARF','NORMAL_STAR']})
    clean, rejected, audit = clean_external(ex, pd.DataFrame({'source_id':['1234567890123456789']}))
    assert clean.benchmark_id.tolist() == ['d','f']
    assert len(rejected) == 4
    assert audit['reference_gaia_overlap_removed'] == 1
    assert audit['conflicting_label_rows_removed'] == 2


def test_metadata_never_changes_model_features_and_nan_survives():
    raw = pd.DataFrame({'benchmark_id':['a','b'], 'parallax':[1,np.nan], 'parallax_error':[.1,.2], 'phot_g_mean_mag':[18,19]})
    schema = [c for c in prepare(raw) if c != 'benchmark_id']
    before, _ = matrix(raw, schema)
    raw['ra'] = [100,200]
    raw['dec'] = [-30,50]
    raw['star_truth_class'] = ['NORMAL_STAR','WHITE_DWARF']
    raw['spectral_label'] = ['DA','M5']
    raw['source_id'] = ['1','2']
    after, _ = matrix(raw, schema)
    pd.testing.assert_frame_equal(before, after)
    assert np.isnan(after.loc[1,'parallax'])
    assert np.isnan(after.loc[1,'absolute_g'])


def test_missing_indicators_follow_frozen_schema():
    raw = pd.DataFrame({'benchmark_id':['a'], 'parallax':[2.]})
    x, _ = matrix(raw, ['parallax','missing__parallax','missing__g'])
    assert x.iloc[0].tolist() == [2.,0.,1.]


def test_wilson_reports_small_sample_uncertainty():
    assert wilson(0,0) == [None,None]
    assert wilson(10,10)[0] < .75
    assert wilson(100,100)[0] > .96
