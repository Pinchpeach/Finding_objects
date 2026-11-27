# 작업 보고서 2026-11-27e — "Evaluate WD HR-locus gates"의 VizieR 교차대조 재시도 (2.61.6)

계획 세션 지시서 과제 사. 워크플로 `Evaluate WD HR-locus gates`가 "Crossmatch truth sets to Gaia DR3" 단계에서 실패했다(run 46031822845, 2026-11-27 18:18 UTC). CDS XMatch가 ConnectTimeout으로 죽어 VizieR 우회(`_vizier_fallback`)로 갔고, VizieR 쪽 응답이 중간에서 잘려 4번 재시도가 모두 같은 오류로 끝났다. 분류 결과·관문 평가 코드는 바꾸지 않았다.

## 1. 한 줄 결과

- **원인 셋**: ① 미러 층(`throttle._with_mirrors`)이 **HTTP 200이지만 `</VOTABLE>` 앞에서 끊긴 VOTable**을 성공으로 쳤다 → 그 미러가 "응답한 미러"로 기억되어(`_preferred`) 재시도마다 같은 미러가 같은 잘린 답을 되돌려줬다. ② 전송 도중 끊긴 본문(`ChunkedEncodingError`, 로그의 "Connection reset by peer")은 미러 순환이 잡는 예외(`ConnectionError`, `Timeout`)에 들지 않아 순환 없이 위로 올라갔다. ③ `_vizier_fallback`의 재시도(4번, 15–60 s 쉬고)는 주석("mirror failover")과 달리 매번 같은 미러에 갔고, 배치 500개 위치가 미러가 자르는 크기라서 같은 요청을 반복했다.
- **고침**: (a) 미러 층이 잘린 VOTable과 끊긴 본문을 그 미러의 실패로 판정해 다음 미러로 간다(그 미러는 뒤로 밀린다; 모든 미러가 자르면 반쪽 표를 돌려주지 않고 `ChunkedEncodingError`). (b) `throttle.distrust_last_mirror()`: 응답은 왔지만 호출자가 못 읽은 경우(astroquery `TableParseError`) 그 미러를 실패로 표시해 재시도가 다른 미러로 간다. (c) `_vizier_fallback`: 시도 사이에 이 미러 표시를 하고, **읽을 수 없는 응답**(끊김·파싱 실패)이 2번 나오면 배치를 반으로 줄여(500 → 250 → … 최소 50) 줄인 크기를 나머지 배치에도 쓴다. 연결 거부·오류 상태 같은 "크기와 상관없는" 실패는 줄이지 않고 같은 크기로 다시 한다.
- **쉬는 규칙 유지**: 미러를 도는 요청과 새 시도마다 `throttle`의 3–5 s 쉼이 붙는다(요청 단위). 재시도 사이 15·n s 백오프는 그대로.
- **시험 14개 추가**(병합 뒤 전체 499개 통과). **결과 불변**: 같은 100개 위치의 VizieR 응답(실제 데이터, 캐시에 있던 것)으로 이전 코드와 이번 코드가 낸 교차대조 표가 같고(95행, 234열, `DataFrame.equals`), `evaluate_wd_hr_gates.py` 결과 JSON도 바이트 단위로 같다.
- **한계**: 이 컨테이너에서는 VizieR 미러가 지금 쓸 수 없는 상태(CfA 60 s 뒤 504, IDIA 301 s ProxyError, NAOJ·IUCAA 읽기 시간 초과, 스트라스부르 404)라 500개 위치 실데이터 전체를 다시 받아 보지는 못했다. 잘림 재현은 시험(미러 층 위의 가짜 VizieR)으로 했다. 실제 워크플로가 이번 수정으로 통과하는지는 CI에서 확인해야 한다(7절).

## 2. 실패 로그가 말해 준 것

```
requests.exceptions.ConnectTimeout: ... host='cdsxmatch.u-strasbg.fr' ... (connect timeout=None)    # XMatch: 이것이 우회를 일으킴
ValueError: 1027:862: no element found                                                          # astropy: VOTable이 1027줄 862열에서 끝남
astroquery.exceptions.TableParseError: Failed to parse VIZIER result!                          # collect_star_gaia.py:50 query_region, 4번째 시도
```

"1027:862: no element found"는 XML이 열린 채 끝났다는 뜻이다(응답이 잘림). 같은 실패가 4번 연속 난 것은 우연이 아니라 구조적이다: 잘린 응답도 상태 200이라 미러 층은 성공으로 기록하고(`_remember(host, True)`, `_preferred`), 다음 요청은 그 미러를 먼저 물었다.

## 3. 설계와 이유

**왜 `throttle`에서 고쳤나(수집기마다가 아니라)**: VizieR 미러 순환은 모든 수집기가 쓰는 한 곳(`throttle._with_mirrors`)에 있다. 잘림 판정을 여기 두면 `_vizier_fallback`만이 아니라 VizieR를 쓰는 모든 수집기(Gaia 복사본, AllWISE, 2MASS, 전파 …)가 얻는다. 호출 쪽에서 `TableParseError`를 잡아 재시도하는 안은 잘림이 "같은 미러, 같은 답"이라는 사실을 못 바꾼다.

**잘림 판정**: 상태 200이고 VOTable(`Content-Type`에 votable이 있거나 본문 머리 2000바이트에 `<VOTABLE`이 있음)인데 마지막 2048바이트에 `</VOTABLE>`이 없으면 잘린 것이다. JSON·HTML·오류 상태는 건드리지 않는다. 대안 `Content-Length` 비교는 청크 전송 응답에 길이가 없어 버렸고, 파서에 맡기는 안은 잘림을 "읽기 오류"라는 모호한 신호로만 알려 준다. 정상 응답에는 바이트 비교 한 번만 늘어난다(이미 `resp.text`를 읽는 자리).

**실패 처리**: 그 미러는 `MIRROR_STICKY_S`(600 s) 동안 뒤로 밀리고 다른 프로세스도 실패 기억(`archive_cache`)으로 공유한다 — 기존 연결 거부·504와 같은 규칙이라 "미러를 건너뛰지는 않고 순서만 바꾼다"는 원칙(모든 미러가 실패하면 마지막으로 다시 묻는다)이 유지된다. 모든 미러가 자르면 마지막 응답을 돌려주는 대신 `ChunkedEncodingError`를 올린다: 호출 쪽의 `TableParseError`보다 원인이 보이고, "반쪽 표를 빈 응답으로 읽는" 일(2026-11-07의 침묵 실패)이 없다.

**왜 `distrust_last_mirror()`가 따로 필요한가**: 본문이 끝까지 왔는데 파서가 거부하는 경우(예: 서버 오류 페이지가 200으로 오는 경우)는 미러 층이 알 수 없다. 호출자가 "방금 답을 못 읽었다"고 알려 줄 길이 있어야 재시도가 미러를 바꾼다. 스레드별로 마지막 응답의 미러를 기억해(`last_host`) 그것만 표시한다.

**왜 배치를 반으로 줄이나, 그리고 언제**: 이 컨테이너에서도 500개 위치 요청은 CfA가 "Connection reset by peer"로 끊었다(응답이 길어서다). 같은 요청을 아무리 다시 해도 같은 크기의 답이 같은 곳에서 끊긴다. 그래서 읽을 수 없는 응답이 시도 2번 나오면 크기를 줄이고(최소 50), 성공한 크기를 나머지 배치에도 쓴다(500으로 되돌아가 같은 실패를 반복하지 않도록). 처음부터 작게 하는 안은 요청 수가 5배(100개씩이면 10,000개 위치에 100번 × 3–5 s 쉼)라 정상 경로의 시간을 늘리므로 버렸다. 연결 거부·504 같은 "도달" 실패에는 줄이지 않는다(크기와 무관하고, 미러가 되살아나면 같은 크기가 맞다). 결과는 배치 분할과 무관하다: 교차대조는 위치마다 가장 가까운 행을 남긴다(`sort_values(["benchmark_id", "_sep_arcsec"]).drop_duplicates`).

**시도 횟수**(9절 5번에서 고침): 배치마다 최대 4번(예전과 같음). 다만 최소 크기보다 큰 배치는 읽을 수 없는 응답이 2번 나오면 그 자리에서 멈추고 반으로 줄인다. 줄여도 같은 오류가 이어지면 최소 크기(50)에서 4번 한 뒤 오류를 올린다. 총 시도 수는 읽을 수 없는 응답이 끝까지 이어질 때 늘고(500→250→125→62가 각 2번, 최소 크기 50에서 4번 = 12번), 도달 실패(연결 거부·오류 상태·시간 초과)일 때는 예전처럼 4번이다.

**하지 않은 것**: XMatch에 시간 제한을 두지 않았다(큰 업로드가 정당하게 오래 걸릴 수 있어 정상 경로를 깰 수 있다; 이번 실패의 원인도 아니고 비용은 연결 시간 초과 한 번). 워크플로 파일도 건드리지 않았다.

## 4. 시험 (`test_vizier_mirrors.py` +6, `Classifier/tests/test_collect_star_gaia.py` 8)

- 잘린 VOTable 판정: 끝 태그 없음 = 잘림, 끝 태그 뒤 공백·줄바꿈 = 정상, JSON·오류 상태·본문 없는 가짜 = 아님.
- 잘린 응답은 다음 미러로 가고, 그 미러는 다음 요청에서 뒤로 간다. 끊긴 본문(`ChunkedEncodingError`)도 같다. 모든 미러가 자르면 `ChunkedEncodingError`(각 미러를 한 번씩 물음). 정상 응답은 한 번에 반환.
- `distrust_last_mirror()` 뒤의 다음 요청은 그 미러를 맨 앞에 두지 않는다.
- 폴백(미러 층 위에 얹은 가짜 `Vizier`): 정상 실행은 XMatch 배치 형식(`benchmark_id`, `angDist` …), 첫 미러가 자르면 한 시도 안에서 둘째 미러가 답한다, 읽을 수 없는 본문이면 재시도가 **다른 미러**로 간다(예전에는 같은 미러), 어디서나 잘리면 반으로 줄고 줄인 크기가 유지된다, 줄일 수 없는 크기에서 계속 실패하면 오류, 도달 실패(연결 거부)는 줄이지 않고 같은 크기로 다시 시도, 재시도로 받은 결과와 처음에 정상으로 받은 결과가 `assert_frame_equal`로 같다.

## 5. 결과가 바뀌지 않음

- **같은 100개 위치, 실제 VizieR 응답**(`star_truth.csv` 앞 100행; 이 컨테이너에서 받아 천문 캐시에 있는 응답): 이전 코드(main 572d4b2)와 이번 코드가 낸 교차대조 표가 `DataFrame.equals`로 같다(95행 × 234열, 전부 `WHITE_DWARF`). 같은 입력에 `evaluate_wd_hr_gates.py`를 돌려 낸 JSON도 **바이트 단위로 같다**(예: 광대역 관문 정밀도 1.0, 재현율 0.884; `plx4_or_pm10_p75` 사용 가능 82, 표시 80, 정밀도 1.0, 재현율 0.842).
- 정상 경로의 코드는 같은 요청·같은 후처리다: 배치 크기(`VIZIER_BATCH = 500`)에서 시작해 실패가 없으면 줄이지 않는다.
- 시험 14개 추가, 병합 뒤 전체 499개 통과.

## 6. 영향

- VizieR 미러를 쓰는 모든 수집기: 잘린 VOTable을 받으면 파서 오류 대신 다음 미러로 간다. 정상 응답의 동작은 같고 요청 수도 같다. 잘림이 모든 미러에서 나는 요청은 `ChunkedEncodingError`로 끝나 수집기가 `error`로 보고한다(예전에는 `TableParseError` 같은 파서 오류).
- `Classifier/collect_star_gaia.py`: 정상 경로 요청 수 같음. 배치 로그에 "batch of N (mirror …): …; attempt k/m"와 크기 변경 안내가 추가된다.

## 7. 한계와 다음에 볼 것

- **CI에서 확인이 남았다**: 이 컨테이너는 VizieR 미러가 대부분 막혀 있어(요청 로그: CfA 504 60 s, IDIA ProxyError 301 s, NAOJ·IUCAA ReadTimeout 10 s, China-VO 연결 오류, 스트라스부르 404) 500개 위치 실데이터를 끝까지 받지 못했다. 워크플로(`Evaluate WD HR-locus gates`)를 이 수정으로 한 번 돌려 보면 알 수 있다(계획 세션의 몫; 이 세션은 워크플로를 돌리지 않는다).
- 잘림이 크기 때문이 아니라 미러 쪽 시간 제한 때문이면 크기를 줄여도 같은 오류가 날 수 있다: 최소 크기(50)에서 4번 시도한 뒤 오류를 올리고, 로그에 미러와 오류가 남는다.
- 모든 미러가 막힌 날(이 컨테이너)에는 시도 하나가 미러 6개를 모두 거쳐 수 분이 걸린다(IDIA의 읽기 제한 300 s). 이것은 이전과 같다.

## 8. 산출물

- 코드: `Get_data/throttle.py`(`_truncated_votable`, `last_host`, `distrust_last_mirror`, 순환 루프의 잘림·끊김 처리, 독스트링), `Classifier/collect_star_gaia.py`(`_batch_rows`, `_unreadable_answer`, 배치 크기 조정).
- 시험: `Preprocess/tests/test_vizier_mirrors.py`(+6), `Classifier/tests/test_collect_star_gaia.py`(8).

## 9. 병합 전 검토 (2.61.6)

검토 세션의 질문 세 개를 코드로 확인했고, 검토·CI에서 나온 것을 고쳤다(시험 499 → 508).

1. **잘림 판정이 정상 응답을 실패로 오판하지 않는가.** `_truncated_votable`은 상태 200이고 VOTable(Content-Type에 `votable`이 있거나 본문 앞 2,000바이트에 `<VOTABLE`)인데 끝 2,048바이트에 `</VOTABLE>`가 없을 때만 참이다. 이 판정은 `_with_mirrors`의 VizieR 미러 호스트(`VIZIER_HOSTS`) 요청에만 걸린다. 그 밖의 요청(Data Lab, MAST, LS 뷰어의 `stream=True` FITS, SkyServer 등)은 판정 전에 그대로 지나간다.
   - VizieR 요청은 astroquery의 `/viz-bin/votable`(VOTable; BINARY·BINARY2 직렬화여도 XML 뿌리와 끝 태그가 있음)이다. 이 저장소의 수집기 중 VizieR에 TSV·FITS·JSON을 요청하는 것은 없다(`-out.form`은 throttle이 `mini`를 지울 때만 나온다).
   - 전송 gzip은 `requests`가 풀어 `content`가 평문이다. 행 0개 응답과 오류 INFO만 있는 응답도 `</VOTABLE>`로 끝난다(빈 원뿔·오류는 기존 `_tableless_votable`/`_answer_error`가 다룬다).
   - 끝 태그 뒤에 2 KB 넘는 꼬리가 붙는 VizieR 응답은 본 적이 없다. 생기면 정상 미러가 600 s씩 밀릴 수 있으나, 모든 미러가 그렇게 판정되면 오류로 끝나므로 조용히 틀리지는 않는다.
2. **실패 기억의 공유.** 잘림은 기존의 연결 거부·시간 초과와 같은 길로 기록된다(`_remember(host, False)` → `archive_cache.note_source`, `V2_CACHE_DIR` 아래 파일). 그래서 같은 기계의 다른 프로세스에서도 그 미러가 MIRROR_STICKY_S 동안 뒤로 간다. 그 미러가 나중에 잘 답하면 기억이 지워진다. 의도된 동작이고 2.60.0부터의 시간 초과 처리와 같다. 세트 C의 60개 작업은 각기 다른 GitHub 러너에서 돌아 캐시를 공유하지 않으므로 서로 영향을 주지 않는다.
3. **고침: 실패한 요청 뒤의 `distrust_last_mirror`.** `last_host`는 성공한 응답에서만 기록되었다. 그래서 한 요청이 모든 미러에서 실패(모두 잘림, 모두 거부)하면 `collect_star_gaia`가 부르는 `distrust_last_mirror()`가 **이전 배치에 잘 답한 미러**를 600 s 뒤로 밀었다. 이제 VizieR 요청을 시작할 때 `last_host`를 지우므로, 실패한 요청 뒤에는 미러를 지목하지 않는다(None). 시험 `test_a_request_that_fails_everywhere_leaves_no_mirror_to_distrust`(옛 코드에서 실패).
4. **코드 검토(Codex) 반영.** ① 한 미러가 잘린 VOTable을 주고 나머지 미러가 연결을 거부·시간 초과하면 마지막 예외(`ConnectionError`)가 잘림 신호를 덮었다. 그러면 `collect_star_gaia`가 "읽을 수 없는 응답"으로 보지 않아 배치를 줄이지 못했다. 이제 어떤 미러든 잘린 답을 주었고 온전한 답을 준 미러가 없으면, 뒤의 연결 오류나 빈 답보다 잘림 오류(`ChunkedEncodingError`)가 우선한다. ② astroquery는 응답을 파싱 전에 캐시하므로(`query_region(cache=True)` 기본값), 파싱에 실패한 완전한 본문을 재시도마다 캐시에서 다시 읽고 `throttle`에 가지 않았다. 이제 재시도(둘째 시도부터)는 `cache=False`로 네트워크에 간다. 시험 2개(옛 코드에서 실패; 가짜 Vizier에 astroquery의 캐시 동작을 넣음), 전체 501개. ③ (b51d74b 검토) ①과 같은 덮어쓰기가 **전송 중 끊긴 본문**(`ChunkedEncodingError`·`ContentDecodingError`, 응답이 아니라 예외로 온다)에는 남아 있었다. 이제 이 예외도 잘림 신호로 따로 기억해 뒤의 연결 오류·시간 초과보다 우선하고, 오류 문구에 어느 쪽인지 적는다("before </VOTABLE>" 또는 "in transfer (ChunkedEncodingError)"). 시험 2개(두 예외 각각, 옛 코드에서 실패), 전체 505개. ④ (4d216f9 검토) **마지막 미러의 오류 상태**(404·5xx)는 그대로 응답으로 돌려주었으므로, 앞 미러가 표를 잘랐어도 503 응답이 나가 배치가 줄지 않았다. 이제 잘림이 기록되었으면 마지막 미러의 오류 상태도 건너뛰고 잘림 오류로 끝난다(잘림이 없으면 예전처럼 그 응답을 돌려준다). 시험 3개(503·404, 그리고 잘림 없는 경우의 기존 동작), 전체 508개.
5. **고침: 도달 실패의 재시도 수(CI).** 처음 판은 크기마다 2번만 시도해서(예전 4번), 모든 미러가 막힌 장애에서는 예전보다 빨리 멈췄다. 이 PR의 `Validate WD Subtype DA DB` 실행(run 46055319902, 70f7b03)이 바로 그렇게 끝났다: CDS XMatch 연결 시간 초과 → VizieR 스트라스부르 404 → IDIA 읽기 시간 초과(300 s) → "2번 중 2번" 실패. 크기와 무관한 실패이니 예전처럼 4번 시도해야 맞다. 이제 시도는 배치마다 최대 4번이고, 최소 크기보다 큰 배치만 **읽을 수 없는 응답이 2번** 나오면 멈추고 반으로 줄인다(`_batch_rows(..., halvable)`, `VIZIER_RETRIES = 4`, `VIZIER_RETRIES_UNREADABLE = 2`). 시험 2개: 세 번 시간 초과한 뒤 넷째 시도에서 받는 배치는 줄지 않고 끝까지 받는다(이전 판에서 실패); 읽을 수 없는 응답 2번이면 반으로 준다(8 → 4 → 2, 각 크기에서 다른 미러 두 곳). 전체 503개.
6. **확인 계획**: 병합 뒤 `Evaluate WD HR-locus gates`(main push로 자동 실행: 경로 조건에 `collect_star_gaia.py`가 없으면 수동 실행)와, 실사용 영역 하나(NGC 4522, 저장된 이전 수집과 같은 반경)의 수집 행 수 비교를 GitHub Actions에서 돌린다.
7. **실사용 수집 비교(병합 전, 같은 시각).** `v2_practical_probe.yml`을 main(5602935, run 46055402893)과 이 브랜치(70f7b03, run 46055407720)에서 같은 시각에 돌렸다(NGC 4522 2′, COSMOS 2′, 은하면 l = 30° b = −2° 1′; 원자료는 `validation-data`의 `practical_probe/<run>/`). 70f7b03은 미러 층의 잘림 판정을 모두 담고, 뒤 커밋은 잘린 답이 있을 때의 오류 순서와 `collect_star_gaia`만 바꾼다.

   | 영역 | 수집기 | 행 수 main / PR | 다른 수집기 | Gaia DR3 행 | 수집 단계 시간 main / PR |
   |---|---|---|---|---|---|
   | NGC 4522 | 30 / 30 | 1,128 / 1,128 | 없음 | 13 / 13 | 143 / 142 s |
   | COSMOS | 30 / 30 | 6,453 / 6,453 | 없음 | 18 / 18 | 76 / 88 s |
   | 은하면 | 30 / 30 | 1,155 / 1,250 | NED(main `error` 0행, PR `ok` 95행) | 349 / 349 | 57 / 62 s |

   - 표 내용도 비교했다. 두 실행 모두 읽은 수집기 표는 `DataFrame.equals`로 같았다(NGC 4522 26개, COSMOS 26개, 은하면 21개). 예외는 Pan-STARRS 하나다. 행 수는 같지만 NGC 4522에서 0.4″ 떨어진 PS1 천체 하나가 다른 objID로 왔다(MAST API 경로, VizieR 아님). COSMOS·은하면의 Pan-STARRS는 행 순서만 달랐다.
   - 은하면 NED의 차이는 main 쪽 실패다(`ExpatError`, NED의 XML 응답). NED는 `ned.ipac.caltech.edu`라 잘림 판정이 걸리지 않는다.
   - 시간 차는 러너 차이 수준이다. COSMOS는 1–7단계도 PR 쪽이 함께 느렸다(5.5 대 7.8 s 등).
8. **CI의 WD 워크플로(오늘의 CDS 장애).** PR의 세 WD 워크플로(`Evaluate WD HR-locus gates`, `Validate WD Subtype DA DB`, `Validate STAR WD Classifier`)는 6eddefa·b51d74b·dfb87e7에서 모두 "Crossmatch … to Gaia" 단계에서 실패했다. main에서도 같은 단계가 오늘 실패했다(run 46031822845, 18:18 UTC, 이 PR의 동기). 원인을 보려고 WD HR의 교차대조 단계에 미러별 요청 로그(`V2_HTTP_LOG=1`, 요청·결과 불변)를 켰다(dfb87e7, run 46061788161). 결과:

   | 미러 | 500개 위치 요청의 결과 (8번) |
   |---|---|
   | 스트라스부르 | 404, 1 s (모든 요청; 실사용 수집의 작은 원뿔도 404) |
   | CfA | 504, 매번 60.2 s(게이트웨이 시간 제한; 작은 원뿔은 같은 시각 3–4 s에 200) |
   | NAOJ / IUCAA | 연결 시간 초과 10 s |
   | China-VO | 연결 오류 0.2 s |
   | IDIA | 300 s 읽기 시간 초과 3번, 504 3번, 60 s 뒤 끊김 1번, **200 한 번(453 s)** |

   - CDS XMatch는 연결 시간 초과다. 첫 배치(500개)는 넷째 시도에서 IDIA가 453 s 만에 주었다. 둘째 배치는 4번 모두 실패해 오류로 끝났다.
   - 잘림은 한 번도 나오지 않았다. 이 PR이 고친 경로가 아니라 **모든 미러가 500개 위치 요청을 끝내지 못한** 장애다. 이전 코드도 같은 4번을 시도하고 같은 오류로 끝난다.
   - 이 PR의 판단(시도 수, 미러 순서, 잘림 우선)은 이 실패를 바꾸지 못하고 더 나쁘게 하지도 않는다.
   - **다음 과제 후보**(제안만): CfA의 60 s 504는 크기 신호로 보인다(같은 시각 작은 요청은 성공). 시간 초과·504도 "읽을 수 없는 응답"처럼 배치를 줄이는 근거로 쓰면 CfA가 작은 배치로 답할 수 있다. 다만 진짜 장애일 때 실패까지 걸리는 시간이 늘고(최대 12번 시도 × 약 7분), CfA가 몇 개 위치까지 60 s 안에 답하는지는 재 보지 않았다. 검토 세션이 판단할 일이다.
