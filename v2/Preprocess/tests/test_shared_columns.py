"""The shared bare columns of Stage 2 (2.61.4): the code list, the table and the readers agree."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT.parent / "benchmark" / "shared_columns" / "shared_columns.csv"


def _stage2():
    spec = importlib.util.spec_from_file_location("pre_02_shared", ROOT / "02_integrate_objects.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_table_lists_exactly_the_names_stage2_drops():
    t = pd.read_csv(TABLE)
    assert set(t.name) == set(_stage2().SHARED_FIELDS)
    assert (t.n_catalogues >= 2).all(), "a name in the table is shared by at least two catalogues"
    assert t.name.is_unique


def test_every_name_has_a_stated_reader_status():
    t = pd.read_csv(TABLE).fillna("")
    assert (t.readers_of_the_bare_name != "").all() and (t.reader_change != "").all() and (t.stage2_now != "").all()


def test_run_headers_add_names_that_two_catalogues_share(tmp_path):
    m = _stage2()
    (tmp_path / "a.csv").write_text("catalog_object_id,only_a,twice\n1,1,2\n")
    (tmp_path / "b.csv").write_text("catalog_object_id,only_b,twice\n1,1,2\n")
    assoc = pd.DataFrame({"input_file": ["a.csv", "b.csv"], "catalog": ["A", "B"]})
    got = m.shared_fields(assoc, tmp_path)
    assert "twice" in got and "catalog_object_id" in got  # two catalogues, same name
    assert "only_a" not in got and "only_b" not in got
    assert m.SHARED_FIELDS <= got
    # two files of one catalogue are not "two catalogues"
    assoc2 = pd.DataFrame({"input_file": ["a.csv", "b.csv"], "catalog": ["A", "A"]})
    assert "twice" not in m.shared_fields(assoc2, tmp_path)
