import argparse
from .pipeline import RunConfig, run_pipeline

def main() -> None:
    p = argparse.ArgumentParser(description="Discover and catalogue astronomical source candidates.")
    p.add_argument("--ra", type=float, required=True)
    p.add_argument("--dec", type=float, required=True)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--pixscale", type=float, default=0.262)
    p.add_argument("--band", default="r")
    p.add_argument("--detection-sigma", type=float, default=5.0)
    p.add_argument("--gaia-match-arcsec", type=float, default=1.0)
    p.add_argument("--high-snr", type=float, default=10.0)
    a = p.parse_args()
    output = run_pipeline(RunConfig(
        ra=a.ra, dec=a.dec, size=a.size, pixscale=a.pixscale, band=a.band,
        detection_sigma=a.detection_sigma, gaia_match_arcsec=a.gaia_match_arcsec,
        high_snr=a.high_snr,
    ))
    print(f"Candidate catalogue: {output}")

if __name__ == "__main__":
    main()
