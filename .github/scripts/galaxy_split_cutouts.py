"""Legacy Surveys DR10 image cutouts of the "galaxy split" cases (2.33.1 review).

Reads <work>/galaxy_split_cases.csv (diag_association.py section C) and
<work>/source_association.csv, fetches a 25" grz cutout around each LS galaxy
from the Legacy Surveys viewer and marks every catalogue detection on it:
LS (green +), Pan-STARRS1 (red circle; the case's PS1-only row thick),
Gaia DR3 (cyan x), SDSS (yellow square).  North up, east left.  One mosaic
per field, written to <out>/<tag>.png with the case table next to it.

usage: python galaxy_split_cutouts.py WORK OUT_DIR TAG
"""

import io
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, "v2/Get_data")
import throttle  # noqa: E402

throttle.install()

work, out, tag = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
cases = pd.read_csv(work / "galaxy_split_cases.csv")
a = pd.read_csv(work / "source_association.csv", low_memory=False)
objs = pd.read_csv(work / "classified_objects.csv", usecols=["object_id", "pan_starrs1_dr2_meanobject__nDetections"], low_memory=False)
NDET = objs.set_index("object_id")["pan_starrs1_dr2_meanobject__nDetections"]
URL = "https://www.legacysurvey.org/viewer/cutout.jpg"
SIZE, PIX = 120, 0.131  # pixels, arcsec/pixel (half the DECam pixel) -> 15.7"
HALF = SIZE * PIX / 2
STYLE = {
    "DESI Legacy Surveys DR10": dict(marker="+", color="lime", s=90, lw=1.5),
    "Pan-STARRS1 DR2 MeanObject": dict(marker="o", facecolors="none", edgecolors="red", s=70, lw=1.0),
    "Gaia DR3": dict(marker="x", color="cyan", s=50, lw=1.2),
    "SDSS DR18 PhotoObj": dict(marker="s", facecolors="none", edgecolors="yellow", s=60, lw=1.0),
}

cases = cases.sort_values(["verdict", "case", "sep"]).reset_index(drop=True)
n = len(cases)
cols = 5
rows = max(1, int(np.ceil(n / cols)))
fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 4.6 * rows), squeeze=False)
for ax in axes.flat:
    ax.axis("off")
for i, c in cases.iterrows():
    ax = axes.flat[i]
    ra0, de0 = float(c.ls_ra), float(c.ls_dec)
    try:
        r = requests.get(URL, params={"ra": f"{ra0:.7f}", "dec": f"{de0:.7f}", "layer": "ls-dr10", "pixscale": PIX, "size": SIZE}, timeout=60)
        r.raise_for_status()
        img = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))
        ax.imshow(img, extent=[HALF, -HALF, -HALF, HALF], origin="upper")
    except Exception as exc:
        ax.text(0, 0, f"no image\n{type(exc).__name__}", ha="center", va="center", fontsize=7)
        ax.set_xlim(HALF, -HALF)
        ax.set_ylim(-HALF, HALF)
    cosd = np.cos(np.radians(de0))
    for cat, st in STYLE.items():
        g = a[a.catalog.eq(cat)]
        dx = (g.ra.to_numpy() - ra0) * cosd * 3600
        dy = (g.dec.to_numpy() - de0) * 3600
        k = (np.abs(dx) < HALF) & (np.abs(dy) < HALF)
        ax.scatter(dx[k], dy[k], **st)
        if cat == "Pan-STARRS1 DR2 MeanObject":  # label each PS1 row with its detection count
            for x, y, oid in zip(dx[k], dy[k], g.object_id.to_numpy()[k]):
                nd = NDET.get(oid)
                ax.text(x - 0.35, y + 0.35, f"{nd:g}" if pd.notna(nd) else "?", color="red", fontsize=7, weight="bold")
    ax.scatter([(c.ps1_ra - ra0) * cosd * 3600], [(c.ps1_dec - de0) * 3600], marker="o", facecolors="none", edgecolors="red", s=220, lw=2.2)
    ax.set_xlim(HALF, -HALF)
    ax.set_ylim(-HALF, HALF)
    ax.axis("on")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        f"#{i} {c.case[:9]} | {str(c.verdict)[:14]}\n"
        f"sep {c.sep:.2f}\" r/re {c.r_over_shape_r} nDet {c.nDet:g}\n"
        f"extra->{c.ps1_obj_class}  PS1 nDet:Kron-LS {c.ps1_rows_ndet_kron_minus_ls}",
        fontsize=7,
    )
fig.suptitle(f"{tag}: LS galaxy centre; + LS, o PS1 (thick: PS1-only row), x Gaia, square SDSS; 15.7\" N up E left; red numbers = PS1 nDetections", fontsize=9)
fig.tight_layout()
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / f"{tag}.png", dpi=100)
cases.to_csv(out / f"{tag}.csv", index=False)
print(f"wrote {out / f'{tag}.png'} ({n} cases) in {time.process_time():.1f} s cpu")
