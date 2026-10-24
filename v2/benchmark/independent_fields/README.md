# 독립 정답 검증 원자료 (별도 브랜치)

100개 영역의 원자료는 233 MB(영역마다 `objects*.csv.gz`, 정답 목록, `field.json`, 아카이브 상태)라서 main에 두지 않고 브랜치 **`validation-data`**에 보관한다.

- 점수표: `../independent_fields_scores/`
- 보고서: `../VALIDATION_32_FIELDS_2026-10-23.md`, `../VALIDATION_100_FIELDS_2026-10-24.md`

다시 채점하거나 실제 하늘 순도표를 다시 만들 때는 이 폴더에 원자료를 받는다.

```bash
git fetch origin validation-data
git checkout origin/validation-data -- v2/benchmark/independent_fields
python v2/benchmark/score_independent_fields.py --which blind --out /tmp/score
python v2/benchmark/natural_purity.py --desi-pred PRED_CSV --out /tmp/np
git restore --staged v2/benchmark/independent_fields && git checkout -- v2/benchmark/independent_fields/README.md
```

새 영역을 수집할 때는 `v2_independent_truth.yml`을 `validation-data` 브랜치에서 실행한다(workflow_dispatch, ref = validation-data). 워크플로는 실행한 브랜치에 결과를 커밋하며, main에서 실행하면 커밋 단계를 건너뛴다.
