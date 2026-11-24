"""SIMBAD cone-search collector. Reference metadata.

Besides the basic fields, the literature behind each object is attached
(best effort; a failed reference query leaves these columns empty and never
fails the collector):
  simbad_otype_label     readable object type (SIMBAD otypedef)
  simbad_nbref           number of papers citing the object
  simbad_ref_bibcodes    up to 3 papers that discuss the object most
                         (has_ref.obj_freq), then most recent; '|' separated
  simbad_ref_titles / simbad_ref_years   matching titles and years

Requests (2.60.0).  Every request waits 3-5 s first (throttle.py), so a search takes
as long as it has requests.  astroquery's ``add_votable_fields`` + ``query_region`` + the
reference and ``otypedef`` queries were 8 requests for an empty cone and 8 + one per 300
objects otherwise (NGC 4522 2': 9, COSMOS 2' 3,226 objects: 19; 35-80 s in the 2026-11-23
probe), of which only the cone query and the references hold data:
  * 2 requests: the ``capabilities`` of the failing Strasbourg server (``/sim-tap/capabilities``,
    then pyvo's ``/capabilities``);
  * 4: TAP metadata that only validates field names (``capabilities`` for the row limit, the
    table list, the columns of ``basic``, the filter list);
  * 1: the cone query;  1: ``otypedef``;  1 per 300 objects: ``has_ref`` / ``ref`` rows.
Now the cone query is one synchronous TAP POST with the same columns and the same ``CONTAINS``
predicate astroquery builds, the object-type labels come from the same query (LEFT JOIN
``otypedef``: ``otype`` is unique there), and the references of all objects of the cone from
one more (the same predicate in a sub-query, no list of names): 2 requests (1 for an empty cone).
The predicate written straight into the join took 6.7-8.5 s on the server (COSMOS 2', 3,226
objects, 10,136 rows), as a sub-query 1.7 s for the same rows (2026-11-23).  A server
that failed is asked last for the failure memory (archive_cache.note_source).  A query that
SIMBAD rejects (HTTP 400, e.g. a renamed column) falls back to the astroquery path of 2.54.0.
"""

from pathlib import Path
import io
import sys

import pandas as pd

if str(Path(__file__).resolve().parent) not in sys.path:  # loaded by file path elsewhere
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_cache  # noqa: E402

CATALOG = "SIMBAD"
# CDS Strasbourg, then its official mirror at Harvard-CfA (the two servers of
# astroquery's simbad.conf.servers_list; same database, synchronised by CDS).
# 2.54.0: on 2026-11-14/15 Strasbourg answered 404 to every SIMBAD request
# (TAP capabilities included) and every search lost SIMBAD.
SERVERS = ("simbad.cds.unistra.fr", "simbad.harvard.edu")
FIELDS = ("otype", "sp", "plx", "pmra", "pmdec", "rvz_redshift")  # astroquery path
TAP_SYNC = "https://{server}/simbad/sim-tap/sync"
MAXREC = 2_000_000  # SIMBAD's hard limit (its TAP capabilities); astroquery's query_region asks the same
CONNECT_TIMEOUT_S, READ_TIMEOUT_S = 10.0, 120.0
# References of a cone with more objects than this are not asked (2.60.0 review).  They are optional (not used by
# the classification) and their answer is objects x papers with titles: COSMOS 10' (59,540 objects) peaked at
# 788 MB with them, 20' (192,486) at 1.9 GB (WORK_REPORT_2026-11-23d.md 2.3), next to the other collectors of
# the search in the desktop app.  The measured 10' case is kept; beyond it only the cone rows are fetched.
REFERENCE_MAX_OBJECTS = 60_000
# The columns astroquery 0.4.11 selects for ``add_votable_fields("otype", "sp", "plx", "pmra", "pmdec",
# "rvz_redshift")`` (its query payload, 2026-11-23), in its order.
MAIN_COLUMNS = (
    "main_id",
    "ra",
    "dec",
    "coo_err_maj",
    "coo_err_min",
    "coo_err_angle",
    "coo_wavelength",
    "coo_bibcode",
    "pmra",
    "pmdec",
    "rvz_redshift",
    "otype",
    "sp_type",
    "sp_qual",
    "sp_bibcode",
    "plx_value",
)


class _ServerFailed(RuntimeError):
    """The server gave no usable answer (404 / 5xx / refused / timeout / not a VOTable): its mirror is asked."""


class _QueryRejected(RuntimeError):
    """SIMBAD answered 400 or QUERY_STATUS ERROR: the query is wrong for it, not the server."""


def _infos(votable):
    return [(str(i.name), str(i.value), str(i.content or "")) for r in votable.resources for i in r.infos]


def _tap_sync(server, adql, maxrec=MAXREC):
    """(astropy Table, overflow) of one synchronous TAP query to ``server`` (one request)."""
    import requests
    from astropy.io.votable import parse

    try:
        resp = requests.post(
            TAP_SYNC.format(server=server),
            data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "MAXREC": maxrec, "QUERY": adql},
            timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
        )
    except requests.exceptions.RequestException as exc:  # refused, DNS, connect / read timeout
        raise _ServerFailed(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
    if resp.status_code not in (200, 400):  # 404 (Strasbourg since 2026-11-15), 5xx, 429 ...: the server
        raise _ServerFailed(f"HTTP {resp.status_code}")
    try:
        votable = parse(io.BytesIO(resp.content))
        infos = _infos(votable)
    except Exception as exc:  # an HTML maintenance page with status 200, a cut answer
        if resp.status_code == 400:
            raise _QueryRejected("HTTP 400") from exc
        raise _ServerFailed(f"HTTP 200, not a VOTable ({type(exc).__name__})") from exc
    errors = [c for n, v, c in infos if n == "QUERY_STATUS" and v == "ERROR"]
    if resp.status_code == 400 or errors:  # the query is wrong for SIMBAD: not a reason to ask the mirror
        raise _QueryRejected((errors or ["HTTP 400"])[0][:200])
    overflow = any(n == "QUERY_STATUS" and v == "OVERFLOW" for n, v, _ in infos)
    return votable.get_first_table().to_table(use_names_over_ids=True), overflow


def _cone_numbers(ra, dec, radius_arcmin):
    """Centre and radius in degrees exactly as astroquery's query_region writes them into its ADQL."""
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    center = SkyCoord(ra * u.deg, dec * u.deg)
    return center.ra.deg, center.dec.deg, (radius_arcmin * u.arcmin).to(u.deg).value


def _cone_predicate(table, c_ra, c_dec, r_deg):
    return f"CONTAINS(POINT('ICRS', {table}.ra, {table}.dec), CIRCLE('ICRS', {c_ra}, {c_dec}, {r_deg})) = 1"


def _main_adql(c_ra, c_dec, r_deg):
    cols = ", ".join(f'basic."{c}"' for c in MAIN_COLUMNS)
    return (
        f'SELECT {cols}, otypedef."description" AS otype_label FROM basic '
        f'LEFT JOIN otypedef ON basic."otype" = otypedef."otype" WHERE {_cone_predicate("basic", c_ra, c_dec, r_deg)}'
    )


def _references_adql(c_ra, c_dec, r_deg):
    return (
        'SELECT b.main_id, b.nbref, r.bibcode, r."year" AS ref_year, r.title, h.obj_freq '
        "FROM basic AS b JOIN has_ref AS h ON h.oidref=b.oid JOIN ref AS r ON r.oidbib=h.oidbibref "
        f'WHERE b.oid IN (SELECT basic.oid FROM basic WHERE {_cone_predicate("basic", c_ra, c_dec, r_deg)})'
    )


def _ordered_servers():
    """Strasbourg first, unless it failed within the failure memory: then the mirror (stable order)."""
    return sorted(SERVERS, key=lambda h: archive_cache.source_down(f"simbad:{h}"))


def _query(server, ra, dec, radius_arcmin):
    """The astroquery path (2.54.0): the fallback when SIMBAD rejects the direct query."""
    from astroquery.simbad import Simbad
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    s = Simbad()
    s.server = server  # before add_votable_fields, which already asks the TAP service
    s.add_votable_fields(*FIELDS)
    return s, s.query_region(SkyCoord(ra * u.deg, dec * u.deg), radius=radius_arcmin * u.arcmin)


def _query_astroquery(ra, dec, radius_arcmin):
    last = None
    for server in SERVERS:
        try:
            s, t = _query(server, ra, dec, radius_arcmin)
            return server, s, t
        except Exception as exc:  # 404 / 5xx / refused / timeout: the mirror
            print(f"[simbad] {server}: {type(exc).__name__}: {str(exc)[:160]}", flush=True)
            last = exc
    raise last


def _query_direct(ra, dec, radius_arcmin):
    """(server, main table with ``otype_label``, cone numbers) from one TAP POST; the mirror when a server fails."""
    c_ra, c_dec, r_deg = _cone_numbers(ra, dec, radius_arcmin)
    last = None
    for server in _ordered_servers():
        key = f"simbad:{server}"
        try:
            table, overflow = _tap_sync(server, _main_adql(c_ra, c_dec, r_deg))
        except _ServerFailed as exc:
            print(f"[simbad] {server}: {exc}", flush=True)
            archive_cache.note_source(key, False)
            last = exc
            continue
        archive_cache.note_source(key, True)
        if overflow:  # more objects than SIMBAD's row limit: a partial list must not look complete
            raise RuntimeError(f"SIMBAD cone has more than {MAXREC} objects")
        return server, table, (c_ra, c_dec, r_deg)
    raise last


def fetch(ra, dec, radius_arcmin):
    try:
        server, table, cone = _query_direct(ra, dec, radius_arcmin)
        s = None
    except _QueryRejected as exc:
        print(f"[simbad] TAP rejected the direct query ({exc}); astroquery path", flush=True)
        server, s, table = _query_astroquery(ra, dec, radius_arcmin)
        cone = None
    if table is None:
        return pd.DataFrame(columns=["catalog", "catalog_object_id", "object_name", "ra", "dec"])
    df = table.to_pandas()
    low = {str(c).lower(): c for c in df.columns}
    idc = low.get("main_id")
    rac = low.get("ra")
    dcc = low.get("dec")
    if not all([idc, rac, dcc]):
        raise KeyError(f"SIMBAD required columns missing; got {list(df.columns)}")
    rv = pd.to_numeric(df[rac], errors="coerce")
    dv = pd.to_numeric(df[dcc], errors="coerce")
    bad = rv.isna() | dv.isna()
    if bad.any():
        # Only the rows that are not numeric degrees are sexagesimal: re-parsing
        # every row as hours turned "150.1" into 150.1 h (2.19.0).
        # Parsed row by row (2.23.0): one empty value failed the whole bulk parse.
        from _catalog_utils import coordinates

        pr, pd_ = coordinates(df.loc[bad], [rac], [dcc])
        rv = rv.copy()
        dv = dv.copy()
        rv[bad] = pr
        dv[bad] = pd_
    df["ra_raw"] = df[rac]
    df["dec_raw"] = df[dcc]
    df[rac] = rv
    df[dcc] = dv
    df.insert(0, "catalog", CATALOG)
    df.insert(1, "catalog_object_id", df[idc].astype("string"))
    df.insert(2, "object_name", df[idc].astype("string"))
    if rac != "ra":
        df.insert(3, "ra", rv)
    if dcc != "dec":
        df.insert(4 if "ra" in df else 3, "dec", dv)
    df = df.drop_duplicates("catalog_object_id", keep="last").reset_index(drop=True)
    df["simbad_server"] = server
    label = df.pop("otype_label") if "otype_label" in df else None  # direct path: the object-type labels
    try:
        if s is None:  # the references are one more query
            df = _attach_references_cone(server, df, cone, label)
        else:
            df = _attach_references(s, df)
    except Exception as exc:  # reference metadata is optional
        df["simbad_reference_status"] = "error:" + type(exc).__name__
    # *_query_status is what archive_cache.cacheable() checks: a failed
    # reference / object-type lookup must not be cached for LIVE_TTL_DAYS.
    st = df["simbad_reference_status"].astype(str)
    # A cone whose references were skipped (REFERENCE_MAX_OBJECTS) is not cached either (PR #76 review):
    # archive_cache serves smaller cones from a containing one, which would then lack references a search of
    # their own size gets.  Its rows are complete; only the cache leaves it out.
    df["simbad_reference_query_status"] = st.where(st.str.startswith(("error", "skipped")), "ok")
    return df


def _adql_list(values):
    return ",".join("'" + str(v).replace("'", "''") + "'" for v in values)


_OTYPE_LABELS = None


def _otype_labels(s):
    """SIMBAD otypedef table (static): fetched once per process; a failure
    raises so the result is marked partial and not cached."""
    global _OTYPE_LABELS
    if _OTYPE_LABELS is None:
        od = s.query_tap("SELECT otype, label, description FROM otypedef").to_pandas()
        _OTYPE_LABELS = dict(zip(od["otype"].astype(str), od["description"].astype(str)))
    return _OTYPE_LABELS


def _attach_references(s, df, chunk=300, per_object=3):
    """The astroquery path: ``has_ref`` rows of ``chunk`` objects per query."""
    ids = df["catalog_object_id"].astype(str).tolist()
    rows = []
    for i in range(0, len(ids), chunk):
        part = _adql_list(ids[i : i + chunk])
        q = (
            'SELECT b.main_id, b.nbref, r.bibcode, r."year" AS ref_year, r.title, h.obj_freq '
            "FROM basic AS b JOIN has_ref AS h ON h.oidref=b.oid JOIN ref AS r ON r.oidbib=h.oidbibref "
            f"WHERE b.main_id IN ({part})"
        )
        t = s.query_tap(q)
        if t is not None and len(t):
            rows.append(t.to_pandas())
    labels = _otype_labels(s)
    df["simbad_otype_label"] = df.get("otype", pd.Series(index=df.index, dtype=object)).astype(str).map(labels)
    return _merge_references(df, pd.concat(rows, ignore_index=True) if rows else None, per_object)


def _attach_references_cone(server, df, cone, label, per_object=3):
    """The direct path: the object-type labels of the cone query and the ``has_ref`` rows of every object of
    the cone from one query (the cone query's predicate, no ``IN`` list of names)."""
    df["simbad_otype_label"] = label.to_numpy() if label is not None else None
    if df.empty:  # nothing in the cone: no request
        return _merge_references(df, None, per_object)
    if len(df) > REFERENCE_MAX_OBJECTS:  # memory of an objects x papers answer (see REFERENCE_MAX_OBJECTS)
        df["simbad_reference_status"] = f"skipped:more_than_{REFERENCE_MAX_OBJECTS}_objects"
        return df
    table, overflow = _tap_sync(server, _references_adql(*cone))
    if overflow:
        raise RuntimeError(f"SIMBAD references exceed {MAXREC} rows")
    return _merge_references(df, table.to_pandas() if len(table) else None, per_object)


def _merge_references(df, r, per_object=3):
    if r is None or not len(r):
        df["simbad_reference_status"] = "no_references"
        return df
    r = r.copy()
    r.columns = [str(c).lower() for c in r.columns]
    r["obj_freq"] = pd.to_numeric(r.get("obj_freq"), errors="coerce").fillna(0)
    r["ref_year"] = pd.to_numeric(r.get("ref_year"), errors="coerce")
    # Papers with the same obj_freq and year (10 % of the objects of COSMOS 2' have a tie inside their top 3) were
    # taken in the order the server happened to answer; the bibcode now decides, so a run does not depend on it.
    r["bibcode"] = r["bibcode"].astype(str)
    r = r.sort_values(["main_id", "obj_freq", "ref_year", "bibcode"], ascending=[True, False, False, True])
    top = r.groupby("main_id").head(per_object).groupby("main_id")
    agg = pd.DataFrame(
        {
            "simbad_nbref": r.groupby("main_id")["nbref"].first(),
            "simbad_ref_bibcodes": top["bibcode"].agg(lambda x: "|".join(map(str, x))),
            "simbad_ref_titles": top["title"].agg(lambda x: "|".join(str(v).replace("|", "/") for v in x)),
            "simbad_ref_years": top["ref_year"].agg(lambda x: "|".join(str(int(v)) if v == v else "" for v in x)),
        }
    )
    df = df.merge(agg, left_on="catalog_object_id", right_index=True, how="left")
    df["simbad_reference_status"] = "ok"
    return df


def save(df, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.drop_duplicates("catalog_object_id", keep="last").to_csv(path, index=False)
