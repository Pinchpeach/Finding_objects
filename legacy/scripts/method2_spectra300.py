"""Method 2 spectrum stage: download SDSS spectra, save wavelength-flux SEDs, and mark atomic/metal-line positions."""
from pathlib import Path
import io, json, time
import numpy as np
import pandas as pd
import requests
from astropy.io import fits
import matplotlib.pyplot as plt
from finding_objects.classification import LINE_LIBRARY

SRC=Path("data/method2/spectroscopic_reference_objects.csv")
OUT=Path("results/method2_300_spectra")
METALS={"OIII_5007","OII_3727","NII_6583","SII_6716","SII_6731","CaII_K","CaII_H","MgII_2796","MgII_2803","NaI_D","FeII_2600","CIV_1549"}
URL="https://data.sdss.org/sas/dr18/spectro/sdss/redux/26/spectra/{plate:04d}/spec-{plate:04d}-{mjd}-{fiber:04d}.fits"

def fetch(row):
    u=URL.format(plate=int(row.plate),mjd=int(row.mjd),fiber=int(row.fiberid))
    for a in range(6):
        try:
            r=requests.get(u,timeout=90); r.raise_for_status(); return r.content,u
        except Exception:
            if a==5:return None,u
            time.sleep(min(30,2**a))

def main():
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"spectra").mkdir(exist_ok=True); (OUT/"plots").mkdir(exist_ok=True)
    src=pd.read_csv(SRC,dtype={"objid":str,"specobjid":str}); line_rows=[]; status=[]
    for _,r in src.iterrows():
        raw,url=fetch(r)
        if raw is None:
            status.append({"objid":r.objid,"status":"no_response","url":url}); continue
        try:
            with fits.open(io.BytesIO(raw),memmap=False) as h:
                d=h[1].data; wave=10**np.asarray(d["loglam"],float); flux=np.asarray(d["flux"],float)
                ivar=np.asarray(d["ivar"],float) if "ivar" in d.names else np.full(len(wave),np.nan)
            z=float(r.redshift); rest=wave/(1+z) if np.isfinite(z) else np.full(len(wave),np.nan)
            pd.DataFrame({"wavelength_observed_angstrom":wave,"wavelength_rest_angstrom":rest,"flux_1e-17_erg_s_cm2_A":flux,"ivar":ivar}).to_csv(OUT/"spectra"/f"{r.objid}.csv",index=False)
            for name,rw in LINE_LIBRARY.items():
                ow=rw*(1+z); covered=bool(wave.min()<=ow<=wave.max())
                line_rows.append({"objid":r.objid,"line":name,"element_or_ion":name.split("_")[0],"is_metal_line":name in METALS,"rest_wavelength_angstrom":rw,"expected_observed_wavelength_angstrom":ow,"covered_by_spectrum":covered})
            fig,ax=plt.subplots(figsize=(12,4)); ax.plot(wave,flux,lw=.6); ax.set_xlabel("Observed wavelength (Angstrom)"); ax.set_ylabel("Flux (1e-17 erg s-1 cm-2 Angstrom-1)"); ax.set_title(f"{r['class']} objid={r.objid} z={z:.5f}")
            ymin,ymax=np.nanpercentile(flux,[2,98]); ax.set_ylim(ymin,ymax)
            for name,rw in LINE_LIBRARY.items():
                ow=rw*(1+z)
                if wave.min()<=ow<=wave.max():
                    ax.axvline(ow,lw=.7,ls="--"); ax.text(ow,ymax,name,rotation=90,va="top",ha="right",fontsize=6)
            fig.tight_layout(); fig.savefig(OUT/"plots"/f"{r.objid}.png",dpi=140); plt.close(fig)
            status.append({"objid":r.objid,"status":"available","url":url,"n_pixels":len(wave),"wave_min":wave.min(),"wave_max":wave.max()})
        except Exception as ex:
            status.append({"objid":r.objid,"status":"parse_error","url":url,"error":str(ex)})
    st=pd.DataFrame(status); st.to_csv(OUT/"spectrum_status.csv",index=False); pd.DataFrame(line_rows).to_csv(OUT/"line_positions.csv",index=False)
    summary={"requested":len(src),"spectra_available":int((st.status=="available").sum()),"failed":int((st.status!="available").sum()),"line_position_rows":len(line_rows),"notes":["Spectrum SED is wavelength-flux, not broadband photometric SED.","Line markers are expected positions from the SDSS spectroscopic redshift; a marker is not itself a detected line.","Metal-line positions are separately tagged with is_metal_line=true."]}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
if __name__=="__main__":main()
