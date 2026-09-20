"""Cross-band counterpart association helpers."""
from __future__ import annotations
import math
def chance_coincidence_probability(rho,r): return 1-math.exp(-max(rho,0)*math.pi*r*r)
def likelihood_ratio(r,sigma,rho):
 sigma=max(float(sigma),1e-9); rho=max(float(rho),1e-15)
 return math.exp(-.5*(r/sigma)**2)/(2*math.pi*sigma*sigma*rho)
def posterior_counterpart_probability(lr,prior):
 q=min(max(float(prior),1e-6),1-1e-6); odds=lr*q/(1-q); return odds/(1+odds)
def classify_association(*,covered=True,service_responded=True,candidate_count=1,posterior_probability=None):
 if not service_responded:return "no_response"
 if not covered:return "not_observed"
 if candidate_count<=0:return "observed_no_counterpart"
 if posterior_probability is not None and posterior_probability>=.9:return "probable_counterpart"
 if posterior_probability is not None and posterior_probability<.2:return "likely_not_same_object"
 return "ambiguous"
