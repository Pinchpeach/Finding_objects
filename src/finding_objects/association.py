"""Cross-band counterpart association helpers.

New science code should use LR/posterior APIs. Legacy wrappers remain for API
compatibility and are explicitly positional diagnostics, not calibrated
counterpart probabilities.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class CounterpartEvidence:
    source_band: str
    counterpart_band: str
    separation_arcsec: float
    beam_fwhm_arcsec: float
    positional_error_arcsec: float = 0.0

def chance_coincidence_probability(rho,r):
    return 1-math.exp(-max(float(rho),0)*math.pi*float(r)*float(r))

def likelihood_ratio(r,sigma,rho):
    sigma=max(float(sigma),1e-9); rho=max(float(rho),1e-15)
    return math.exp(-.5*(float(r)/sigma)**2)/(2*math.pi*sigma*sigma*rho)

def posterior_counterpart_probability(lr,prior):
    q=min(max(float(prior),1e-6),1-1e-6)
    odds=float(lr)*q/(1-q)
    return odds/(1+odds)

def association_score(evidence: CounterpartEvidence):
    sigma=max(evidence.beam_fwhm_arcsec/2.355, evidence.positional_error_arcsec, 1e-9)
    score=math.exp(-.5*(evidence.separation_arcsec/sigma)**2)
    return {"positional_score":score,"positional_likelihood":score,
            "separation_arcsec":evidence.separation_arcsec,
            "sigma_arcsec":sigma,
            "warning":"Legacy positional diagnostic only; not a calibrated counterpart probability."}

def classify_association(*args,covered=True,service_responded=True,candidate_count=1,posterior_probability=None):
    # Backward-compatible positional API: (separation, search_radius, score)
    if args:
        separation=float(args[0]) if len(args)>0 else 0.0
        search_radius=float(args[1]) if len(args)>1 else 0.0
        legacy_score=args[2] if len(args)>2 else None
        if not service_responded: return "no_response"
        if not covered: return "not_covered"
        if candidate_count<=0: return "no_counterpart"
        if candidate_count>1: return "ambiguous"
        if separation<=search_radius and legacy_score is not None and float(legacy_score)>=0.5: return "matched"
        return "ambiguous"
    if not service_responded:return "no_response"
    if not covered:return "not_observed"
    if candidate_count<=0:return "observed_no_counterpart"
    if posterior_probability is not None and posterior_probability>=.9:return "probable_counterpart"
    if posterior_probability is not None and posterior_probability<.2:return "likely_not_same_object"
    return "ambiguous"
