# 리뷰용 — insane-search 엔진 병합 (2026-07-20)

> "insane-search 업데이트 다 됐냐?"에 대한 정확한 답과, 클로드코드에서 검토할 체크리스트.

## TL;DR

**코드 병합·검증·PR 제출까지 완료. 릴리스(머지→포인터→캐시→재시작)는 아직 안 됨.**

- ✅ 코드 수정 완료 (24 파일, +1473/-15)
- ✅ 검증 완료 (본가/omo 각각 89 테스트 통과, bias clean, 라이브 스모크)
- ✅ PR 제출: https://github.com/fivetaku/insane-search/pull/10 (3 커밋, `feat/omo-engine-merge`)
- ✅ 버전 0.9.1 → **0.10.0** (브랜치 내, main 반영은 머지 후)
- ⏳ **미완**: PR 리뷰·머지 / marketplace 서브모듈 포인터 / 캐시 교체 / installed_plugins.json / 재시작

즉 **네가 지금 검토하는 이 상태는 "머지 대기 중인 PR"**이고, 검토 후 머지해야 실제 배포가 시작된다.

---

## 1. 무엇이 바뀌었나 (파일별)

### 엔진 핵심
| 파일 | 변경 | 핵심 |
|---|---|---|
| `engine/validators.py` | +28/-? | 마커 lookbehind(octocaptcha 오탐 제거), CF 인터스티셜 구조 마커, SOFT 격하 |
| `engine/transport.py` | +21 | curl_cffi 런타임 타깃 필터 |
| `engine/executor.py` | +78 | `protocol_stealth_chrome`(nodriver→patchright) |
| `engine/fetch_chain.py` | +44 | recipe Phase 0.5 통합 + TLS 필터 적용 + observations 로깅 훅 |
| `engine/waf_profiles.yaml` | +64 | kasada/imperva 추가, needs_protocol_stealth, avoid 정리 |
| `engine/bias_check.py` | +8 | phase0 예외를 경로 접미사 매칭(스킬 디렉토리명 무관) |

### 신규 파일
| 파일 | 역할 |
|---|---|
| `engine/observations_log.py` | fetch 결과 JSONL 기록 (경로 학습은 기존 learning.py) |
| `engine/recipe_loader.py` | recipes/<domain>/recipe.yaml 로드·rewrite·XSSI 스트립 |
| `engine/templates/nodriver_fetch.py` | raw-CDP 스텔스 브라우저 |
| `engine/templates/patchright_fetch.py` | patchright channel=chrome |
| `engine/templates/network_capture_patchright.py` | 렌더 중 XHR/JSON 캡처 |
| `scripts/endpoint_miner.py` | 정적 API 후보 마이닝 + 프로브 |
| `references/scraper-forge.md` | 발굴→검증→레시피→스크래퍼 4단계 문서 |
| `recipes/section.blog.naver.com/recipe.yaml` | 실동작 예시(레시피→JSON) |
| `recipes/www.glassdoor.com/recipe.yaml` | 제약 문서화 예시(HTML 차단, API 일부 생존) |
| `engine/tests/test_u9_merge.py` | 신규 회귀 15종 |
| `tests/live_benchmark/bench.py` | before/after 벤치 하네스 |

### 문서
- `CHANGELOG.md` 0.10.0 항목, `SKILL.md` recipe/protocol-stealth/forge 반영
- `HANDOFF-2026-07-engine-merge.md` (계획·함정 원문)
- `MERGE-COMPLETE-2026-07-20.md` (완료 보고 상세)

---

## 2. 검토 포인트 (리뷰 시 집중해서 볼 것)

1. **validators.py 마커 규칙** — lookbehind만 쓰고 lookahead 금지(구조 마커가 더 긴 토큰의 접두사라서). `window._cf_chl_opt`가 정상 페이지에 없는지 재확인됨. SOFT 격하 임계값 20KB가 타당한지.
2. **recipe Phase 0.5 위치** — Phase 0(공식 API) 다음, 격자 전. R6 실패 게이트/trace와 정합.
3. **protocol stealth의 AGPL(nodriver)** — 배포 라이선스 관점. import-guard라 미설치 시 다음 fallback으로 진행하고, patchright(Apache-2.0)가 차선.
4. **recipes/ 공개 저장** — 사이트명이 데이터 파일에 들어가나 No-Site-Name Rule은 observations/recipes를 면제. engine 코드에는 사이트명 없음(bias_check clean).
5. **omo 미러링** — omo 엔진이 본가와 모듈 단위 동일. 단 omo `SKILL.md`/references는 구 모듈명 참조 잔존(경미, 동작 무관).

---

## 3. 검증 재현

```bash
cd skills/insane-search
for t in engine/tests/test_*.py; do PYTHONPATH=. python3 "$t"; done   # 89 pass
python3 engine/bias_check.py                                          # clean
python3 -m engine "https://section.blog.naver.com/" --json           # recipe → JSON 1 attempt
python3 -m engine "https://example.com/" --selector h1               # strong_ok
```

라이브 벤치(14개 사이트) 요지: **9/14 → 12/14**, 챌린지 오탐 3종 수정 + 거짓 성공 1종 자가 검출. 잔여 실패는 example.com(셀렉터 필요)·glassdoor(IP 평판 물리 한계)뿐.

---

## 4. 머지 후 릴리스 체크리스트 (AGENTS.md 기준)

1. [ ] PR #10 리뷰·머지 (main에 0.10.0 반영)
2. [ ] marketplace(insane-plugins/marketplace) `plugins/insane-search` 서브모듈 포인터를 머지 커밋으로 이동 + 커밋/푸시
3. [ ] 캐시 교체: 구 버전 삭제 → 신 버전 복사
4. [ ] `installed_plugins.json` installPath/version/gitCommitSha/lastUpdated 갱신
5. [ ] 캐시에 신 버전만 존재 확인
6. [ ] Codex 재시작

> 현재는 1번 이전 단계. **PR을 검토하고 머지 여부를 결정하면 그 다음부터 진행**한다.
