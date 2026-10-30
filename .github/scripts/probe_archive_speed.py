"""Time a Gaia DR3 TAP cone and a VizieR cone (archive health before a field rerun, 2.44.0; re-run 19:17 UTC)."""
import time

from astroquery.gaia import Gaia
from astroquery.vizier import Vizier

for ra, dec in ((185.09, -1.26), (283.76, -23.90)):
    t = time.time()
    try:
        r = Gaia.launch_job(f"SELECT TOP 5000 source_id FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},0.2))").get_results()
        print(f"Gaia TAP {ra},{dec}: {len(r)} rows {time.time() - t:.1f} s", flush=True)
    except Exception as exc:
        print(f"Gaia TAP {ra},{dec}: error {exc!r:.150} after {time.time() - t:.1f} s", flush=True)
    t = time.time()
    try:
        r = Vizier(row_limit=5000).query_region(f"{ra} {dec}", radius="12m", catalog="II/328/allwise")
        print(f"VizieR {ra},{dec}: {sum(len(x) for x in r)} rows {time.time() - t:.1f} s", flush=True)
    except Exception as exc:
        print(f"VizieR {ra},{dec}: error {exc!r:.150} after {time.time() - t:.1f} s", flush=True)
