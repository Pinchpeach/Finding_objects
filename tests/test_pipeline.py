import numpy as np
import pandas as pd

from finding_objects.pipeline import RunConfig, label_candidates


def test_label_candidates():
    cfg = RunConfig(ra=10.0, dec=20.0, high_snr=10.0)
    sources = pd.DataFrame({
        "source_id": [1, 2, 3],
        "snr": [20.0, 5.0, 15.0],
        "gaia_sep_arcsec": [0.2, np.nan, np.nan],
    })
    result = label_candidates(sources, cfg)
    assert result["candidate_label"].tolist() == [
        "gaia_matched",
        "unmatched_source",
        "high_snr_unmatched",
    ]
