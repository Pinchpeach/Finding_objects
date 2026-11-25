"""``t_n_fragments_top``: the A/B fragment count over top-level objects only (2.60.11); ``t_n_fragments`` is unchanged."""

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BENCH = Path(__file__).resolve().parents[2] / "benchmark"
sys.path.insert(0, str(BENCH))
import score_independent_fields as S  # noqa: E402

LS, PS1, WISE = "DESI Legacy Surveys DR10", "Pan-STARRS1 DR2 MeanObject", "AllWISE"


def _field(tmp_path):
    a = 1 / 3600
    fdir = tmp_path / "f1"
    (fdir / "truth").mkdir(parents=True)
    (fdir / "field.json").write_text(json.dumps({"ra": 150.0, "dec": 2.0, "radius_arcmin": 6.0}))
    truth = pd.DataFrame(
        {
            "_RAJ2000": [150.0, 150.02],
            "_DEJ2000": [2.0, 2.0],
            "ACSF814Wmag": [22.0, 22.0],
            "ACSmuClass": [1, 1],
            "lptype": [0, 0],
        }
    )
    truth.to_csv(fdir / "truth" / "J_ApJS_258_11_classic.csv.gz", index=False)
    objs = pd.DataFrame(
        [
            # truth A: a three-catalogue object, a top-level LS-only row 0.5'' away, a grouped LS-only row 0.6'' away
            dict(
                object_id="H",
                ra=150.0,
                dec=2.0,
                catalogs=f"{WISE}|{LS}|{PS1}",
                primary_class="GALAXY",
                parent_object_id=None,
            ),
            dict(object_id="T", ra=150.0 + 0.5 * a, dec=2.0, catalogs=LS, primary_class="STAR", parent_object_id=None),
            dict(object_id="G", ra=150.0, dec=2.0 + 0.6 * a, catalogs=LS, primary_class="STAR", parent_object_id="H"),
            # truth B: a three-catalogue object and only a grouped LS-only row near it
            dict(
                object_id="H2",
                ra=150.02,
                dec=2.0,
                catalogs=f"{WISE}|{LS}|{PS1}",
                primary_class="GALAXY",
                parent_object_id=None,
            ),
            dict(
                object_id="G2", ra=150.02 + 0.4 * a, dec=2.0, catalogs=LS, primary_class="STAR", parent_object_id="H2"
            ),
        ]
    )
    with gzip.open(fdir / "objects_blind.csv.gz", "wt") as f:
        objs.to_csv(f, index=False)
    return fdir


def test_grouped_rows_are_not_counted_in_the_top_level_count_and_the_old_count_is_kept(tmp_path):
    m, info = S.field_matches(_field(tmp_path), "blind", pd.DataFrame({"ra": [], "dec": []}))
    m = m.sort_values("t_ra").reset_index(drop=True)
    assert len(m) == 2
    # truth A: the grouped and the top-level row both count in the set-C definition; only the top-level one in the new one
    assert m.t_n_fragments.tolist() == [2, 1]
    assert m.t_n_fragments_top.tolist() == [1, 0]
    # nothing else moved: the counterpart is the multi-catalogue object, whose label is the same either way
    assert m.object_id.tolist() == ["H", "H2"] and m.ours.tolist() == ["GALAXY", "GALAXY"]
