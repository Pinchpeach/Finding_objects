# 문헌 정합성 검토 (2026-10)

**목적**: 분류기가 쓰는 규칙·임계값·상수가 문헌과 맞는지 확인한다. 대상은 v2가 인용해 온 문헌과 2025년까지의 최신 문헌이다. 맞지 않는 곳은 고치거나 "프로젝트 정책(근거 문헌 없음, 측정치로 정함)"으로 표시한다.

**방법**
- `Preprocess`, `Classifier`, `benchmark`의 규칙·임계값·상수 약 150개를 목록으로 만들었다.
- 세 영역으로 나눠 원 문헌 본문(arXiv 또는 저널)과 대조했다. 각 보고서는 값마다 직접 확인했는지(verified), 기억으로 인용했는지(standard ref / not re-verified)를 표시한다.
  1. 위치 연관과 1차 분류
  2. 별
  3. 은하·QSO·전파·X선·현상
- 클라우드 컨테이너에서 VizieR에 접속하지 못해, X선 카탈로그의 VizieR 열 이름은 확인하지 못했다. 그래서 코드는 여러 이름을 대소문자 구분 없이 받는다.

**판정 기준**
- CONSISTENT: 값과 인용이 문헌과 일치
- PARTLY: 방향은 맞지만 값, 인용, 구현 중 일부가 다름
- INCONSISTENT: 인용 문헌 또는 1차 문헌과 모순
- NO-SOURCE: 문헌 근거 없음

## 1. 결론 요약

| 영역 | CONSISTENT | PARTLY | INCONSISTENT | NO-SOURCE |
|---|---:|---:|---:|---:|
| 연관·1차 분류 | 17 | 16 | 2 | 11 |
| 별 | 13 | 14 | 5 | 2 |
| 은하·QSO·전파·현상 | 17 | 17 | 2 | 3 |
| 합계 | 47 | 47 | 9 | 16 |

(한 칸에 판정이 둘 이상인 항목은 각각 셌다.)

**전체 결론**
- 1차 분류(STAR/GALAXY/QSO)의 골격은 문헌과 맞는다. 골격은 Gaia 천체측정 기준(Klioner+2022), 색 선택(Stern+2012, Assef+2018), 형태(Tachibana & Miller 2018, Dey+2019), 학습 기반 증거(Chaussidon+2023 방식), 학습된 로지스틱 융합과 기권(Chow 1970)이다.
- 그러나 다음 두 가지는 문헌과 어긋났다. 2.16.0에서 고쳤다.
  - **Gaia DSC 확률의 사전확률을 이중으로 셈**
  - **탐사별 위치 오차 값 몇 개**
- 세부 분류에서는 생산자(Gaia DPAC) 사용 권고와 어긋난 곳이 다섯 군데 있었다.
  - DSC 쌍성 표지(순도 0.075)
  - `is_cstar` 신뢰 조건
  - FLAME 거성 조건
  - GSP-Spec 보정
  - Suh 2021 표에 광도 확인 없음
- 은하 활동성은 판정 순서가 프로젝트 자신의 WHAN/BPT 논리와 어긋났다.
- 펄서 관련 주석 두 곳은 2.14.0에서 이미 고쳤다.
- NO-SOURCE 항목은 대부분 프로젝트 정책값이다(k = 31, 임계값 0.25 등). 측정치가 있는 것은 측정치를 함께 적고, 나머지는 교차 검증으로 정하도록 표시했다.

## 2. INCONSISTENT 항목과 처리

| 항목 | 내용 | 근거 | 처리 |
|---|---|---|---|
| DSC 사전확률 | DSC-Combmod 사후확률(별 사전확률 0.989)을 계급 균형 융합에 그대로 넣음 | Delchambre+2023 표 2, 부록 C | **2.16.0** 사전확률 제거, DESI 88.46 → 90.96 % |
| PS1 PSF | 0.83″(관측소 시상) | Chambers+2016 표 11: i 1.19″ | **2.16.0** 1.2″ |
| Assef R90 품질 조건 | S/N ≥ 3만 확인 | Assef+2018 §3: W2 S/N > 5, 포화, 은하면·은하 중심 제외 | **2.16.0** 적용 범위로 제한 |
| DSC 쌍성 표지 | binary 확률 ≥ 0.8 → 측광 쌍성 | Delchambre+2023 표 3: 순도 0.075 | **2.17.0** 수정 |
| `is_cstar` | 신뢰 조건 없이 사용 | Lebzelter+2023 권고(median_delta_wl_rp, G_BP) | **2.17.0** 수정 |
| FLAME 거성 | 조건을 잘못 옮김, RGB와 RC/AGB 구분 불가 | Gaia DR3 문서 §11.3.6 | **2.17.0** 수정 |
| GSP-Spec | 보정 없이 log g, [M/H] 사용 | Recio-Blanco+2023 §9.1 | **2.17.0** 수정 |
| Suh 2021 | 광도 확인 없이 물리적 AGB | Suh 2021 표 구성, 프로젝트 G-11 측정 | **2.17.0** 수정 |
| 은하 활동성 순서 | SDSS subclass가 WHAN/BPT보다 먼저 | Bolton+2012, Cid Fernandes+2011 | 2.18.0 |
| 펄서 주석 | 척도 높이·편광 비율 문구 | Lorimer+2006 | 2.14.0에서 수정됨 |

각 버전의 측정치는 `CHANGELOG.md`, 설계 이유는 `WORK_REPORT_2026-10-10.md` §16에 있다.

## 3. 영역별 상세 보고서

아래 세 부분은 검토 당시(2.12.0–2.13.0 코드)의 원문이다. 각 줄에 확인 방법과 권고가 있다. 처리 상태는 위 표를 따른다.

### 3.1 위치 연관과 1차 분류

### Literature review: source association and coarse STAR/GALAXY/QSO classification (v2 2.12.0)

Scope: `Preprocess/association_model.py`, `01_source_association.py`, `04_build_evidence.py`, `05_likelihood_vectors.py`, `color_knn.py`, `ls_gbm.py`, `classification_rules.csv`, `fusion_weights.json`, `benchmark/build_desi_gbm_truth.py`. Review date 2026-10-12. Repository read-only.

**How each fact was checked.** "verified" means I read the value in the paper's full text (arXiv PDF) or abstract during this review. "standard ref" means a well-known reference whose value I quote from memory and did not re-fetch. VizieR and the arXiv API were blocked from this container, so I could not check VizieR column names for the X-ray catalogues.

Verdicts: CONSISTENT = value and citation agree with the literature. PARTLY = the direction is right but the value, the citation or the implementation differs. INCONSISTENT = contradicted by the cited or primary source. NO-SOURCE = no literature basis was given or found.

---

#### 1. Positional association

| id | rule / value in code | verdict | evidence | recommendation |
|---|---|---|---|---|
| A-01 Gaia | 0.10″ fallback, 0.18″ PSF, 5″ cap, epoch 2016.0 | CONSISTENT | DR3 reference epoch J2016.0 (Lindegren+2021 A&A 649 A2, verified). Per-source ra_error/dec_error are used. | Keep. Cite Lindegren+2021 A2. |
| A-01 AllWISE | 0.50″ / 6.1″ / 8″, epoch 2010.5 | CONSISTENT | W1 PSF FWHM 6.1″ (Wright+2010 AJ 140 1868, standard ref). sigra/sigdec are used per source. | Add the Wright+2010 citation. |
| A-01 2MASS | 0.25″ / 2.5″ / 6″, epoch 2000.0 | CONSISTENT | Skrutskie+2006 AJ 131 1163 (standard ref): about 2.5″ image FWHM. err_maj is used. The survey ran 1997–2001, so epoch 2000 is fine. | Add the citation. |
| **A-01 PS1** | **PSF 0.83″**, 0.12″ fallback, no epoch | **INCONSISTENT** (PSF); PARTLY (epoch) | Chambers+2016 (arXiv:1612.05560) Table 11, verified: the median delivered PSF FWHM in the 3π survey is g 1.47, r 1.31, i 1.19, z 1.14, y 1.09″. The site DIMM median seeing is 0.84″, which is probably where 0.83 came from. PS1 DR2 mean positions are mean-epoch (about 2010–2014), but the profile has `ref_epoch=None`, so high-proper-motion stars are not propagated. | Set PSF to **1.2″** (i band) and cite Chambers+2016 Table 11. Fetch `epochMean` from PS1 and use it as ref_epoch. |
| A-01 GALEX | 0.80″ / 5.3″ / 8″, no epoch | PARTLY | Morrissey+2007 ApJS 173 682 (verified): absolute astrometry 0.49″ (NUV) and 0.59″ (FUV) RMS for S/N ≥ 10. A 5.3″ NUV FWHM is the standard value. The fetched columns include per-source `Nperr`/`Fperr`, but the code does not read them. | Keep the values and cite Morrissey+2007. Read Nperr/Fperr. Give an epoch of about 2007 (survey 2003–2012). |
| A-01 FIRST | 1.0″ / 5.0″ / 8″ | PARTLY | FIRST beam 5.4″ (Becker+1995 ApJ 450 559, standard ref). | Set PSF to 5.4″ and cite. |
| A-01 NVSS | 3″ / 45″ / 30″ | CONSISTENT | 45″ FWHM (Condon+1998 AJ 115 1693, standard ref). Position errors run from below 1″ to about 7″ near the limit, so per-source e_RA/e_Dec should be used when present. | Cite Condon+1998. Epoch about 1995. |
| A-02 TGSS | 2″ / 25″ / 25″ | CONSISTENT | Intema+2017 A&A 598 A78 (verified, arXiv:1603.04368). | Keep. |
| A-03 ZTF | 0.15″ / 2.0″ / 3″ | CONSISTENT | Bellm+2019 and Masci+2019 (arXiv:1902.01872). | Keep. Add an epoch of about 2019.5 so high-PM stars propagate. |
| A-01 Chandra CSC 2.0 | 0.6″ fallback, **fixed 0.5″ PSF** | PARTLY | CSC `err_ellipse_r0` is the **95 % confidence** radius, statistical only. Documentation adds a 0.16″ (1σ) systematic (CXC CSC column docs). The Chandra PSF grows strongly off-axis, so 0.5″ holds only on-axis. If `errMaj` is read as 1σ, σ is overestimated by about 2.45×. I could not verify the VizieR column names. | Read r0, set σ = r0/2.448 ⊕ 0.16″. Use a per-source PSF from the off-axis angle (or the CSC PSF size column). Cite Evans+2010 ApJS 189 37 and the CSC docs. |
| A-01 XMM 4XMM | 1.5″ / 6″ / 10″ | CONSISTENT | Webb+2020 A&A 641 A136 (verified, arXiv:2007.02899): POSERR = RADEC_ERR ⊕ SYSERRCC (1σ). The 1.5″ fallback equals the 3XMM default systematic. EPIC PSF is about 6″ FWHM on-axis. | Read POSERR per source and cite Webb+2020. |
| A-01 eRASS1 | 4.0″ fallback, 26″ "PSF", epoch 2020.5 | PARTLY | Merloni+2024 A&A 682 A34 (verified, arXiv:2401.17274): POS_ERR = √(1.3σ² + 0.9²) is 1σ, the distribution peaks at about 4.5″ (mean 4.6″), and the **survey-averaged PSF HEW is 30.0″**. The survey ran Dec 2019 – Jun 2020, so the epoch is about 2020.2. | Fallback 4.5″, PSF 30″ (note it is an HEW, not a FWHM), read POS_ERR per source, cite Merloni+2024. |
| **A-01 Legacy Surveys DR10** | **No profile, so DEFAULT 0.6″ / 5″ / no PSF / no epoch** | **NO-SOURCE** | Dey+2019 AJ 157 168 (verified): delivered image quality is about 1.3/1.2/1.1″ in g/r/z for DECaLS and 1.6″/1.5″ for BASS. LS rows carry `ra_ivar`/`dec_ivar` and `ref_epoch` (positions of Gaia-matched stars are at the Gaia epoch), but none of these are fetched. | Add a profile: PSF about 1.2″, σ from ra_ivar/dec_ivar with a small floor, ref_epoch per row. LS is the main photometry source, so this matters most. |
| A-04 | DEFAULT 0.6″ / 5″ | NO-SOURCE | – | Acceptable as a guard. Log a warning whenever it is used. |
| A-05 Suh 2021 IRAS | 12″ / 30″ / 45″ | PARTLY | The IRAS PSC error ellipse is typically tens of arcsec in-scan by a few arcsec cross-scan (Beichman+1988 Explanatory Supplement, standard ref). Not verified here. | Cite the IRAS Explanatory Supplement. Use the catalogue ellipse if Suh gives one. |
| A-06/A-07/A-09 | σ floors 0.02″, 0.05″, PSF/6 | NO-SOURCE | Centroid precision scales as FWHM/(2.35·S/N) (King 1983 PASP 95 163, standard ref). A fixed PSF/6 floor is conservative for bright sources. | Document as project policy. Optionally use FWHM/(2.35·S/N) ⊕ systematic. |
| A-08 / propagation | Linear tangent-plane propagation; σ grows by max(σμ)·Δt | CONSISTENT | Linear propagation is adequate for decades unless the PM is extreme or the source is near the pole (Butkevich & Lindegren 2014 A&A 570 A62, standard ref). However, propagation only happens when **both** catalogues have epochs. PS1, GALEX, FIRST, NVSS, ZTF, Chandra, XMM and LS have none, so a 1″/yr star is offset 5–20″. | Keep the method. Add epochs (above). |
| A-10 | radius = min(cap, max(0.15″, 5σ, 0.6·PSF)) | PARTLY | For a 2-D Gaussian, P(r > 5σ) = e^{−12.5} ≈ 3.7×10⁻⁶. That is reasonable, but uncited. | Document. Cite the Rayleigh tail as in Klioner+2022 Eq. 3. |
| A-11 | P_chance = 1 − exp(−πr²ρ) ≤ 0.25 | PARTLY / NO-SOURCE (0.25) | The Poisson formula is standard (e.g. Bloom+2002 AJ 123 1111, standard ref). The 0.25 cut has no source. ρ comes from the cone of the matched catalogue and does not depend on magnitude. | Keep the formula and call 0.25 project policy. Better: use ρ(m) (magnitude-dependent density) as in likelihood-ratio methods. |
| A-12 | posterior = L/(L+ρ), L = exp(−x²/2)/(2πσ²) (cited as Budavári & Szalay 2008 ApJ 679 301) | PARTLY | This is the Sutherland & Saunders 1992 (MNRAS 259 413) likelihood ratio LR = Q·f(r)/n(m) with reliability LR/(ΣLR + 1 − Q), with **Q = 1** and n(m) replaced by a constant ρ. Budavári & Szalay add an explicit prior on the match fraction. For X-ray and radio catalogues, NWAY (Salvato+2018 MNRAS 473 4937, arXiv:1705.10711, verified) is now standard. It adds colour and magnitude priors, about 95–97 % reliable on 2RXS/XMMSL2. | Add Q, the expected counterpart fraction per catalogue pair, and sum over competing candidates. For eRASS1 and XMM, consider NWAY with a W1−W2 prior, or the published eRASS1 counterpart catalogues. Cite Sutherland & Saunders 1992 next to Budavári & Szalay. |

#### 2. Gaia astrometric evidence

| id | rule | verdict | evidence | recommendation |
|---|---|---|---|---|
| AST-EXT-001 | \|(ϖ + 0.017)/σϖ\| < 5 → EXTRAGALACTIC, score 1 − x/5 | Value CONSISTENT; use as positive evidence PARTLY | The criterion is exactly Gaia-CRF3 Eq. 2 (Klioner+2022 A&A 667 A148, arXiv:2204.12574, verified): "the median parallax of −0.017 mas obtained from … QSO-like sources", with ±0.010 mas variation (Lindegren+2021 A&A 649 A4, verified). The inventory's claim that the citation is wrong is unfounded: Klioner+2022 is the right source. **However**, Klioner uses this cut only to *filter* catalogued QSO candidates. A faint star with σϖ ≈ 0.5–1 mas also passes. Because this is a sign-dropped key with prior weight 0.35, a G ≈ 20 star with x ≈ 0.4 gets about +0.85 nats toward GALAXY and QSO. | Keep the formula and cite Klioner+2022 Eq. 2 plus Lindegren+2021 A4. Emit the evidence only when it is informative (for example σϖ ≲ 0.2–0.3 mas, where a disc star would be detected), or turn it into a likelihood ratio against the expected stellar parallax at that G and b. |
| AST-EXT-002 | √((μα/σ)² + (μδ/σ)²) < 5, diagonal errors | PARTLY | Klioner+2022 Eq. 3 (verified) uses the full covariance with `pmra_pmdec_corr`: X²μ < 25. That column is not fetched (`Get_data/gaia_dr3.py` SOURCE list). | Fetch pmra_pmdec_corr and use Eq. 3. This also applies to AST-GAL-002 and the decisive rule. |
| AST-GAL-001/002 | x/(x + 5) STAR support | NO-SOURCE (the constant 5) | The 5σ pivot matches the Gaia-CRF3 5σ consistency limit. That is a defensible pairing, but it is uncited. AST-GAL-002 is fitted (support 4644). | Cite Klioner+2022 for the 5σ pivot and call the shape project policy. |
| F-06 decisive motion | ϖ or μ ≥ 10σ, reliability ≥ 0.8 (RUWE ≤ 1.75), association ≥ 0.8 → STAR | CONSISTENT (threshold); citation PARTLY | Normalised ϖ and μ of Gaia-CRF3 QSOs have SD 1.052–1.063 (5p) and 1.073–1.116 (6p) (Klioner+2022 §3, verified; the code comment credits Lindegren+2021 A2). **El-Badry, Rix & Heintz 2021 (MNRAS 506 2269, arXiv:2101.05282, verified) find σϖ reliable for G ≳ 18. Underestimates are ≤ 30 % for bright isolated sources and up to 80 % with a companion within about 4″.** The code comment ("faint-end errors underestimated by about 1.5") misstates this. Genuine large QSO PMs exist: at least 0.17 % of SDSS AGN are perturbed, often dual or lensed (Makarov & Secrest 2022, arXiv:2206.04148, verified). Galaxies can show spurious PMs from extent (Delchambre+2023 §3.2.1, verified). The measured 99.6 % / 99.0 % star purity supports the 10σ cut. | Keep 10σ. Fix the comment to cite Klioner+2022 for the widths, and El-Badry+2021 correctly (the risk is close companions, not the faint end). Use covariance (above). Add a veto when LS shows a resolved Tractor model with shape_r > ~1″ or the source is in SGA. Consider RUWE ≤ 1.4 (Lindegren+2018 technical note GAIA-C3-TN-LU-LL-124) as the decisive limit. |
| A-13 RUWE | reliability = min(1, 1.4/RUWE) | CONSISTENT | The RUWE 1.4 convention (Lindegren+2018 TN, standard ref). | Keep. Cite the TN in Preprocess as well. |

#### 3. Gaia DSC (the key question)

**Claim in the pipeline:** DSC "STAR" gets a low (prior) weight because DSC priors favour stars for faint sources.

**Finding: PARTLY CONSISTENT. The reasoning is right in spirit but wrong in detail.** Sources are Delchambre+2023 A&A 674 A31 (arXiv:2206.06710, full text verified) and Jamal & Bailer-Jones 2024 A&A 687 A258 (arXiv:2405.01340, verified).

- DSC uses a **single global prior, the same for every magnitude and latitude** (§3.2.2: "we could make the prior a function of [magnitude, latitude] … but we have not introduced this in Gaia DR3").
- The Table 2 prior values are:

  | class | prior |
  |---|---|
  | quasar | 0.000989 (1/1000 of stars) |
  | galaxy | 0.000198 (1/5000) |
  | star | 0.988728 |
  | white dwarf | 0.000198 |
  | physical binary | 0.009887 |

  The stellar family (STAR + WD + BINARY), which is what the pipeline sums, has a prior of **0.99881**.
- So the prior favours stars by about 10³ (QSO) to 5×10³ (galaxy) **at all magnitudes**, not only faint ones. It *matters* most at faint G only because the likelihoods are flat there and the posterior falls back to the prior. Delchambre §3.3 notes purity rises for G ≤ 18; Jamal & BJ 2024 find a magnitude- and latitude-dependent prior helps "mostly at the faint end".
- Combmod/Allosmod also uses **parallax, total proper motion and sin b** as GMM features (§3.2.1, verified). The DSC posterior is therefore not independent of AST-EXT and AST-GAL evidence.
- The pipeline fusion is trained on **class-balanced (equal-prior) data** (`fusion_weights.json`: training_prior about 1/3 each). Feeding prior-laden DSC posteriors into it double-counts a 1000:1 star prior. This explains why the fitted DSC STAR weight came out negative (CHANGELOG 2.11.0). It is not mere collinearity.
- Delchambre+2023 App. C gives the fix: divide each probability by its catalogue prior and renormalise (Eq. C.1).
- Separately, there is a **CSV bug**: the DSC-001 row is shifted by one field, so `likelihood_method` is "" and the weight falls to 0.25 instead of 1.0. I confirmed this with `csv.DictReader`.

| id | verdict | recommendation |
|---|---|---|
| DSC-001 STAR (sign-dropped, prior weight 0.25) | PARTLY | (1) Fix the CSV shift (move `direct_probability` into `likelihood_method`). (2) Better: strip the DSC prior per Delchambre App. C, ℓ_k = ln(P_k/π_k), and give the fusion the log-likelihood ratios ln(L_QSO/L_star) and ln(L_gal/L_star) as **linear features to fit**. The sign problem then goes away, and the one-sided prior weight is no longer needed. (3) Prefer Specmod (BP/RP only) when AST-* evidence is also present, to avoid counting astrometry twice. Alternatively, use Combmod-α (Jamal & BJ 2024). |
| DSC-001 GALAXY/QSO (fitted, about 0.16 / 0.06) | PARTLY | Same prior-stripping. Optionally add `classlabel_dsc_joint` (Specmod and Allosmod both > 0.5), which Gaia Collaboration, Bailer-Jones+2023 (arXiv:2206.05681) report gives about 95 % purity sub-samples. |

#### 4. Morphology, mid-IR, colour and machine-learning evidence

| id | rule | verdict | evidence | recommendation |
|---|---|---|---|---|
| PS1-MORPH-001/002 | iPSF − iKron > 0.05 → GALAXY, else point; 14 ≤ i ≤ 21 | CONSISTENT | Tachibana & Miller 2018 PASP 130 128001 (arXiv:1902.01935, verified §4.1) uses "iPSFMag − iKronMag > 0.05 mag" as the PS1 baseline model. Its RF (PS1 PSC) outperforms it, especially when faint. | Keep. Consider using the PS1 PSC `ps_score` (T&M 2018; Miller & Hall 2021, arXiv:2012.01544) as evidence instead. |
| LS-MORPH-001/002 | REX/EXP/DEV/SER → GALAXY, PSF → point, when max S/N(r, z) ≥ 10 | PARTLY | Tractor models are as described in Dey+2019 §8 (verified). Neither Dey+2019 nor Chaussidon+2023 gives an S/N ≥ 10 rule. Chaussidon+2023 (ApJ 944 107, arXiv:2208.08511, verified §3/§5.1) uses PSF type for QSO targets and notes that some QSOs are classified REX/extended (Δχ²/χ² < 0.015). Low-z QSO hosts are resolved, so "resolved → GALAXY" is not strictly true. The fit gives a sign-dropped GALAXY key. | Call the S/N 10 threshold project policy, or tune it on the benchmark. Add the relative χ² feature (dchisq REX vs PSF) from Chaussidon §5.1. |
| WISE-AGN-001 Stern | W1 − W2 ≥ 0.8, W2 ≤ 15.05, SNR ≥ 10; score 0.95 | PARTLY | Stern+2012 ApJ 753 30 (arXiv:1205.0811, verified): 78 % completeness and 95 % reliability in COSMOS, using **WISE preliminary/All-Sky photometry, Vega**. Assef+2018 (verified) shows that AllWISE colours differ (All-Sky flux bias, Lake+2013): on AllWISE the 0.8 cut is redder than C75 (0.71). Reliability falls at low latitude (YSOs, AGB stars, PNe), and T/Y brown dwarfs also have W1 − W2 > 0.8 (Kirkpatrick+2011 ApJS 197 19, standard ref). | Keep, but treat 0.95 as a high-latitude COSMOS number. Down-weight at \|b\| < 10° and suppress when Gaia shows significant motion. Confirm that W1mag/W2mag are AllWISE **Vega**, not the AB-converted values from units.py. |
| WISE-AGN-R90-001 | Assef R90 (0.650, 0.153, 13.86); code needs SNR1, SNR2 ≥ 3 | Coefficients CONSISTENT; quality cuts INCONSISTENT | Assef+2018 ApJS 234 23 (arXiv:1706.09901, verified Eq. 4 and §3): R90 = (0.650, 0.153, 13.86), with 90 % reliability and **17 % completeness**. The catalogue additionally requires **W2 S/N > 5**, W1 > 8 and W2 > 7 (saturation), cc_flags = 0, and **\|b\| > 10° and > 30° from the Galactic Centre**, plus masks around nearby galaxies, PNe and HII regions. The SAA region needs W2 S/N > 10. Partly mitigated: `catalog_confidence_allwise` already scales with min(SNR)/10 and zeros out cc_flags ≠ 0. | Change the gate to **W2 S/N ≥ 5** (keep W1 S/N ≥ 3, from Fig. 1). Add the saturation limits and the Galactic plane / Galactic Centre masks, or down-weight inside them. Record these in the CSV criterion. |
| PS1-QSO-Z6-001 | Bañados+2016 i-dropout | CONSISTENT (criteria) / NO-SOURCE (weight) | Bañados+2016 ApJS 227 11 (standard ref). Its kind `selection_evidence` falls back to weight 0.25. | Add the kind to WEIGHT explicitly. |
| LS-COLOR-001 | dereddened g−r, r−z, z−W1, W1−W2; clip [−3, 6] | CONSISTENT (features) / NO-SOURCE (clip) | Chaussidon+2023 (verified) uses grzW1W2 colours. The clip is data hygiene. | Document the clip as hygiene. |
| LS-CKNN-001 / PS1-CKNN-001 | kNN k = 31, colour error ≤ 0.2, r/4 magnitude axis, Laplace smoothing | PARTLY (citation wrong) / NO-SOURCE (k, 0.2, /4) | **Ball+2006 ApJ 650 497 is a decision-tree paper**, not kNN. The kNN (instance-based) paper is **Ball+2007 ApJ 663 774** (arXiv:astro-ph/0612471, verified). The magnitude axis is well supported by XDQSO (Bovy+2011 ApJ 729 141), and the stellar locus by Covey+2007. PS1 colours are not dereddened. | Cite Ball+2007 for kNN. Choose k and the /4 scale by cross-validation and record the grid. Deredden PS1 with the Schlafly & Finkbeiner 2011 (ApJ 737 103) PS1 coefficients. |
| LS-GBM-001 | HistGBM on DESI DR1 Redrock SPECTYPE (ZWARN = 0, ΔCHI2 > 25), balanced classes, LS DR9 photometry | PARTLY | (a) The feature set (10-colour-like set plus r and type) matches the DESI QSO random forest (Chaussidon+2023 §3, verified: 11 inputs, being 10 grzW1W2 colours plus r; PSF only; 16.5 < r < 23). (b) **Label noise:** Chaussidon+2023 §6.2 (verified) shows that the Redrock QSO class alone recovers only **about 80 %** of quasars. DESI's QSO catalogue adds the MgII afterburner and QuasarNET, reaching 99.2 % efficiency and 98.3 % purity. Training on Redrock alone puts about 20 % of true QSOs in GALAXY, or drops them. (c) **Selection bias:** DESI targets are colour-preselected (LRG/ELG/QSO/BGS/MWS), so the held-out 95.6 % does not carry over to untargeted sources (faint M dwarfs, faint red galaxies). (d) Trained on DR9 photometry, applied to DR10. | Relabel QSOs with the DESI logic (RR + MgII + QN, Chaussidon+2023) or a DESI DR1 QSO VAC. Report GBM accuracy on the independent SDSS benchmark by magnitude. Add a domain flag outside the DESI target colour boxes. Cite Chaussidon+2023 §6.2 for the labelling. |
| (gap) Gaia-only QSO selection | – | NO-SOURCE (missing) | Quaia (Storey-Fisher+2024 ApJ 964 69, arXiv:2306.17749, verified) cleans Gaia QSO candidates with a PM cut μ < 10^{0.4(G − 18.25)} mas/yr and G − W1 > 2.15, W1 − W2 > 0.4, BP − G > −0.3, (G − W1) + 1.2(W1 − W2) > 3.4. Hughes, Bailer-Jones & Jamal 2022 A&A 668 A99 is a Gaia + WISE classifier with priors. | For objects without LS (bright or southern sources), add a Quaia membership or Quaia-cut evidence key. |

#### 5. Fusion and abstention

| id | rule | verdict | evidence | recommendation |
|---|---|---|---|---|
| F-01 WEIGHT priors | 1.0 / 1.5 / 0.35 / 0.35 / 0.25 | NO-SOURCE | Hand-set. | Mark as project policy. Fix the DSC CSV shift. |
| F-03 | w · rel · logit(raw), clip [0.01, 0.99] | PARTLY | Weighted log-odds addition is naive-Bayes-like and assumes conditional independence. The fitted multinomial logistic handles correlated keys only for fitted ones. Unfitted, sign-dropped keys (DSC STAR, AST-EXT-001, AST-GAL-001, LS-MORPH-001 GALAXY) still add without regard to correlation. | Aim to fit every key (Gaia-only augmentation already helps). After prior-stripping, DSC can be fitted. |
| F-04 fusion | multinomial logistic, balanced, C = 1 | CONSISTENT | A standard stacking approach (Clarke+2020 A&A 639 A84 uses an RF on SDSS + WISE). The reported ECE of 0.010 / 0.023 is good. | Keep. |
| F-05 abstention | confidence ≥ 0.6, chosen on a calibration split | CONSISTENT | Chow's reject option (Chow 1970, IEEE Trans. Inf. Theory 16 41, standard ref). | Cite Chow 1970. Remove or align the stale code defaults (0.5 / 0.1). |
| F-07 | conflict abstention unless p ≥ 0.99 | NO-SOURCE (measured 19/19) | – | Project policy, keep with its measurement. |
| F-11 | Saerens+2002 EM field prior (off by default) | CONSISTENT | Saerens, Latinne & Decaestecker 2002 Neural Comput. 14 21 (standard ref). Delchambre+2023 and Jamal & BJ 2024 also argue for field-dependent priors. | Keep it off by default. Note that it is consistent with the DSC recommendation. |

#### Summary of INCONSISTENT and NO-SOURCE items

1. **PS1 PSF 0.83″ (A-01): INCONSISTENT.** The delivered median FWHM is 1.19″ in i (Chambers+2016 Table 11); 0.84″ is the site DIMM seeing. Set 1.2″ and add `epochMean`.
2. **Assef R90 quality gate S/N ≥ 3: INCONSISTENT.** Assef+2018 §3 uses W2 S/N > 5, saturation limits, cc_flags = 0, and masks \|b\| > 10° and > 30° from the Galactic Centre.
3. **DSC prior handling: PARTLY.** The prior is global (not magnitude-dependent) and favours stars at about 1000:1 and 5000:1. Strip it per Delchambre+2023 App. C and fit the result. Fix the DSC-001 CSV column shift (weight 0.25 → 1.0).
4. **AST-EXT-001 used as positive evidence:** the formula is right (Klioner+2022 Eq. 2), but it is uninformative for large σϖ. Gate it or turn it into a likelihood ratio.
5. **AST-EXT-002 / decisive rule:** use `pmra_pmdec_corr` (Klioner+2022 Eq. 3). Fix the El-Badry+2021 misattribution and cite Klioner+2022 for the widths.
6. **Colour kNN cites Ball+2006 (decision trees):** cite Ball+2007 ApJ 663 774. k = 31, colour error 0.2 and the /4 scale are NO-SOURCE, so tune them by CV. Deredden PS1 colours.
7. **LS-GBM labels:** Redrock-only QSO labels miss about 20 % of QSOs (Chaussidon+2023 §6.2). Relabel with RR + MgII + QN and validate outside DESI target selection.
8. **NO-SOURCE: Legacy Surveys association profile** (no PSF, epoch or per-source error). Also P_chance ≤ 0.25, σ floors / PSF/6, the LS-MORPH S/N 10, the WEIGHT priors, CONFLICT 0.99 and the LS colour clip. Document them as project policy or tune them.
9. Smaller value fixes:
   - eRASS1: PSF 30″ HEW and fallback error 4.5″ (Merloni+2024).
   - Chandra: r0 is a 95 % radius, plus a 0.16″ systematic.
   - FIRST beam 5.4″.
   - GALEX: per-source Nperr.
   - Association posterior: add the counterpart fraction Q (Sutherland & Saunders 1992), or use NWAY (Salvato+2018) for X-ray.

#### Sources (accessed 2026-10-12)

**Verified this session (full text or abstract):**
- Delchambre+2023, A&A 674 A31 — https://arxiv.org/abs/2206.06710
- Jamal & Bailer-Jones 2024, A&A 687 A258 — https://arxiv.org/abs/2405.01340
- Gaia Collaboration, Bailer-Jones+2023 (extragalactic content) — https://arxiv.org/abs/2206.05681
- Klioner+2022 (Gaia-CRF3), A&A 667 A148 — https://arxiv.org/abs/2204.12574
- Lindegren+2021, A&A 649 A4 — https://arxiv.org/abs/2012.01742
- Lindegren+2021, A&A 649 A2 — https://arxiv.org/abs/2012.03380
- El-Badry, Rix & Heintz 2021, MNRAS 506 2269 — https://arxiv.org/abs/2101.05282
- Makarov & Secrest 2022 — https://arxiv.org/abs/2206.04148
- Storey-Fisher+2024 (Quaia), ApJ 964 69 — https://arxiv.org/abs/2306.17749 (cites Hughes, Bailer-Jones & Jamal 2022, A&A 668 A99)
- Chaussidon+2023, ApJ 944 107 — https://arxiv.org/abs/2208.08511
- Dey+2019, AJ 157 168 — https://arxiv.org/abs/1804.08657
- Stern+2012, ApJ 753 30 — https://arxiv.org/abs/1205.0811
- Assef+2018, ApJS 234 23 — https://arxiv.org/abs/1706.09901
- Tachibana & Miller 2018, PASP 130 128001 — https://arxiv.org/abs/1902.01935
- Miller & Hall 2021 (PS1 PSC II) — https://arxiv.org/abs/2012.01544
- Chambers+2016 — https://arxiv.org/abs/1612.05560
- Morrissey+2007, ApJS 173 682 — https://arxiv.org/abs/0706.0755
- Wright+2010, AJ 140 1868 — https://arxiv.org/abs/1008.0031
- Intema+2017, A&A 598 A78 — https://arxiv.org/abs/1603.04368
- Masci+2019 — https://arxiv.org/abs/1902.01872
- Webb+2020, A&A 641 A136 — https://arxiv.org/abs/2007.02899
- Merloni+2024, A&A 682 A34 — https://arxiv.org/abs/2401.17274
- Predehl+2021, A&A 647 A1 — https://arxiv.org/abs/2010.03477
- Salvato+2018 (NWAY) — https://arxiv.org/abs/1705.10711
- Ball+2007, ApJ 663 774 — https://arxiv.org/abs/astro-ph/0612471
- CSC position columns — https://cxc.harvard.edu/csc1/columns/positions.html
- eRASS1 POS_ERR (HEASARC) — https://heasarc.gsfc.nasa.gov/W3Browse/all/erass1main.html

**Standard references quoted from memory, not re-fetched:**
- Skrutskie+2006 AJ 131 1163
- Becker+1995 ApJ 450 559
- Condon+1998 AJ 115 1693
- Evans+2010 ApJS 189 37
- Sutherland & Saunders 1992 MNRAS 259 413
- Budavári & Szalay 2008 ApJ 679 301
- Butkevich & Lindegren 2014 A&A 570 A62
- Kirkpatrick+2011 ApJS 197 19
- Bañados+2016 ApJS 227 11
- Schlafly & Finkbeiner 2011 ApJ 737 103
- Bovy+2011 ApJ 729 141
- Covey+2007 AJ 134 2398
- Chow 1970 IEEE TIT 16 41
- Saerens+2002 Neural Comput. 14 21
- Lindegren+2018 Gaia TN GAIA-C3-TN-LU-LL-124
- Bloom+2002 AJ 123 1111
- King 1983 PASP 95 163
- IRAS Explanatory Supplement (Beichman+1988)

### 3.2 별

### Literature review: stellar rules in the v2 classifier

Scope: stellar rules in `v2/Classifier` (subclass.py, axes/physical.py, axes/variability.py, branches/star.py, branches/evolved_star.py) at commit 40fab7c (2.13.0 work, VERSION file 2.12.0).
Method: read the code; checked each rule against the cited paper and against 2018-2025 work.
Papers marked **[verified]** were opened (full text, abstract or official Gaia DR3 documentation) during this review, and the quoted numbers come from them.
Papers marked **[not re-verified]** are well-known references that I cite from memory. Check them before you quote them in `LITERATURE*.md`.

Verdicts:
- **CONSISTENT**: matches the literature.
- **PARTLY**: the core is right, but there is a caveat, an uncited value or a missing recommended cut.
- **INCONSISTENT**: contradicts the cited or official source.
- **NO-SOURCE**: no literature basis, only internal measurement.

#### Summary table

| id | Rule (code) | Verdict | Key reference(s) | Recommendation |
|---|---|---|---|---|
| S-04..S-09 | Spectral type from (BP−RP)0, (g−r)0, PS1 i−z or GSP-Phot Teff on the Pecaut & Mamajek **dwarf** sequence | PARTLY | Pecaut & Mamajek 2013, ApJS 208, 9 [not re-verified] (dwarf sequence only); van Belle et al. 2021, ApJ 922, 163 [verified: G0III–M7.75III Teff scale from interferometry]; Alonso et al. 1999, A&AS 140, 261 [verified: giant Teff–colour scale] | The dwarf scale is also applied to luminosity class III and IV objects. At the same Teff a K giant is about 2–3 subtypes earlier than a dwarf. When the luminosity class is III, map Teff with a giant scale (van Belle+2021) or report the type as "dwarf-scale equivalent". The ±0.15 mag tolerance, the (g−r)0 < 1.3 cap and i−z > 0.25 are uncited; label them as internal. |
| S-11 | ΔM > 3 below the dwarf sequence → "WD region" | NO-SOURCE / internally inconsistent | Gentile Fusillo et al. 2021, MNRAS 508, 3877, Eq. 1 [verified] | The project uses two WD definitions: B-STAR-2 uses GF21 Eq. 1, S-11 uses ΔM > 3. At (BP−RP)0 = 0.5, ΔM > 3 means M_G ≳ 6.5, but GF21 means M_G > 8.5. Use GF21 Eq. 1 in both places. Hot subdwarfs fall between the two lines; see Culpan et al. 2022, A&A 662, A40 [verified]. |
| S-12 | Subdwarf VI: 1 < ΔM ≤ 3 | PARTLY | Kuiper 1939; Gizis 1997, AJ 113, 806 [not re-verified]; Culpan+2022 [verified] | Metal-poor MS stars do lie about 1–2 mag below the solar sequence, and the internal [M/H] check supports this (median −1.4). However, the window also catches WD+MS binaries, CVs and blue hot subdwarfs (sdB/sdO). Exclude (BP−RP)0 < 0.3, or cross-match the Culpan+2022 hot-subdwarf catalogue (J/A+A/662/A40). Adding a V_T > 200 km/s (halo) check would raise purity. |
| S-13/S-14 | V: ΔM > −1. IV: −2.5 < ΔM ≤ −1 with (BP−RP)0 < 1.3. Otherwise III | PARTLY | Hurley & Tout 1998 (0.75 mag binary offset) [not re-verified]; Ruiz-Dern et al. 2018, A&A 609, A116 [verified: their red-giant selection is G−Ks > 1.6 **and M_G < 4.0**] | For (BP−RP)0 ≥ 1.3, any star 1 mag above the dwarf sequence becomes "III". This includes pre-main-sequence K/M stars, which sit 1–3 mag above the MS, and overluminous young or binary dwarfs. Red giants are ≥ 3 mag above the MS at these colours. Require ΔM ≤ −3 or M_G < 4 (as Ruiz-Dern+2018) for III. Otherwise label it "IV/PMS?". This matters for the new RED_GIANT label. |
| S-15 | Giant boundary on log g: 4.0 (T ≤ 4250); 5.2 − 2.8e-4 T; 3.5 (T ≥ 6000) | CONSISTENT (with caveat) | Ciardi et al. 2011, AJ 141, 108 (arXiv:1009.1840) [verified: exact formula; "a star was considered to be a dwarf if log g ≥ …"; the overlap near log g 3.7 is "likely dominated by sub-giants"] | The formula matches. The paper is 2011 (fix the "2010/2011" docstring). The boundary splits **dwarfs from evolved stars**, with subgiants on the giant side, so log g ≤ limit means "IV or III", not strictly "III". Report "IV/III", or add log g < 3.5 for III. |
| S-16 | GSP-Spec usable when flag positions 1/4/8/13 (Teff), 2/5/8/13 (log g) and 3/6/8 ([M/H]) are 0 | PARTLY | Recio-Blanco et al. 2023, A&A 674, A29 (arXiv:2206.05541) [verified: Table 2 flag definitions; "best" = first 13 flags = 0; "medium" = ≤ 1 with KMgiantPar = 0 and fluxNoise ≤ 3]; Fouesneau et al. 2023, A&A 674, A28 [verified] | The code ignores fluxNoise (pos. 7), negFlux, nanFlux, emission, nullFluxErr (pos. 9–12), and KMgiantPar (pos. 13) for [M/H]. Adopt the paper's medium-quality definition for every parameter. |
| S-16b | GSP-Spec log g and [M/H] used **uncalibrated** | INCONSISTENT with the producer's recommendation | Recio-Blanco+2023, Sect. 9.1 and Table 3 [verified: GSP-Spec log g has a median offset of **−0.3 dex**, larger for giants. Calibration: log g_cal = log g + 0.4496 − 0.0036 log g − 0.0224 log g². [M/H] of giants (log g ≲ 1.5) is underestimated, with a polynomial correction]; Fouesneau+2023 App. A [verified: recommends these polynomial calibrations] | Apply Eq. 1 (log g) and Eq. 2 ([M/H], with Table 3 coefficients) before using the luminosity boundary, the METAL_POOR tag and the AGB log g veto. Without the calibration, luminous giants get spurious METAL_POOR tags. |
| S-17 | LAMOST LASP Teff / log g / [Fe/H] | CONSISTENT | Luo et al. 2015, RAA 15, 1095 [not re-verified] | LASP has no parameters for M types or carbon stars, so the cool end needs no extra guard. LASP [Fe/H] is grid-limited at the very-metal-poor end (≈ −2.5) [not re-verified]. Treat VERY_METAL_POOR from LASP as a lower-confidence tag. |
| T-02 | ASTROMETRIC_BINARY: RUWE > 1.4 | PARTLY | Lindegren+2018/2021 (1.4 = "good single-star fit" limit); Castro-Ginard et al. 2024, A&A, doi:10.1051/0004-6361/202450172 (arXiv:2404.14127) [verified: a **sky-varying** RUWE threshold, below 1.4 in most places, gives more complete binary samples; published in `gaiaunlimited`]; Penoyre et al. 2022 (1.25 for EDR3) [secondary citation, not re-verified]; Andriantsaralaza et al. 2022, A&A 667, A74 [verified: for AGB stars high RUWE "more likely reflects detector saturation, stellar size, or convective photocentre shifts than binarity"] | Keep 1.4 as the "astrometry unreliable" cut. For the *binary* tag, use the Castro-Ginard+2024 sky threshold (≈ 1.15–1.4). Suppress the ASTROMETRIC_BINARY tag for LPV/AGB/RED_GIANT stars with radius > ~100 R☉, where RUWE excess is not evidence of binarity. |
| T-03 / B-STAR-4 | PHOTOMETRIC_BINARY: Gaia DSC Combmod binary prob ≥ 0.8 | **INCONSISTENT** | Delchambre et al. 2023, A&A 674, A31 (arXiv:2206.06710) [verified, Table 3: physical-binary class completeness 0.002, purity 0.075 (Combmod). "Results on the 'binary' class are largely meaningless". "the purities of the white dwarf and physical binary classes are low"] | Drop the DSC-binary tag, or keep it only as raw evidence that decides nothing. The Creevey+2023 attribution of the 0.8 cut is not supported. Better binary evidence: RUWE (above), Gaia NSS tables, or the El-Badry+2021 wide-binary catalogue. |
| B-STAR-4 (WD) | DSC WD prob ≥ 0.8 alone → WD candidate when the HR locus is unavailable | PARTLY | Delchambre+2023 Table 3 [verified: WD class completeness 0.43, purity 0.25 for Combmod at the all-sky prior] | Do not route to WD on DSC alone. Require the GF21 HR locus, or the GF21 catalogue P_WD > 0.75. |
| B-STAR-2/3 | WD HR locus M_G > 6 + 5(BP−RP); quality gate ϖ/σ ≥ 4 or μ/σ > 10 | CONSISTENT (as a preselection) | Gentile Fusillo+2021, MNRAS 508, 3877 (arXiv:2106.07669) [verified: Eq. 1 is exactly G_abs > 6 + 5(BP−RP) with parallax_over_error > 1. Eqs. 6/12 are "parallax_over_error ≥ 4 or pm/pm_err > 10". The final recommended selection is P_WD > 0.75, which is ≈ 91 % pure on SDSS spectra] | The inventory doubt is resolved: the cut is GF21's own preselection. GF21's final product, however, is P_WD, and Eq. 1 "can only be considered fully inclusive for single WDs, double WDs and WDs with low-luminosity companions". Cross-match the GF21 catalogue (VizieR J/MNRAS/508/3877) and use P_WD > 0.75 when available. Fix the stale "broad gate" text in star.py:117. |
| B-STAR-5 | Gaia XP DA/DB, max prob ≥ 0.90 | PARTLY | Vincent et al. 2024, A&A 682, A5 (arXiv:2308.05572) [verified: XP neural-network classes DA/DB/DC/DO/DQ/DZ, > 90 % for DA/DB/DO, lower for DC/DQ/DZ]; Jiménez-Esteban et al. 2023, MNRAS 518, 5106 [verified: DA/non-DA from XP synthetic J-PAS photometry, > 90 %, 100 pc]; García-Zamora et al. 2023, A&A, doi:10.1051/0004-6361/202347601 (arXiv:2308.07090) [verified: random forest on XP coefficients, ~90 %] | The two-class model (trained 1:1 DA:DB) must assign every WD to DA or DB, but most WDs are DA and many are DC/DQ/DZ. Add an "other" class, or abstain outside the DB temperature range (DBs exist only above ≈ 11 kK; below ≈ 5 kK DA and DC are indistinguishable [not re-verified]). Or adopt the Vincent+2024 published classes. The 0.90 gate is internal; say so. |
| T-05 | HIGH_PM: μ > 150 mas/yr | CONSISTENT | Lépine & Shara 2005, AJ 129, 1483 (LSPM-North, μ > 0.15″/yr) [not re-verified] | None. |
| T-01 | Thin disc / thick disc / halo by V_T 40 / 60–150 / > 200 km/s | CONSISTENT | Gaia Collaboration, Babusiaux et al. 2018, A&A 616, A10 [not re-verified] | None. |
| T-06 | RED_CLUMP: M_G = 0.495 + 1.121(G−Ks−2.1); 1.8 ≤ G−Ks ≤ 2.6; \|ΔM\| ≤ 0.5; ΔM ≤ −2.5 | PARTLY | Ruiz-Dern+2018, A&A 609, A116 (arXiv:1710.05803) [verified: M_Ks = −1.606 ± 0.009; M_G = 0.495 + 1.121(G−Ks−2.1). Colour relations are calibrated over G−Ks ≈ 1.6–2.4 (up to 3.6 for some bands)]; Bovy et al. 2014, ApJ 790, 127 (APOGEE-RC) [not re-verified] | The relation is correct. The ±0.5 mag box also catches RGB-bump and lower-RGB stars; photometric RC samples are typically 20–40 % RGB contamination [not re-verified]. Keep the "candidate" wording. If spectroscopic Teff, log g and [Fe/H] exist, use the Bovy+2014 RC cuts. Cite the window as internal. |
| T-09 | METAL_POOR / VERY_METAL_POOR: spectroscopic [Fe/H] < −1 / < −2 | PARTLY | Beers & Christlieb 2005, ARA&A 43, 531 [not re-verified; the standard definitions]; Recio-Blanco+2023 [verified: giant [M/H] biased low; KMgiantPar must be 0] | The definitions are right. For GSP-Spec input, use calibrated [M/H] and require KMgiantPar = 0 (see S-16b). Note in the label that GSP-Spec gives [M/H], not [Fe/H]. |
| T-10 | EMISSION_LINE from ESP-ELS with classlabel_espels_flag ≤ 2, described in code as "P > 0.5" | PARTLY (wrong description) | Gaia DR3 documentation §11.3.7 [verified: the flag encodes **Δp between the two highest class probabilities**: 0: Δp ≥ 0.8; 1: ≥ 0.6; 2: ≥ 0.4; 3: ≥ 0.2; 4: < 0.2. Be/Herbig/T Tauri/dMe identification relies on GSP-Phot APs] | Fix the comment and basis string: flag ≤ 2 means Δp ≥ 0.4, not P > 0.5. Using the emission (not the class) is the right call and is backed by your SIMBAD check (TTauri 2 %). |
| X-PHYS-1 | Suh 2021 catalogue match → physical AGB (no luminosity check) | **INCONSISTENT** (with the project's own G-11 finding and the catalogue content) | Suh 2021, ApJS 256, 43 (VizieR J/ApJS/256/43) [verified: 11 209 O-rich + 7 172 C-rich, includes "more visual carbon stars" taken from general carbon-star lists]; Li et al. 2024, ApJS 271, 12 [verified: dwarf carbon stars by M_G > 5] | The physical axis calls all 263 sub-red-clump Suh "C-AGB" stars (dC/CH stars) AGB, while subclass.py says "not AGB". Apply the same M_Ks > −1 veto (good parallax) in `axes/physical.py` before returning AGB. |
| G-01..G-03 | Chemistry from SIMBAD C*/S*, SDSS/LAMOST carbon templates, Suh subtype | CONSISTENT | Keenan 1993; Li+2024 [verified] | None. |
| G-05/G-07 | Wesenheit ΔW = W_RP − W_KJ, logistic C/O cascade, abstain band \|p−0.5\| < 0.15 | PARTLY | Lebzelter et al. 2018, A&A 616, L13 [not re-verified]; Sanders & Matsunaga 2023, MNRAS, doi:10.1093/mnras/stad574 (arXiv:2302.10022) [verified: ΔW separates O/C well at low extinction. At E(B−V) > 3, O-rich stars enter the C-rich region and the C-rich false-discovery rate is ≈ 95 %. "Restricting to \|b\| ≳ 5 deg largely removes the highly-reddened sources"] | Add an extinction guard: abstain from photometric C/O when E(B−V) > ~2–3 or \|b\| < 5° in the bulge direction. Otherwise reddened O-rich LPVs come out carbon-rich. The 0.15 abstain band is internal; state it. |
| G-08 / X-VAR-7 | Gaia LPV `is_cstar` = 1 → C-rich (confidence 0.76) and LPV/C_STAR_CANDIDATE | **INCONSISTENT** with the producer's usage advice | Lebzelter et al. 2023, A&A 674, A15, as quoted by Sanders & Matsunaga 2023 [verified: "Lebzelter et al. advises only using the classification if 7 < median_delta_wl_rp < 11 and G_BP < 19". Without this cut there are many spurious C-rich LPVs in the midplane and bulge, which are really O-rich] | Collect `median_delta_wl_rp` (vari_long_period_variable) and use is_cstar only when 7 < median_delta_wl_rp < 11 and phot_bp_mean_mag < 19. This should raise the 0.76 precision. Refit the cascade models with the gated flag. |
| G-09 | Silicate (dusty O-rich): Ks − W3 > 1.0 | NO-SOURCE (measured internally) | Suh 2021 two-colour dust models (qualitative) | Acceptable as an internal, measured rule (98.4 % of Suh O-AGB). Label it internal. |
| G-10 | Spectroscopic log g > 3.5 → not AGB | PARTLY | Fouesneau+2023 [verified: "we caution the user against using GSP-Spec's log g values for AGBs as we find them of poorer qualities"]; Recio-Blanco+2023 [verified: KMgiantPar flag for cool K/M giants] | The direction is safe: GSP-Spec log g is biased low, so the bias makes the veto fire less often. A bad GSP-Spec solution can still veto a real AGB star. Apply the veto only with LAMOST, or with GSP-Spec Teff > 4000 K, all first 13 flags = 0 and calibrated log g. Better, require agreement with the parallax M_Ks. |
| G-11 | M_Ks > −1 (good parallax) → not AGB | CONSISTENT | Alves 2000, ApJ 539, 732 [not re-verified]; Hawkins et al. 2017, MNRAS 471, 722 [not re-verified]; Ruiz-Dern+2018 M_Ks(RC) = −1.606 [verified]; Andriantsaralaza+2022 [verified: AGB parallax errors underestimated ×2.7–5.4; RUWE ≤ 1.4 does not guarantee a good parallax] | The physics is sound: AGB stars are above the clump. Because AGB parallax errors are underestimated, use ϖ/σ ≥ 5 after inflating σ by the Andriantsaralaza+2022 factors (×2.74 for G 8–12, ×5.44 for G < 8). |
| G-12 | Dwarf carbon star: M_G > 5 | CONSISTENT | Li et al. 2024, ApJS 271, 12 [verified: "258 dwarf carbon stars by the criterion M_G > 5.0 mag"] | None. |
| G-13 | −6.2 < M_Ks ≤ −1 → "RGB or early AGB" | PARTLY | Nikolaev & Weinberg 2000, ApJ 542, 804 [not re-verified; LMC Ks tip 12.3]; Górski et al. 2018, AJ 156, 278, doi:10.3847/1538-3881/aaeacb [verified: Ks TRGB intercept ≈ −6.28, slope ≈ −0.5 per mag of (V−K); varies 0.36 mag across 3.4 < V−K < 4.1]; Serenelli et al. 2017 (J−Ks-dependent Ks tip) [secondary citation] | The Ks tip depends on colour and metallicity and is brighter for metal-rich disc giants (≈ −6.5 to −7). Use a (J−Ks)0-dependent tip. Thermally pulsing AGB stars of low mass also sit below the tip, so the label should be "RGB or AGB (below RGB tip)", not "early AGB". |
| X-PHYS RED_GIANT | Luminosity class III (CMD, else spectroscopic log g, else GSP-Phot log g with the Ciardi boundary) and Teff < 5500 K → RED_GIANT | PARTLY | Ciardi+2011 [verified: the boundary puts subgiants on the giant side]; Ruiz-Dern+2018 [verified: M_G < 4 for giants]; Recio-Blanco+2023 [verified] | Not separating RGB from AGB (or RC) without asteroseismology or a luminosity cut is scientifically right. Fix the inputs: (1) use the stricter CMD giant cut from S-13/S-14 to keep PMS stars and binaries out; (2) on the log g branch, require log g < 3.5 (true giants) or label "evolved"; (3) GSP-Spec Teff in `_teff()` is used without its flag check. The 5500 K cap is uncited but reasonable (the Ciardi+2011 giant median is 4800 K) [verified]. |
| B-EVOL-1 | FLAME RGB: 490 ≤ evolstage ≤ 1290, GSP-Phot log g < 3.5, mass < 2, age > 1 Gyr | **INCONSISTENT** (guardrails mis-transcribed, and FLAME cannot tell RGB from RC/AGB) | Gaia DR3 documentation §11.3.6 FLAME [verified: "For the masses and ages of giants (flags_flame first character = 1) results should only be used in the **1–2 M☉** range when age > 1 Gyr". Best results with flags_flame second digit 0. Models cover "ZAMS to the tip of the giant branch", so sources outside that range "will receive incorrect mass, age, and evolution stage". Evolstage > 1300 indicates bad GSP-Phot APs. Masses and ages assume solar metallicity]; Fouesneau+2023 Sect. 3.3.2 [verified: restrict giant masses to **1.0 < M < 2.0 M☉ and age > 1.5 Gyr**. Evolstage 100–420 MS, 420–490 subgiant, > 490 giant] | Add the missing lower mass bound (M ≥ 1.0), use age > 1.5 Gyr (paper) or > 1 Gyr (docs), and require flags_flame second digit 0. Name Fouesneau+2023 and the DR3 docs in place of "Gaia validation guardrails". Main point: FLAME tracks end at the RGB tip, so red-clump and AGB stars are forced onto an "RGB" stage. A FLAME "RGB" label is therefore not RGB-specific; relabel it RED_GIANT/evolved. 1290 is not a documented RGB-tip value (the docs give "typically up to 1200", flag > 1300). |
| — | Decision that FLAME masses/ages are unreliable for giants (Kepler test: median 3.3 M☉, 0.3 Gyr) | CONSISTENT | Gaia DR3 FLAME documentation [verified: giants flagged "1" ("mass, age and uncertainties need to be used with care"); "Differences are seen primarily for the more evolved giants"]; Fouesneau+2023 [verified: "it is more delicate to estimate ages for the giant stars reliably … FLAME only relies on L and Teff … significant degeneracies"] | Supported. Cite Fouesneau+2023 Sect. 3.3.2 and the DR3 docs §11.3.6 in physical.py. |
| X-VAR-2 | Gaia SOS RR Lyrae RRAB/RRC/RRD taken verbatim | CONSISTENT | Clementini et al. 2023, A&A 674, A18 [not re-verified] | None. |
| X-VAR-3 | Gaia SOS Cepheid DCEP/ACEP/T2CEP and mode taken verbatim | CONSISTENT | Ripepi et al. 2023, A&A 674, A17 [not re-verified] | None. ACEP/T2CEP typing in the field depends on PL relations and distance, so treat sub-types as lower confidence than DCEP. |
| X-VAR-4 | ZTF Chen+2020 type map (RR→RRAB, RRc, CEP→DCEP, CEPII→T2CEP, Mira, SR, EW, EA, BYDra, RSCVN, DSCT) | CONSISTENT | Chen et al. 2020, ApJS 249, 18 (arXiv:2005.08662) [verified: 11 types; "typical misclassification rate … ~2 %". Mira selected by Amp_r > 2 mag or Amp_g > 2.4 mag. "Classical and Type II Cepheids cannot be separated cleanly only based on LC information" (Chen uses luminosity and location in addition). CEP includes fundamental and first-overtone classical Cepheids] | Map CEP → DCEP without a mode, and treat the CEP/CEPII split as a lower-confidence subtype. |
| X-VAR-5 | g/r amplitude ratio ~1.4 for pulsators vs ~1.0–1.1 for contact binaries (reported only) | CONSISTENT (now with a literature source) | Kulkarni et al. 2025, arXiv:2509.03120 (J-VAR) [verified: RR Lyrae normalised ZTF amplitudes A(g) = 1.38 ± 0.22, A(r) = 0.98 ± 0.15, so A_g/A_r ≈ 1.41]; Braga et al. 2024, arXiv:2407.20813 (LSST templates, amplitude ratios) [verified: exists] | Cite Kulkarni+2025 for the 1.4. Keeping it report-only is right. |
| X-VAR-6 | Gaia LPV semi-amplitude ≥ 0.6 mag and (if a period exists) P ≥ 80 d → MIRA | PARTLY | Zhang & Sanders 2023, MNRAS, doi:10.1093/mnras/stad575 (arXiv:2302.10024) [verified: Gaia DR3 O-rich Mira selection uses 80 < P < 1000 d, G semi-amplitude ≥ 0.5 mag, "compared to Grady et al. 2019 cut at 0.43 mag". Removes alias-affected 170–200 d with amp > 1.3 and 350–400 d with amp > 1.6. YSO contamination is controlled with best_class_score]; Gaia DR3 LPV docs [model amplitude ≈ half the 5–95 % G range] | 0.6 sits in the published 0.43–0.5+ range and is measured (P 0.934 / R 0.968), so the value is fine. Add: (1) an upper period bound of 1000 d; (2) the two alias-window exclusions; (3) do **not** accept MIRA when no period is published, since Zhang & Sanders require one (the code currently accepts `freq is None`); (4) a YSO screen (Gaia vari best_class_score or IR-excess/ESP-ELS T Tauri). |
| X-VAR-8 | Gaia vari_classifier class without a minimum best_class_score | PARTLY | Rimoldini et al. 2023, A&A 674, A14, doi:10.1051/0004-6361/202245591 [verified: exists]; Zhang & Sanders 2023 [verified: best_class_score "seems an effective indicator of YSOs"] | Set a per-class minimum score or report the class as "candidate". |

#### Notes

1. **Biggest scientific errors** (contradict the producer's documentation):
   - DSC binary tag (T-03): Delchambre+2023 Table 3 gives purity 0.075.
   - Gaia `is_cstar` used without the Lebzelter+2023 reliability window (G-08, X-VAR-7).
   - FLAME RGB guardrails (B-EVOL-1): the 1.0 M☉ lower bound is missing, the age cut is softer than the paper's, flags_flame is not used, and FLAME cannot represent RC/AGB phases.
   - The physical axis calls dwarf and CH carbon stars from Suh 2021 AGB (X-PHYS-1).
   - GSP-Spec log g and [M/H] are used uncalibrated (S-16b).
2. **Checks that went the project's way:**
   - GF21 Eq. 1 is exactly the code's WD locus, and the quality gate matches GF21 Eqs. 6/12.
   - The Ciardi+2011 boundary matches the paper digit for digit.
   - The Ruiz-Dern+2018 RC relation matches.
   - Li+2024 uses M_G > 5 for dC stars.
   - The Mira 0.6 mag semi-amplitude sits next to the Grady+2019 (0.43) and Zhang & Sanders 2023 (0.5) cuts.
   - The g/r ≈ 1.4 ratio is reproduced by J-VAR (2025).
3. **RED_GIANT:** the label is the right abstraction: Gaia alone cannot separate RGB, RC and AGB below the tip. Its reliability depends on how clean the "III" input is (PMS stars and binaries at ΔM ≈ −1 to −3 for red colours; subgiants on the Ciardi log g branch).
4. **Speed:** none of the recommended fixes adds a remote query except the extra Gaia columns `median_delta_wl_rp` and `flags_flame`. Both are in tables the collectors already read. The GF21, Culpan+2022 and Vincent+2024 catalogues are VizieR cross-matches that can be cached like the other catalogues.

#### Sources (URLs)

- Ciardi et al. 2011: https://arxiv.org/abs/1009.1840
- Gentile Fusillo et al. 2021: https://arxiv.org/abs/2106.07669 ; VizieR J/MNRAS/508/3877
- Fouesneau et al. 2023 (Apsis II): https://arxiv.org/abs/2206.05992
- Gaia DR3 documentation, FLAME §11.3.6: https://gea.esac.esa.int/archive/documentation/GDR3/Data_analysis/chap_cu8par/sec_cu8par_apsis/ssec_cu8par_apsis_flame.html
- Gaia DR3 documentation, ESP-ELS §11.3.7: https://gea.esac.esa.int/archive/documentation/GDR3/Data_analysis/chap_cu8par/sec_cu8par_apsis/ssec_cu8par_apsis_espels.html
- Recio-Blanco et al. 2023 (GSP-Spec): https://arxiv.org/abs/2206.05541
- Delchambre et al. 2023 (Apsis III, DSC): https://arxiv.org/abs/2206.06710
- Castro-Ginard et al. 2024 (RUWE): https://arxiv.org/abs/2404.14127
- Andriantsaralaza et al. 2022 (AGB parallaxes): https://arxiv.org/abs/2209.03906
- Vincent et al. 2024 (XP WD classes): https://arxiv.org/abs/2308.05572 ; VizieR J/A+A/682/A5
- Jiménez-Esteban et al. 2023: https://upcommons.upc.edu/entities/publication/b613baba-9187-4c4b-a47e-4cd8bef99a5f
- García-Zamora et al. 2023: https://arxiv.org/abs/2308.07090
- Culpan et al. 2022 (hot subdwarfs): https://arxiv.org/abs/2203.07938
- Ruiz-Dern et al. 2018: https://arxiv.org/abs/1710.05803
- Górski et al. 2018 (TRGB): https://arxiv.org/abs/1810.13110
- Suh 2021: https://cdsarc.cds.unistra.fr/VizieR/ftp/J/ApJS/256/43/ReadMe
- Li et al. 2024 (LAMOST DR7 carbon stars): https://arxiv.org/abs/2312.06201
- Sanders & Matsunaga 2023 (C-rich LPVs, is_cstar): https://arxiv.org/abs/2302.10022
- Zhang & Sanders 2023 (O-rich Miras): https://arxiv.org/abs/2302.10024
- Chen et al. 2020 (ZTF periodic variables): https://arxiv.org/abs/2005.08662
- Kulkarni et al. 2025 (J-VAR RR Lyrae amplitudes): https://arxiv.org/abs/2509.03120
- Braga et al. 2024: https://arxiv.org/abs/2407.20813
- Rimoldini et al. 2023: https://arxiv.org/abs/2211.17238
- van Belle et al. 2021 (giant Teff scale): https://ipac.caltech.edu/publication/2021ApJ...922..163V
- Alonso et al. 1999 (giant Teff scale): https://iac.es/es/ciencia-y-tecnologia/publicaciones/effective-temperature-scale-giant-stars-f0-k5-ii-empirical-calibration-teff-versus

### 3.3 은하·QSO·전파·현상

### Literature consistency review: galaxies, QSOs, radio/X-ray/compact objects, phenomena

Scope: `v2/Classifier/subclass.py` (galaxy and QSO parts), `axes/compact.py`, `axes/phenomenon.py`, `axes/extragalactic.py`, `Get_data/desi_fastspec.py`, `Get_data/sdss_spectroscopy.py`, and `benchmark/pulsar_truth/pulsar_metrics.json`. Rule IDs follow `rule_inventory.md`.

Method:
- Each rule was checked against the paper it cites and against 2015–2026 work, using web search. In this container WebFetch could not resolve arxiv.org or data.desi.lbl.gov, so the original PDFs could not be opened.
- Where a value comes only from abstracts or secondary citations, the table marks it "(secondary)".
- No reference was invented. Items I could not verify say so.

Verdicts:
- CONSISTENT: the rule matches the source.
- PARTLY: the source supports the idea, but the value, scope or implementation differs.
- INCONSISTENT: the code contradicts the cited source, or the comment contradicts the measurement.
- NO-SOURCE: no literature basis is given or could be found.

#### 1. Galaxy emission-line diagnostics

| ID | Rule (code) | Verdict | Evidence | Recommendation |
|---|---|---|---|---|
| GX-05 | Kewley+2001 maximum-starburst line, y = 0.61/(x−0.47)+1.19, or x ≥ 0.47 → AGN | CONSISTENT | Kewley+2001 ApJ 556, 121. The DESI DR1 AGN/galaxy VAC uses the same Kewley/Kauffmann [N II] boundaries (DESI DR1 VAC docs). It reproduces the Portsmouth BPT for 95.1 % of galaxies (CHANGELOG). | Keep. |
| GX-07 | Kauffmann+2003 line, y = 0.61/(x−0.05)+1.3 → SF; composite in between | CONSISTENT | Kauffmann+2003 MNRAS 346, 1055 | Keep. |
| GX-06 | Seyfert/LINER split y > 1.05x + 0.45 | PARTLY | Schawinski+2007 MNRAS 382, 1415 calibrated this [N II]-diagram line on galaxies classified with [O I] or [S II] (secondary: arXiv 0912.1643; Cheng+2025 arXiv 2505.17843). Cid Fernandes+2010 gives a different S/L line. Kewley+2006 MNRAS 372, 961 recommends the [S II] and [O I] diagrams for this split. I could not verify the coefficients against the PDF. | Keep it as basis text. When [S II] or [O I] is available (the DESI VAC carries both), prefer the Kewley+2006 [S II]/[O I] Seyfert/LINER lines. Collect the [S II]6717,31 and [O I]6300 fluxes. |
| GX-04 | S/N ≥ 3 in all four BPT lines | PARTLY (citation missing, not wrong) | S/N > 3 in the four lines is the selection of Brinchmann+2004 (MNRAS 351, 1151) and Kauffmann+2003. MPA-JHU line-flux errors are known to be underestimated: the MPA-JHU DR7 documentation gives scale factors of about ×2.47 for Hα, 1.88 for Hβ, 1.57 for [O III] and 2.04 for [N II]. | Cite Brinchmann+2004. Apply the MPA-JHU error scale factors on the MPA-JHU fallback path; it affects only 1.6 % of benchmark galaxies, so the risk is low. |
| GX-02/03 | WHAN: passive if EW(Hα) and EW([N II]) < 0.5 Å; retired if EW(Hα) < 3 Å; applied before BPT | CONSISTENT | Cid Fernandes+2011 MNRAS 413, 1687 (arXiv 1012.4426): SF x < −0.4 and EW > 3; sAGN x > −0.4 and EW > 6; wAGN 3–6; RG EW < 3; passive both < 0.5 Å. The 3 Å division comes from the bimodality of EW(Hα). | Keep. On the DESI path `line_nii6584_ew` is always NaN (desi_fastspec.py:50), so the passive test can never fire for DESI. Either fetch `nii_6584_ew` or document that DESI gives only "retired". |
| GX-08 | [N II]/Hα alone: < −0.4 SF, −0.4 to −0.2 composite, > −0.2 AGN (strong if EW > 6 Å) | PARTLY | The −0.4 SF limit is Stasińska+2006 MNRAS 371, 972, and WHAN uses it too. The −0.2 AGN limit is attributed to Stasińska+2006 by later papers (OTELO III, arXiv 2002.05751), but others use −0.1 (Martínez+2010, arXiv 1001.2825). I could not open the original. This deviates from pure WHAN, which calls everything above −0.4 AGN. The deviation is justified by measurement: 104 → 19 errors. | Keep. Write it in LITERATURE as a "hybrid WHAN + Stasińska" scheme, and note that −0.2 comes from secondary sources. Account for the measured DESI-vs-SDSS [N II]/Hα offset of +0.053 dex (CHANGELOG): either correct it or widen the composite band by 0.05 on the DESI path. |
| GX-09 | Dn4000 ≥ 1.6 → old population, used only when there is no EW(Hα) | PARTLY | Kauffmann+2003 MNRAS 341, 33 places the bimodality division at Dn4000 ≈ 1.5 (narrow index of Balogh+1999 ApJ 527, 54; secondary). 1.6 is closer to the Mignoli+2005 (broad D4000) convention. Quiescent selections commonly use 1.5–1.55 (e.g. MaNGA arXiv 1611.00528). | Keep 1.6 as a deliberately conservative cut, but state in the comment that it is stricter than Kauffmann's 1.5. A better option is 1.55 with a measurement. Also, DESI FastSpecFit has `dn4000`, but `desi_fastspec.py` never fetches it, so the DESI Dn4000 path is dead code. |
| GX-01 / precedence | The SDSS `subclass` (AGN/STARFORMING/STARBURST) is used **before** WHAN/BPT | INCONSISTENT (with the project's own WHAN logic) | The SDSS pipeline splits SF from AGN with log([O III]/Hβ) = 0.7 − 1.2(log([N II]/Hα) + 0.4) (Bolton+2012 AJ 144, 144; SDSS docs, secondary). This is not the Kewley/Kauffmann pair, so composites become "AGN". It also applies no WHAN retired-galaxy test, which Cid Fernandes+2011 shows is needed for LINER-like galaxies with EW(Hα) < 3 Å ("fake AGN"). | Run `galaxy_lines()` (WHAN → BPT) first whenever line fluxes exist. Use the SDSS `subclass` only for BROADLINE (type-1) and as a fallback. Measure the change on the SDSS test split. |
| GX-10 | SDSS > DESI precedence; DESI lines from `desi_dr1.agngal` | PARTLY | This table **is** the DESI DR1 AGN/Galaxy classification VAC (Juneau et al., in prep., cited by arXiv 2607.27390 and 2607.07329). It already provides bit-wise [N II], [S II] and [O I] BPT, WHAN, MEx, KEx, BLUE, He II and WISE classes (`OPT_UV_TYPE`, `AGN_MASKBITS`). Fibre aperture: the DESI fibre is 1.5″, versus 3″ for SDSS and 2″ for BOSS. | Use the collected but unused `halpha_broad_*` columns (type-1 tag) and `opt_uv_type`/`agn_maskbits` as a cross-check, or as the DESI-path classification. Cite the DESI DR1 VAC page and Juneau et al. (in prep.). |
| (missing) | Fibre aperture effects | NO-SOURCE (not handled) | Kewley, Jansen & Geller 2005 PASP 117, 227 (astro-ph/0501229): the fibre should capture > 20 % of the galaxy light, which for SDSS means z > 0.04 for an average galaxy (2dF z > 0.06). Brighter or late-type galaxies need a higher z. The 1.5″ DESI fibre is worse. | Add an `APERTURE_NUCLEAR` flag when z < 0.04 (SDSS) or z < ~0.06–0.08 (DESI), or when the fibre/Petrosian flux ratio < 0.2. In that case report the line class as "nuclear", for example nuclear LINER in a star-forming disc. |

#### 2. Galaxy activity and morphology from photometry

| ID | Rule | Verdict | Evidence | Recommendation |
|---|---|---|---|---|
| GX-12 | Stern W1−W2 ≥ 0.8, W2 < 15.05 (no S/N cut) | PARTLY | Stern+2012 ApJ 753, 30: W2 ≤ 15.05 is the 95 %-reliability depth for COSMOS. Stage 4 additionally requires S/N ≥ 10. The measured precision on this path is 0.25/0.40 (CHANGELOG). | Use the same rule as Stage 4 (S/N1,2 ≥ 10), or use Assef+2018 R90 (ApJS 234, 23). Note that in low-mass galaxies W1−W2 can be red from star formation (Hainline+2016 ApJ 832, 119; not re-verified here). |
| GX-13 | W2−W3 > 3.0 → SF; < 1.5 → quiescent (σW3 < 0.2) | PARTLY | Jarrett+2017 ApJ 836, 182 and Jarrett+2019 ApJS 245, 25 define spheroid → intermediate disc → SF disc along a W2−W3 sequence. A secondary source (arXiv 2508.06896) quotes the Jarrett+2017 boundaries as < 2 (spheroids), 2–3.5 (intermediate) and > 3.5 (SF discs). Another (arXiv 2201.00826) uses 1.5 (Jarrett+2011, 2017). I could not confirm the 3.0 value. No K-correction is applied (WISE colours change at z ≳ 0.1). | Cite the exact figure or table of Jarrett+2017 for 1.5 and 3.0, or adopt 3.5 for SF. The measured SF precision of 0.76/0.75 suggests that a higher cut may help; refit on the train split. Restrict the rule to z < 0.15 or K-correct. |
| GX-14 | W3 upper limit and W2−W3_lim < 1.5 → quiescent | CONSISTENT (logic) | The direction is right: the true colour is bluer than the limit. Measured precision is 0.96/1.00. | Keep. Make sure "ew3 is None" really means an AllWISE upper limit (`ccflag`/`ph_qual` = 'U') and not a missing W3 measurement. |
| GX-15 | (NUV−r)0 > 5 → quiescent, citing Kaviraj+2007 | PARTLY (miscited) | Kaviraj+2007 ApJS 173, 619: early types with NUV−r < **5.5** are "very likely" to have had recent star formation, so only NUV−r ≳ 5.5–5.6 is quiescent. NUV−r > 5 is the red-sequence limit of Salim 2014 (SerAJ 189, 1) and Wyder+2007 (ApJS 173, 293). Measured precision 0.906/0.88. | Cite Salim 2014 / Wyder+2007 for > 5, not Kaviraj. Optionally add a "strictly quiescent" tier at > 5.5 (Kaviraj+2007). |
| GX-15b | R_NUV = 8.2 (described as "no explicit source") | CONSISTENT (citation missing) | Wyder+2007 used A_NUV/E(B−V) = 8.2 (Cardelli+1989, R_V = 3.1), confirmed by citing papers. The ratio depends on the SED: about 8.2 for constant star formation and about 7.5 for a 7 Gyr SSP. Peek & Schiminovich 2013 give R_NUV = 8.36 + 14.3E − 82.8E² for E(B−V) ≤ 0.2. | Cite Wyder+2007 for 8.2 in the code. Note that the r coefficient 2.165 (DECam) is also applied when r comes from PS1 or SDSS (2.285): use the coefficient that matches the band. |
| GX-16 | Green valley 4 < (NUV−r)0 ≤ 5 | CONSISTENT | Salim 2014 SerAJ 189, 1; Wyder+2007 | Keep. Not scored, so add it to the benchmark report. |
| GX-17/18 | DEV → early, EXP → disc; Sérsic n ≥ 2.5 → early | CONSISTENT | Shen+2003 MNRAS 343, 978 (n = 2.5); Blanton+2003 | Keep. REX/PSF get no profile, which is correct. |
| GX-19 | (u−r)0 ≥ 2.22 → early type | PARTLY | Strateva+2001 AJ 122, 1861: u*−r* = 2.22 optimal separator for g* < 21. The split is only rough by morphology, and the blue fraction rises at faint magnitudes. Baldry+2004 (ApJ 600, 681) gives a magnitude-dependent divider. | Keep it as a fallback. Prefer the Baldry+2004 luminosity-dependent divider when M_r is known. Label the result "red/blue" instead of "early/late". |
| GX-22 | M_B < −21 "luminous" (Schechter M*_B ≈ −20.5 uncited) | NO-SOURCE (value plausible) | 2dFGRS M*_bJ − 5 log h = −19.66 (Norberg+2002 MNRAS 336, 907). For h = 0.7 this is ≈ −20.4. | Cite Norberg+2002, or Blanton+2003 for the r-band equivalent. |
| GX-24 | Any 1.4 GHz detection in a quiescent galaxy → "radio-loud AGN candidate" | PARTLY | Best & Heckman 2012 MNRAS 421, 1569 select radio AGN with D4000 vs L1.4/M* (line Dn4000 = 1.45 − 0.55(log L/M* − 12.2), secondary), plus BPT and Hα–L1.4 tests. Below ~10^23 W/Hz, star-forming galaxies dominate radio samples (Mauch & Sadler 2007 MNRAS 375, 931; secondary). A WHAN-retired galaxy at z = 0.01 detected at 2.5 mJy has L ~ 10^21 W/Hz. NVSS (45″) can blend neighbours. | Require L1.4 > 10^23 W/Hz, or the Best & Heckman 2012 D4000–L/M* criterion. Below that, tag "RADIO" only. Use the FIRST position or flux (5″) when available. |

#### 3. QSO

| ID | Rule | Verdict | Evidence | Recommendation |
|---|---|---|---|---|
| Q-01 | R_i = 0.4(m_i − t) > 1 → radio loud | CONSISTENT (with caveats) | Ivezić+2002 AJ 124, 2364 define R_i with FIRST 1.4 GHz and the SDSS i band, loud for R_i > 1. Newer work uses K-corrected luminosity ratios: Baloković+2012 ApJ 759, 30, R_i = log(L5GHz/L_i); LoTSS uses L144/L_i (Gürkan+2019 A&A 622, A11, arXiv 1811.07933). Falcke+1996 and Kellermann+2016 (ApJ 831, 168; not re-verified) note that the boundary is arbitrary and that radio-intermediate sources exist. | Keep. Prefer FIRST over NVSS (already done). Flag NVSS-only values as "possibly confused (45″ beam)". Add the K-corrected Baloković form when z is known, and an "intermediate" band 0.5 < R_i < 1.5. The benchmark has no radio fluxes, so validate on DR16Q × FIRST. |
| Q-04 | z ≥ 2.1 → HIGH_Z | CONSISTENT (re-cite) | DESI: tracer quasars at 0.9 < z < 2.1 and Lyα quasars at z > 2.1 (Chaussidon+2023 ApJ 944, 107). BOSS targeted 2.15 < z < 3.5 (Ross+2012 ApJS 199, 3). | Add the Chaussidon+2023 citation. |
| Q-07 | M_i(z=2), K-correction, < −22 | CONSISTENT | Richards+2006 AJ 131, 2766; Schneider+2010 AJ 139, 2360. DR16Q (Lyke+2020 ApJS 250, 8) dropped the luminosity cut. | Keep it as a tag. |
| X-ray (B-QSO-1) | Catalogue membership | CONSISTENT | – | Optionally compute αox (Lusso & Risaliti 2016 ApJ 819, 154; not re-verified) to flag X-ray-weak or BAL quasars. |
| Q-10 / blazar | Blazar only from SIMBAD BLL/Bla | PARTLY | Dedicated catalogues exist: Roma-BZCAT 5th ed. (Massaro+2015 Ap&SS 357, 75), WIBRaLS2/KDEBLLACS (D'Abrusco+2019 ApJS 242, 4, arXiv 1903.11124; 9,541 + 5,655 candidates), and Fermi 4LAC-DR3 (Ajello+2022 ApJS 263, 24). | Add a BZCAT/4LAC match → BLAZAR (BZB/BZQ/BCU subtype), and the WISE blazar strip (WIBRaLS2) as a candidate route. |
| X-EXG-1 | `in_vari_agn` → AGN; or Gaia `best_class_name` = AGN with no score threshold | PARTLY | Gaia DR3 variable AGN (Carnerero+2023 A&A 674, A24, arXiv 2207.06849): after filtering, about 872k sources, with purity estimated > 95 % and completeness about 50 %. The generic vari_classifier AGN class (Rimoldini+2023 A&A 674, A14) is not filtered that way. | Keep `in_vari_agn`. For `best_class_name` = AGN, require a minimum `best_class_score` (fit on train), or demote it to "AGN candidate". |

#### 4. Radio pulsar candidates without ATNF (compact axis)

| ID | Rule | Verdict | Evidence | Recommendation |
|---|---|---|---|---|
| X-CMP-3 | α(TGSS 150 → NVSS 1400) ≤ −1.5 and TGSS S_tot/S_peak ≤ 1.5 | CONSISTENT | Frail+2018 MNRAS 475, 942 (arXiv 1712.06609): candidates have α ≤ −1.5 and C ≤ 1.5. This is quoted by arXiv 2011.03456; the C ≲ 1.5 justification is from Frail+2016b. Frail+2016 is **ApJ 829, 119** (200 + 88 TGSS pulsars). Pulsar α: mean −1.6 (Jankowski+2018 MNRAS 473, 4436, 441 pulsars; ±0.54 not re-verified) and −1.4 ± 1.0 (Bates+2013 MNRAS 431, 1352). Benchmark median −1.38 vs −0.73. | Keep. Recall (21.6 %) is limited mainly by TGSS detection: only 66/116 pulsars are detected and 25/66 = 38 % pass (recomputed here). Add LoTSS DR2 (6″, about 0.08 mJy rms) α where it exists, and RACS-low (888 MHz) for the south. Frail+2018 also used α *upper limits*. Compactness at 25″ (TGSS) is coarse: add VLASS/FIRST deconvolved size (cf. "From NVSS to RACS", arXiv 2604.04577). Pulsar spectra with low-frequency turnovers (Jankowski+2018) are missed by design; record this. |
| X-CMP-4 | Significant linear polarisation: P/σ ≥ 3 and P/S > 5 % | CONSISTENT (σ part is a project choice) | Han & Tian 1999 A&AS 136, 571 (97 NVSS pulsars): only 8 of 89 have < 5 % polarisation, against ~10 % of quasars and BL Lacs above 5 % (secondary). Benchmark median fpol is 0.139 for pulsars vs 0.024 for the control. | Keep. Cite "3σ" as the standard detection threshold used in NVSS polarisation work (Condon+1998 AJ 115, 1693). Recent searches add **circular** polarisation, which is a much stronger discriminator: Sobey+2022 A&A 661, A87 (LoTSS linear and circular polarisation, TULIPP); Wang Y.+2022 ApJ (PSR J0523−7125, VAST, DOI 10.3847/1538-4357/ac61dc); Pritchard+2021 (RACS circular polarisation > 6 %); Lenc+2018 (MWA). Add RACS/VAST Stokes V when it becomes reachable. |
| X-CMP-5a | Pol LR = 0.241/0.0332 | INCONSISTENT (comment and doc only, not the constant) | Recomputed from `radio_sample.csv.gz` (one row per NVSS source): significant polarisation is 28/116 = 0.241 for pulsars and 84/2531 = 0.0332 for the control, so **the constants are correct**. The comment's "7/116 and 0/2531" means hits *within* the steep+compact selection, and `pulsar_metrics.json` gives 6, not 7. The naive-Bayes LR is unconditional, while within rule hits the separation is 6/25 vs 0/3. Applying it after LR_rule assumes independence. | Fix the comment and LITERATURE text (6/25 within hits; 28/116 vs 84/2531 overall). Estimate the LR conditionally on rule hits, or state the independence assumption next to the measured counts. The concern in `rule_inventory` §C.5 is resolved for the constants. |
| X-CMP-5b | Prior 116/1.77M | CONSISTENT | Han & Tian 1999 found 97 pulsars in NVSS. The benchmark finds 116 unique NVSS sources out of all ATNF pulsars (B/psr, all rows, 15″), so 116/1.77M is the right order of magnitude. The "~3,000 pulsars" in LITERATURE_MULTI_AXIS refers to all ATNF pulsars, not NVSS-detected ones. | Keep. Fix the LITERATURE wording. |
| X-CMP-5c | Plane LR \|b\| < 10°: 0.621/0.099; comment "scale height ~0.5 kpc (Lorimer+2006)" | INCONSISTENT (text) | Lorimer+2006 MNRAS 372, 777 (astro-ph/0607640): exponential **scale height 330 pc** for 1008 normal pulsars. MSPs are much more isotropic. Frail+2018 found mostly MSPs, which the plane LR then penalises (0.42×). | Change the comment to 330 pc. Consider a separate LR for |b| ≥ 10° combined with a Fermi-LAT unassociated-source match (4FGL-DR4), which is a strong MSP prior (Frail+2018). |
| X-CMP-5d | Naive-Bayes posterior design | PARTLY | Recent image-based searches combine steep spectrum, compactness, polarisation, variability or scintillation, and the absence of an optical/IR counterpart: Sett+2024 PASA 41, e045 (MWA VCS imaging census); Mantovanini+2025 (GLEAM-X GP, 106 candidates, arXiv 2509.02919); a 2025/26 ApJ paper on scintillation-based candidate selection (DOI 10.3847/1538-4357/ae23c9); an ANN selection from continuum surveys (MNRAS 494, 1035, 2020; authors not verified). The benchmark shows a Gaia neighbour within 5″ for 39 % of pulsars vs 17 % of the control, so "no counterpart" is *not* usable with Gaia at 5″ in the plane. | Keep naive Bayes, but calibrate the posterior on the 25+3 hits (reliability table) and report it. Add LoTSS/RACS spectral index and Stokes V as factors. Do **not** add a "no Gaia counterpart" factor without a crowding correction. |
| X-CMP-1/2 | ATNF match → PULSAR; SIMBAD N*/Psr/XB*/LXB/HXB | CONSISTENT | Manchester+2005 AJ 129, 1993 | Keep. |
| X-CMP-2 (XRB) | XRB only from SIMBAD | PARTLY | Curated catalogues: XRBcats LMXB (Avakyan+2023 A&A 675, A199; 349 LMXBs) and HMXB (Neumann+2023 A&A 677, A134; 169 HMXBs), both on VizieR and updated regularly. | Add XRBcats as the primary XRB source (LMXB/HMXB subtype), with SIMBAD as fallback. |
| X-CMP-6 | Gaia `in_vari_compact_companion` → COMPACT_COMPANION_CANDIDATE | CONSISTENT (label is appropriately "candidate") | Gomel+2023 (Gaia DR3): 6,306 ellipsoidal candidates, of which 262 have modified minimum mass ratio > 1. Spectroscopic follow-up (Nagarajan+2023, arXiv 2304.07324) found most are contact binaries of two luminous stars, so purity is low. | Keep the candidate label. Raise confidence only for the mMMR > 1 subset. Add the Gaia BH1–3 class objects (El-Badry+2023; Gaia Collab. Panuzzo+2024) via SIMBAD. |

#### 5. Phenomena

| ID | Rule | Verdict | Evidence | Recommendation |
|---|---|---|---|---|
| X-PHN-1 | Acker PN spectrum → PN if ≥ 2 positive lines; [O III]/Hα computed but not used | NO-SOURCE (≥ 2 lines) | The Strasbourg-ESO PN catalogue (Acker+1992) is itself a PN catalogue, so the count only checks that data exist. Literature PN-versus-mimic diagnostics use line *ratios*: [N II]/Hα vs [S II]/Hα (SMB diagram), [O III]5007/Hβ and He II 4686 (Frew & Parker 2010 PASA 27, 129). HII regions, symbiotic stars and SNRs also show ≥ 2 lines. | Treat Acker membership like HASH (identity evidence). Use the ratios as a mimic veto, for example log [S II]/Hα > −0.4 → SNR-like (Frew & Parker 2010), or report them. Fix LITERATURE_SPECTROSCOPY §5 ("used" → "reported"). |
| X-PHN-2a | HASH match → PN regardless of status | PARTLY | HASH (Parker, Bojičić & Frew 2016, J. Phys. Conf. Ser. 728, 032008, arXiv 1603.07042) grades objects True/Likely/Possible (2,401/447/692 in 2016) and also lists post-AGB stars, pre-PNe and mimics. | Label only True/Likely as PN. Label Possible as PN_CANDIDATE. Do not label HASH non-PN entries (mimics, post-AGB) as PN. `pn_catalog_status` is already collected. |
| X-PHN-2b | ASAS-SN / Asiago SN match → SN | PARTLY | ASAS-SN bright SN catalogues (Holoien+2017 MNRAS 464, 2672 and follow-ups to 2019); Asiago (Barbon+1999 A&AS 139, 531; no longer maintained). The rule does not check the event epoch, unlike X-PHN-3, so a host-galaxy detection years after the event is labelled "SN". | Apply the same epoch rule as X-PHN-3. Give the SN label only if the observation is within ~1 yr of discovery; otherwise emit "SN_HOST/past SN". Add TNS as the current SN source. |
| X-PHN-3 | Time-domain SN class only with an event epoch | CONSISTENT | General practice | Keep. |
| X-PHN-4 | SIMBAD SN*/PN/No*; Gaia SN/MICROLENSING without score | PARTLY | Rimoldini+2023 vari_classifier scores are not calibrated | Fit a minimum `best_class_score`, as for X-EXG-1. |

#### 6. Summary of INCONSISTENT / NO-SOURCE items

1. **GX-01 precedence (INCONSISTENT):** the SDSS `subclass` (Bolton+2012 pipeline line) overrides the project's WHAN retired test and its Kewley/Kauffmann BPT. Composites and retired galaxies become "AGN". Fix: run WHAN → BPT first, and keep the SDSS subclass only for BROADLINE or as a fallback.
2. **X-CMP-5a pol LR comment (INCONSISTENT text):** the constants match the unconditional rates (28/116, 84/2531). The comment's 7/116 and 0/2531 are within-hit counts, and the metrics file says 6. Fix the comment/doc, and estimate the LR conditional on hits or state the independence assumption.
3. **X-CMP-5c scale height (INCONSISTENT text):** Lorimer+2006 gives 330 pc, not ~0.5 kpc.
4. **Fibre aperture (NO-SOURCE / missing):** add a Kewley+2005 aperture flag (z < 0.04 SDSS; higher for the 1.5″ DESI fibre).
5. **X-PHN-1 "≥ 2 lines" (NO-SOURCE):** replace with Frew & Parker 2010 ratio diagnostics, or treat Acker as identity evidence.
6. **GX-22 M*_B (NO-SOURCE):** cite Norberg+2002.

Notable PARTLY items:
- GX-15 cites Kaviraj for > 5, but Kaviraj uses 5.5; cite Salim 2014 for 5.
- GX-09 Dn4000 1.6 vs Kauffmann 1.5; the DESI Dn4000 path is dead code.
- GX-13 Jarrett thresholds are unverified (3.0 vs 3.5).
- GX-24 radio AGN needs a luminosity or BH12 test.
- The DESI VAC classification and broad-Hα columns are collected but unused.
- HASH status is not filtered.
- SN matches are not epoch-gated.
- No blazar or XRB catalogues are used.

#### Sources (URLs)
- DESI DR1 AGN/Galaxy VAC: https://data.desi.lbl.gov/doc/releases/dr1/vac/agngal/ ; arXiv 2607.27390, 2607.07329
- Stasińska+2006: https://arxiv.org/abs/astro-ph/0606724 ; secondary: https://arxiv.org/pdf/2002.05751 , https://arxiv.org/pdf/1001.2825
- Cid Fernandes+2011 WHAN: https://arxiv.org/pdf/1012.4426
- Schawinski+2007: https://arxiv.org/pdf/0709.3015 ; Cid Fernandes+2010: https://arxiv.org/pdf/0912.1643 ; Cheng+2025: https://arxiv.org/abs/2505.17843
- Kewley, Jansen & Geller 2005: https://arxiv.org/abs/astro-ph/0501229
- Kaviraj+2007: https://arxiv.org/abs/astro-ph/0601029
- Wyder+2007 / R_NUV: https://arxiv.org/pdf/0706.3938 ; https://arxiv.org/pdf/1805.08951
- Dn4000 conventions: https://arxiv.org/pdf/1611.00528
- Jarrett+2017/2019 secondary thresholds: https://arxiv.org/pdf/2508.06896 , https://arxiv.org/pdf/2201.00826 , https://ipac.caltech.edu/publication/2019ApJS..245...25J
- Strateva+2001: https://arxiv.org/abs/astro-ph/0107201
- Best & Heckman 2012: https://arxiv.org/pdf/1201.2397 ; D4000–L/M* line: https://arxiv.org/pdf/2206.01195
- Radio loudness: https://arxiv.org/pdf/1811.07933 , https://arxiv.org/pdf/1408.1090
- Chaussidon+2023: https://discovery.ucl.ac.uk/id/eprint/10166608/1/Chaussidon_2023_ApJ_944_107.pdf
- Blazars: https://arxiv.org/pdf/1903.11124 ; 4LAC-DR3: https://dc.g-vo.org/rr/q/lp/custom/CDS.VizieR/J/ApJS/263/24
- Gaia DR3 variable AGN: https://arxiv.org/abs/2207.06849
- Gaia compact companions: https://gea.esac.esa.int/archive/documentation/GDR3/Data_analysis/chap_cu7var/sec_cu7var_cc/ssec_cu7var_cc_intro.html ; https://arxiv.org/abs/2304.07324
- XRBcats: https://www.aanda.org/articles/aa/full_html/2023/07/aa46522-23/aa46522-23.html ; https://dc.g-vo.org/rr/q/lp/custom/CDS.VizieR/J/A+A/677/A134
- Frail+2018: https://arxiv.org/pdf/1712.06609 ; secondary for cuts: https://arxiv.org/pdf/2011.03456 ; Frail+2016: https://arxiv.org/abs/1606.00449
- Jankowski+2018: https://arxiv.org/abs/1709.08864
- Han & Tian 1999: https://arxiv.org/abs/astro-ph/9903100
- Lorimer+2006: https://arxiv.org/abs/astro-ph/0607640
- Sobey+2022 TULIPP: https://www.aanda.org/articles/aa/full_html/2022/05/aa42636-21/aa42636-21.html
- Wang+2022 PSR J0523−7125: https://iopscience.iop.org/article/10.3847/1538-4357/ac61dc
- Sett+2024: https://www.cambridge.org/core/services/aop-cambridge-core/content/view/6558F7066E737A0B87EAA9A7822087B9/S1323358024000626a.pdf ; Mantovanini+2025: https://arxiv.org/html/2509.02919v1
- Scintillation candidates: https://iopscience.iop.org/article/10.3847/1538-4357/ae23c9 ; NVSS→RACS compact steep: https://arxiv.org/pdf/2604.04577 ; ANN selection: https://academic.oup.com/mnras/article/494/1/1035/5816868
- HASH: https://arxiv.org/pdf/1603.07042

Local recomputation (this review): `v2/benchmark/pulsar_truth/radio_sample.csv.gz`, deduplicated by NVSS source:
- pulsars in the Galactic plane (|b| < 10°): 0.621; control: 0.0988
- significant polarisation: pulsars 28/116, control 84/2531
- TGSS detection: pulsars 66/116; among those, 25/66 have α ≤ −1.5
- LoTSS detection: only 5/116 pulsars

