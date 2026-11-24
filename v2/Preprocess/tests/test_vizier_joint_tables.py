"""The tables of one VizieR catalogue are asked in one request (2.60.2): agb_suh2021 and the Gaia SOS collector."""

import sys
from pathlib import Path

import pandas as pd
import pytest

GET = Path(__file__).resolve().parents[2] / "Get_data"
sys.path.insert(0, str(GET))
import agb_suh2021  # noqa: E402
import gaia_dr3_variability_sos_vizier as sos  # noqa: E402


class _Table:
    def __init__(self, df):
        self.df = df

    def __len__(self):
        return len(self.df)

    def to_pandas(self):
        return self.df


class _TableList:
    """What astroquery returns: keyed by table id, only the tables that have rows; ``[0]`` is the first one."""

    def __init__(self, tables):
        self.tables = dict(tables)

    def keys(self):
        return self.tables.keys()

    def __getitem__(self, k):
        return self.tables[k] if isinstance(k, str) else list(self.tables.values())[k]

    def __bool__(self):
        return bool(self.tables)


def _agb(rows):
    return {tid: _Table(pd.DataFrame(df)) for tid, df in rows.items()}


AGB_ROWS = {
    "J/ApJS/256/43/table9": {"IRAS": ["12345+0000"], "RAdeg": [266.4], "DEdeg": [-28.9]},
    "J/ApJS/256/43/table11": {"WISEA": ["J1", "J2"], "RAdeg": [266.41, 266.42], "DEdeg": [-28.91, -28.92]},
}


def test_the_four_agb_tables_are_one_request(monkeypatch):
    calls = []

    def vizier_query(catalog, ra, dec, radius, *a):
        calls.append(catalog)
        return _TableList(_agb(AGB_ROWS))

    monkeypatch.setattr(agb_suh2021, "vizier_query", vizier_query)
    d = agb_suh2021.fetch(266.4, -28.9, 10.0)
    assert calls == [list(agb_suh2021.TABLES)]  # one request, the four tables together
    assert len(d) == 3 and set(d.agb_subclass) == {"OAGB_IRAS", "OAGB_WISE"} and set(d.agb_query_status) == {"ok"}
    assert d.catalog_object_id.str.startswith(("OAGB_IRAS:", "OAGB_WISE:")).all()


def test_an_empty_cone_is_one_request_and_no_error(monkeypatch):
    calls = []
    monkeypatch.setattr(agb_suh2021, "vizier_query", lambda c, *a: calls.append(c) or _TableList({}))
    d = agb_suh2021.fetch(150.1, 2.2, 6.0)
    assert len(calls) == 1 and d.empty


def test_a_failed_joint_request_falls_back_to_one_request_per_table(monkeypatch):
    calls = []

    def vizier_query(catalog, ra, dec, radius, *a):
        calls.append(catalog)
        if isinstance(catalog, list):
            raise RuntimeError("the mirrors answered 500")
        return _TableList({catalog: _agb(AGB_ROWS)[catalog]} if catalog in AGB_ROWS else {})

    monkeypatch.setattr(agb_suh2021, "vizier_query", vizier_query)
    d = agb_suh2021.fetch(266.4, -28.9, 10.0)
    assert calls[0] == list(agb_suh2021.TABLES) and calls[1:] == list(agb_suh2021.TABLES)  # then the old way
    assert len(d) == 3 and set(d.agb_query_status) == {"ok"}


def test_a_table_that_fails_is_recorded_not_dropped(monkeypatch):
    def vizier_query(catalog, ra, dec, radius, *a):
        if isinstance(catalog, list) or catalog.endswith("table12"):
            raise RuntimeError("down")
        return _TableList({catalog: _agb(AGB_ROWS)[catalog]} if catalog in AGB_ROWS else {})

    monkeypatch.setattr(agb_suh2021, "vizier_query", vizier_query)
    d = agb_suh2021.fetch(266.4, -28.9, 10.0)
    assert len(d) == 3 and set(d.agb_query_status) == {"error:table12:RuntimeError"}  # partial: not cached


SOS_FRAMES = {
    "I/358/vrrlyr": {
        "Source": [1, 2],
        "Class": ["RRAB", "RRC"],
        "PF": [0.5, 0.3],
        "P1O": [None, None],
        "ptpG": [0.9, 0.5],
        "RA_ICRS": [80.0, 80.1],
        "DE_ICRS": [-69.7, -69.8],
        "extra": ["x", "y"],
    },
    "I/358/vcep": {
        "Source": [3],
        "Class": ["DCEP"],
        "SubClass": ["F"],
        "ModeClass": ["F"],
        "PF": [4.0],
        "P1O": [None],
        "ptpG": [0.4],
        "RA_ICRS": [80.2],
        "DE_ICRS": [-69.9],
    },
}


def test_the_sos_products_are_one_request_with_every_column(monkeypatch):
    calls = []

    def vizier_query(catalog, ra, dec, radius, columns=("**",)):
        calls.append((catalog, tuple(columns)))
        return _TableList({k: _Table(pd.DataFrame(v)) for k, v in SOS_FRAMES.items()})

    monkeypatch.setattr(sos, "vizier_query", vizier_query)
    monkeypatch.setattr(sos, "vizier_cone", lambda *a, **k: pytest.fail("the joint answer is used"))
    d = sos.fetch(80.9, -69.75, 20.0)
    assert calls == [(["I/358/vrrlyr", "I/358/vcep", "I/358/vlpv"], ("**",))]
    assert sorted(d.gaia_variability_sos_kind.unique()) == ["CEPHEID", "RR_LYRAE"] and len(d) == 3


def test_one_requested_product_keeps_its_columns_and_a_failed_joint_request_asks_one_by_one(monkeypatch):
    seen = []
    monkeypatch.setattr(sos, "vizier_query", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))

    def cone(table, ra, dec, radius, columns):
        seen.append(table)
        return pd.DataFrame(SOS_FRAMES[table]) if table in SOS_FRAMES else None

    monkeypatch.setattr(sos, "vizier_cone", cone)
    d = sos.fetch(80.9, -69.75, 20.0)
    assert seen == ["I/358/vrrlyr", "I/358/vcep", "I/358/vlpv"] and len(d) == 3
    seen.clear()
    sos.fetch(80.9, -69.75, 20.0, kinds=("rr",))  # a single product: no joint request
    assert seen == ["I/358/vrrlyr"]
