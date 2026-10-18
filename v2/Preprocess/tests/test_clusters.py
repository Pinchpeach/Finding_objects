"""Galaxy cluster membership (clusters.py, 2.32.0)."""

import importlib.util
from pathlib import Path

import pandas as pd

V2 = Path(__file__).resolve().parents[2]


def _cl():
    s = importlib.util.spec_from_file_location("cl", V2 / "clusters.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_membership(tmp_path):
    cl = _cl()
    pd.DataFrame(
        [
            {
                "catalog": "Galaxy clusters",
                "catalog_object_id": "WH24 A",
                "ra": 200.0,
                "dec": 10.0,
                "cluster_source": "WH24",
                "cluster_z": 0.1,
                "cluster_z_spec": True,
                "cluster_r500_mpc": 1.0,
                "pcont": None,
            },
            {
                "catalog": "Galaxy clusters",
                "catalog_object_id": "eRASS1 B",
                "ra": 201.0,
                "dec": 10.0,
                "cluster_source": "eRASS1",
                "cluster_z": 0.2,
                "cluster_z_spec": False,
                "cluster_r500_mpc": 1.0,
                "pcont": 0.9,
            },  # contaminant: ignored
        ]
    ).to_csv(tmp_path / "galaxy_clusters_x.csv", index=False)
    d = 1 / 3600
    out = pd.DataFrame(
        [
            {"object_id": "bcg", "ra": 200.0, "dec": 10.0 + 1 * d, "primary_class": "GALAXY", "subclass_tags": None},
            {
                "object_id": "mem",
                "ra": 200.0,
                "dec": 10.0 + 120 * d,
                "primary_class": "GALAXY",
                "desi_dr1_spectroscopy__z": 0.103,
            },
            {
                "object_id": "bg",
                "ra": 200.0,
                "dec": 10.0 + 120 * d,
                "primary_class": "GALAXY",
                "desi_dr1_spectroscopy__z": 0.3,
            },
            {"object_id": "nz", "ra": 200.0, "dec": 10.0 + 120 * d, "primary_class": "GALAXY"},
            {"object_id": "far", "ra": 200.0, "dec": 10.5, "primary_class": "GALAXY"},  # 30' > r500 (9.0')
            {"object_id": "star", "ra": 200.0, "dec": 10.0 + 60 * d, "primary_class": "STAR"},
            {"object_id": "ctm", "ra": 201.0, "dec": 10.0, "primary_class": "GALAXY"},
        ]
    )
    r = cl.apply(out, tmp_path).set_index("object_id")
    assert r.loc["bcg", "cluster_membership"] == "BCG" and "brightest cluster galaxy" in r.loc["bcg", "subclass_tags"]
    assert r.loc["mem", "cluster_membership"] == "MEMBER"
    assert r.loc["bg", "cluster_membership"] == "NON_MEMBER"
    assert r.loc["nz", "cluster_membership"] == "IN_CLUSTER_AREA"
    for o in ("far", "star", "ctm"):
        assert pd.isna(r.loc[o, "cluster_membership"])
