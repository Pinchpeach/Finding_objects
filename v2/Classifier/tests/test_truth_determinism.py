"""The independent truth list does not depend on the order an archive answers in (2.61.9).

Before 2.61.9 the lists were "the first N rows the archive sends" and the validator drew ``DataFrame.sample(random_state=42)`` from them: over 25 bot
commits the variability classes had 6-7 different sets of truth ids (``validation/reproducibility/sample_states.csv``).
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CLS = Path(__file__).resolve().parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


D = _load(CLS / "truth" / "deterministic.py", "truth_deterministic")
B = _load(CLS / "truth" / "build_independent_truth_sets.py", "truth_builder_test")


def _frame(n=600, seed=0, classes=("A", "B")):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "truth_id": [f"ID{i:05d}" for i in range(n)],
            "ra": rng.uniform(0, 360, n),
            "dec": rng.uniform(-80, 80, n),
            "truth_axis": "variability",
            "truth_class": [classes[i % len(classes)] for i in range(n)],
        }
    )


def test_bottom_k_is_the_same_for_every_order_of_the_rows():
    df = _frame()
    a = D.bottom_k(df, 50)
    for s in (1, 2, 3):
        b = D.bottom_k(df.sample(frac=1.0, random_state=s).reset_index(drop=True), 50)
        assert list(a.truth_id) == list(b.truth_id)
    assert a.groupby("truth_class").size().to_dict() == {"A": 50, "B": 50}


def test_a_candidate_outside_the_sample_does_not_change_it_and_a_duplicate_does_not_count_twice():
    df = _frame()
    a = D.bottom_k(df, 40)
    outside = df[~df.truth_id.isin(a.truth_id)].iloc[:100]
    b = D.bottom_k(df.drop(outside.index), 40)  # 100 candidates that were not chosen are gone
    assert list(a.truth_id) == list(b.truth_id)
    dup = pd.concat([df, df.iloc[:30]], ignore_index=True)
    assert len(D.bottom_k(dup, 1000)) == len(df)
    assert D.bottom_k(df, 40, seed="another seed").truth_id.tolist() != a.truth_id.tolist()


def test_set_hash_ignores_order():
    assert D.ids_sha256(["b", "a", "c"]) == D.ids_sha256(["c", "b", "a"])
    assert D.ids_sha256(["a", "b"]) != D.ids_sha256(["a", "c"])


def _fake_archive(seed):
    """Every catalogue the builder asks for, in an order and with an extra tail that depend on ``seed`` (what a server does)."""
    rng = np.random.default_rng(seed)

    def table(n, **cols):
        d = pd.DataFrame({"RAJ2000": rng.uniform(0, 360, n), "DEJ2000": rng.uniform(-80, 80, n), **cols})
        return d

    base = np.random.default_rng(99)  # the CONTENT of the archive is the same for every seed
    ra = lambda n: base.uniform(0, 360, n)  # noqa: E731
    de = lambda n: base.uniform(-80, 80, n)  # noqa: E731
    tabs = {
        "J/A+A/697/A165/table4": pd.DataFrame({"KIC": np.arange(900), "EV": [1, 2, 1][0:1] * 0 + [1 + (i % 2) for i in range(900)], "RAJ2000": ra(900), "DEJ2000": de(900)}),
        "B/psr/psr": pd.DataFrame({"PSRJ": [f"J{i:04d}" for i in range(700)], "RAJ2000": ra(700), "DEJ2000": de(700)}),
        "V/84/main": pd.DataFrame({"PNG": [f"PN{i:04d}" for i in range(500)], "RAJ2000": ra(500), "DEJ2000": de(500)}),
        "B/sn/sncat": pd.DataFrame({"SN": [f"SN{i:04d}" for i in range(800)], "Type": "Ia", "RAJ2000": ra(800), "DEJ2000": de(800)}),
    }
    types = {t: pd.DataFrame({"ASASSN-V": [f"{t}{i:05d}" for i in range(700)], "Type": t, "Prob": 0.9, "RAJ2000": ra(700), "DEJ2000": de(700)}) for t in ("RRAB", "RRC", "DCEP", "DCEPS", "M", "SR")}

    def vizier(catalog, row_limit=-1, **constraints):
        t = types[constraints["Type"]] if catalog == "II/366/catv2021" else tabs[catalog]
        t = t.sample(frac=1.0, random_state=seed).reset_index(drop=True)  # another order every time
        if seed % 2:  # and a different tail when the archive is truncated by a limit
            t = t.iloc[: max(len(t) - 3, 1)] if row_limit != -1 else t
        return t

    return vizier


def test_the_builder_gives_the_same_files_whatever_the_archive_order(tmp_path, monkeypatch):
    sums = []
    for seed in (1, 2, 3):
        monkeypatch.setattr(B, "_vizier", _fake_archive(seed))
        out = tmp_path / f"b{seed}"
        summary = B.build(out, 250)
        assert all(x["status"] == "ok" and x["rows"] > 0 for x in summary)
        assert B.verify(out) == []
        sums.append(json.loads((out / B.MANIFEST).read_text())["sets"])
    for name in sums[0]:
        assert {s[name]["sha256"] for s in sums} == {sums[0][name]["sha256"]}, name  # the same bytes
        assert {s[name]["file"] for s in sums} == {sums[0][name]["file"]}
    assert B.list_sha256(tmp_path / "b1") == B.list_sha256(tmp_path / "b2") == B.list_sha256(tmp_path / "b3")
    v = pd.read_csv(tmp_path / "b1" / "variables_truth.csv")
    assert v.groupby("truth_class").size().to_dict() == {"CEPHEID": 250, "LPV": 250, "MIRA": 250, "RR_LYRAE": 250}


def test_verify_finds_a_changed_file_a_changed_class_and_a_failed_set(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "_vizier", _fake_archive(1))
    out = tmp_path / "l"
    B.build(out, 100)
    assert B.verify(out) == []
    f = out / "pn_truth.csv"
    f.write_text(f.read_text().replace("PN0", "PX0", 1))
    assert any("pn_truth.csv" in p and "SHA-256" in p for p in B.verify(out))
    assert B.verify(tmp_path / "nowhere")  # no manifest
    # a set that failed when it was built is recorded and is a problem, not a smaller list
    def failing(catalog, row_limit=-1, **c):
        if catalog == "II/366/catv2021" and c.get("Type") == "SR":
            raise RuntimeError("archive down")
        return _fake_archive(1)(catalog, row_limit, **c)

    monkeypatch.setattr(B, "_vizier", failing)
    B.build(tmp_path / "bad", 100)
    assert any("variables" in p and "error" in p for p in B.verify(tmp_path / "bad"))
