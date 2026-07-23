# 엔진 병합 완료 보고 — 2026-07-20

omo-senpi 측 `ultimate-browsing` 엔진과 본가 `insane-search` 엔진을 **동등하게** 병합했다.
이 문서는 실제로 수정·검증한 내용의 최종 정리다. (계획 문서는 `HANDOFF-2026-07-engine-merge.md`)

---

## 1. 결과 요약

- **본가(fivetaku/insane-search)**: 세션 델타를 병합 → **v0.10.0**, PR로 제출.
  - PR: https://github.com/fivetaku/insane-search/pull/10 (브랜치 `feat/omo-engine-merge`, 2 커밋)
- **omo 측(ultimate-browsing)**: 엔진을 본가와 **모듈 단위로 미러링** → 두 엔진 코드 동등.
- 검증: 본가 74개 기존 테스트 + 15개 신규 통과 / omo 동일 89개 통과 / 양측 `bias_check` clean / 라이브 스모크 통과.

병합 방향 결정: **본가 = SSOT**. 본가가 아키텍처 상위집합(R6 실패 게이트·learning·phase0·transport 풀·content-safety·diversity planner)이므로, 세션 델타를 본가에 반영한 뒤 omo 엔진을 본가로 미러링했다.

---

## 2. 반영한 개선 (세션 델타)

| 영역 | 내용 | 근거 |
|---|---|---|
| validators | 마커 매칭을 식별자 경계(lookbehind)로 — `octocaptcha` 토큰 오탐 제거. CF 인터스티셜 구조 마커(`window._cf_chl_opt`, `orchestrate/chl_page`) 크기 무관 즉시 challenge. 대형 본문 단일 SOFT 마커 → mention 격하 | 라이브 벤치 오탐 3종(github/medium/incolumitas) + 거짓 성공 1종(glassdoor 인터스티셜) |
| transport | curl_cffi 설치본 지원 집합과 impersonate 후보 교집합(버전 스큐 안전). avoid는 실증 블랙리스트 전용 | 프로파일 yaml이 설치본에 없는 타깃 나열 시 낭비 제거 |
| executor | `protocol_stealth_chrome`(nodriver raw-CDP → patchright channel=chrome). import-guard + `INSANE_AUTO_INSTALL` opt-in | 2026 공개 벤치: Playwright shim은 Runtime.enable 지문으로 최상위 게이트 전멸, nodriver만 0 blocked |
| waf_profiles | `kasada_ips`·`imperva_incapsula` 추가, akamai/cloudflare/datadome/perimeterx에 `needs_protocol_stealth` + fallback에 protocol stealth 삽입, akamai avoid에서 버전 가드 항목 제거 | 커버리지 확대 |
| scraper forge | `scripts/endpoint_miner.py`(정적 API 마이닝) + `engine/templates/network_capture_patchright.py`(동적 XHR 캡처) + `engine/recipe_loader.py` + `recipes/<domain>/recipe.yaml`. 레시피는 격자 전(Phase 0.5) 조회 — 막힌 HTML을 열린 JSON API로 rewrite | 네이버 블로그 섹션 12개 API 발굴 → recipe → `python3 -m engine`가 1 attempt로 69KB JSON |
| observations | fetch 결과를 `observations/*.jsonl`에 기록(경로 학습은 기존 `learning.py` 유지) | 프로파일 튜닝 근거 축적 |

**본가가 이미 독립적으로 해결해 둔 것**(중복 반영 안 함): 소형 완결 페이지 통과(`_looks_complete_content_page`), HARD/SOFT 마커 분리, 소형 JSON API 인식, 경로 학습(`learning.py`).

---

## 3. 라이브 벤치 (before/after, 14개 사이트)

- 성공률 **9/14 → 12/14** (정직 기준). 잔여 실패: example.com(설계상 selector 필요), glassdoor(CF 인터랙티브 챌린지 + IP 평판 = 무료 스택 물리 한계).
- 핵심 수확은 수치보다 **판정 정확도**: 거짓 차단 3건 구조 + 거짓 성공 1건 자가 검출.
- glassdoor는 R7(API-first) 실증 사례: HTML 403이지만 `api-web/employer/find.htm`은 200 JSON.

---

## 4. omo 측 PR이 불가한 이유

omo 변경분은 `oh-my-openagent` 리포에서 **`.gitignore`로 추적 제외**된 경로에 있다:

```
packages/omo-senpi/.gitignore
  /plugin/skills/          ← ultimate-browsing이 여기 위치
```

즉 `plugin/skills/**`는 upstream(code-yeongyu/oh-my-openagent)이 추적하지 않는 로컬 스킬이라, 이 경로 변경으로는 upstream PR을 만들 수 없다. omo 측은 **로컬에서 본가와 동등하게 동기화된 상태**로 두고, 정식 반영은 본가 PR #10 머지 후 본가를 재동기화하는 것이 올바른 경로다.

---

## 5. 남은 후속 작업

1. **PR #10 리뷰·머지** → 이후 marketplace(insane-plugins/marketplace) 서브모듈 포인터 업데이트 + 캐시 교체(AGENTS.md 체크리스트).
2. omo `ultimate-browsing`의 `SKILL.md`/`references/insane-search/*.md`가 구 엔진 모듈명(curl_probe/observations 등)을 참조 — 본가 모듈명(transport/observations_log/phase0)으로 문구 정합화(경미, 동작 무관).
3. glassdoor급: 레지덴셜 프록시 훅 또는 유료 언락커 폴백 티어(비용/키 필요 — 사용자 결정).
4. 레시피 로더 `endpoints` `{query}` 템플릿 치환(검색형 API 직행) + forge 실적 축적.

---

## 6. 검증 재현 커맨드

```bash
# 본가
cd skills/insane-search
for t in engine/tests/test_*.py; do PYTHONPATH=. python3 "$t"; done   # 89 pass
python3 engine/bias_check.py                                          # clean
python3 -m engine "https://section.blog.naver.com/" --json           # recipe → JSON

# omo
cd packages/omo-senpi/plugin/skills/ultimate-browsing
for t in engine/tests/test_*.py; do PYTHONPATH=. python3 "$t"; done   # 89 pass
python3 engine/bias_check.py                                          # clean
```
