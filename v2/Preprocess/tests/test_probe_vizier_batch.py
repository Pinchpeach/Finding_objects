"""``Get_data/probe_vizier_batch.py`` (2.62.12): the per-mirror batch-size probe, without the network."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Get_data"))
import probe_vizier_batch as P  # noqa: E402


def fake(limit):
    """A mirror that answers up to ``limit`` positions in size/10 s and answers 504 after 60 s above it."""
    def send(host, chunk):
        n = len(chunk)
        if n > limit.get(host, 10**9):
            return dict(status="504", seconds=60.3, bytes=200, rows=-1, error="")
        return dict(status="200", seconds=n / 10, bytes=1000 * n, rows=n, error="")
    return send


def test_a_host_that_fails_every_repeat_of_a_size_is_not_sent_the_larger_sizes():
    truth = pd.DataFrame({"ra": range(1000), "dec": range(1000)})
    t = P.probe(truth, ["cfa", "idia"], [50, 125, 250, 500], 2, send=fake({"cfa": 125}), sleep=lambda s: None)
    cfa = t[t.host == "cfa"]
    assert sorted(cfa["size"].unique()) == [50, 125, 250]  # 250 failed twice: 500 not sent
    assert (t[t.host == "idia"]["size"].value_counts() == 2).all() and len(t[t.host == "idia"]) == 8
    assert set(t.first_row) == {0, 500}  # the repeats do not overlap


def test_the_summary_counts_answers_and_names_the_failures():
    truth = pd.DataFrame({"ra": range(1000), "dec": range(1000)})
    s = P.summarize(P.probe(truth, ["cfa"], [125, 250], 2, send=fake({"cfa": 125}), sleep=lambda s: None)).set_index("size")
    assert s.loc[125, "answered"] == 2 and s.loc[125, "positions_per_s"] == 10.0 and s.loc[125, "failures"] == ""
    assert s.loc[250, "answered"] == 0 and s.loc[250, "failures"] == "504 x2"
