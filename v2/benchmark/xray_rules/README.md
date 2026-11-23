# X선 규칙 통제 시험 표본 (2.56.0)

`../evaluate_xray_rules.py`가 읽는 `sample.csv.gz`(31,268행)를 만드는 과정. 원자료(수백 MB)는 저장소에 두지 않고, 아래 순서로 다시 받을 수 있다. 2026-11-23에는 CDS Strasbourg가 404, Gaia 아카이브가 DR4 준비로 중단이라 VizieR 미러(CfA·IDIA)와 GAVO TAP(하이델베르크)을 썼다.

1. VizieR 미러에서 내려받기(`DIR`에 저장; asu-tsv, `-out.max=unlimited`)
   - 4XMM-DR13 `IX/69/xmm4d13s`: `4XMM,RA_ICRS,DE_ICRS,ePos,Flux8,e_Flux8,F8max,HR1,ext,srcML` → `xmm.tsv`
   - eRASS1 주 목록 `J/A+A/682/A34/erass1-m`: `IAUName,RA_ICRS,DE_ICRS,posErr,EXT,DetLike0,MLFlux1,e_MLFlux1` → `erass.tsv`
   - CSC 2.0 `IX/57/csc2master`: `2CXO,RAICRS,DEICRS,r0,fe,Favgb,S/N` → `csc.tsv`
   - 정답(astroquery `get_catalogs`, 전체 열): Ritter & Kolb `B/cb/cbdata` → `rk.csv.gz`, Neumann+2023 `J/A+A/677/A134/hmxbcat`, Avakyan+2023 `J/A+A/675/A199/lmxbcat`, Fortin+2023 `J/A+A/671/A149/tablea`, Fortin+2024 `J/A+A/684/A124/lmxbcat`, HamStar(Freund+2024) `J/A+A/684/A121/like_ctp` → `hamstar.csv.gz`
2. `python build_sdss_spec.py DIR/sdss_star_qso.csv.gz` — SDSS DR18 분광 STAR·QSO(zWarning = 0), RA 10°씩
3. `python build_match.py DIR` — 정답·HamStar를 세 X선 목록에 맞춤(위치 오차 3σ, 하한·상한 4XMM 3–10″, eRASS1 5–15″, CSC 2–5″)
4. `python build_sample.py DIR` — SDSS 분광 천체 대응, Gaia DR3(`gaia.dr3lite`)·2MASS(`twomass.data`) 3″ 최근접(GAVO TAP 업로드)
5. 저장: QSO는 Ks가 있거나 시차/오차 > 3인 것만 남김(나머지는 두 규칙 어느 쪽에도 쓰이지 않음)

`chance_matches.py`: SDSS 별 위치를 1–2′ 옮겨 우연 일치 비율을 잼(4XMM 19 %, eRASS1 65 %, CSC 11 %; 1.5″ 안에서는 4.2 %, 1.7 %).
