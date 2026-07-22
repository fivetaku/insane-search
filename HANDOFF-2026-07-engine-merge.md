# HANDOFF — insane-search 엔진 개선 머지 (2026-07-20 세션)

이 문서는 **다른 세션이 이어받아 바로 작업**할 수 있도록, 2026-07-20 세션에서
omo-senpi 측 엔진에 적용·검증한 개선 사항과, 그것을 이 본가 플러그인에
포팅하는 방법을 정리한다.

---

## 0. 두 리니지의 관계와 SSOT 결정 필요

| | 본가 (이 플러그인) | omo-senpi 측 사본 |
|---|---|---|
| 경로 | `/Users/chulrolee/insane_plugins/plugins/insane-search/skills/insane-search/` | `/Users/chulrolee/oh-my-openagent/packages/omo-senpi/plugin/skills/ultimate-browsing/` |
| 역할 | 마켓플레이스 배포용 플러그인 (Claude/Codex) | omo-senpi 스킬의 Tier-1 엔진 (`ultimate-browsing`의 일부) |
| 강점 | R6 실패 게이트, learning.py, content_safety/safety, phase0, coverage_battery, HARD/SOFT 마커, patchright JS 템플릿 | 이번 세션 개선 전부 적용·벤치 검증 완료 (아래 §2) |

**문제**: 두 엔진이 이미 발산했다. 한쪽에만 있는 기능이 양방향으로 존재.
**권고**: 본가를 SSOT로 정하고, omo-senpi 측은 본가에서 주기적으로 동기화.
이 문서의 포팅(§3)이 끝나면 omo 측에 본가의 R6/learning/phase0를 역포팅(§4)하거나,
omo 측 엔진을 본가 서브모듈/심링크로 대체하는 것을 검토.

---

## 1. 이번 세션에서 실측으로 확정한 사실들

벤치: 14개 타겟(컨트롤 3 + 글로벌 WAF 8 + 한국 3) × before/after × cold/warm 2회.
하네스: `/tmp/insane-bench/bench.py` (휘발성 — §5.4에 이관 지시).

- **성공률 9/14 → 12/14** (정직한 기준). 잔여 2개: example.com(설계상 selector 필요), glassdoor(물리 한계).
- 발견·수정한 버그 5종 (전부 라이브 사이트로 재현 확인):
  1. **마커 서브스트링 오탐** — github의 feature-flag `octocaptcha_origin_optimization`이 `captcha` 마커에 걸려 github/medium이 차단 오판. → 식별자 lookbehind 정규식으로 해결.
  2. **브랜드 마커 언급 오탐** — 봇 탐지 블로그 본문 속 "datadome" 언급이 challenge 오판. → 브랜드 마커는 대형 본문(>20KB) 단일 히트 시 mention으로 격하.
  3. **거짓 성공(더 위험)** — CF 한국어 인터스티셜("잠시만 기다리십시오…", 312KB)이 weak_ok로 유입. → 구조 마커(`window._cf_chl_opt`, `orchestrate/chl_page`)는 크기 무관 즉시 challenge. **lookahead은 쓰면 안 됨**(마커가 더 긴 토큰의 접두사로 쓰이는 경우를 죽임 — `window._cf_chl_opt` 등).
  4. **정적 소형 페이지 fallback 낭비** — 559B 완결 페이지에 브라우저 fallback 11초. → tiny_body + `<script>` 없음이면 fallback 스킵 (SPA 셸은 유지).
  5. **glassdoor "성공" 허상** — nodriver로 받은 312KB가 실은 인터스티셜. **weak_ok라도 내용을 열어 확인하는 절차** 없이는 성공 선언 금지라는 교훈.
- **CF 인터스티셜 + IP 평판급(glassdoor)은 물리 한계**: nodriver/patchright 40초 대기, Jina Reader 모두 차단. 레지덴셜 프록시 또는 유료 언락커 필요.
- **R7(API-first) 실증**: glassdoor HTML 403인데 `/api-web/employer/find.htm`는 200 JSON. 마케팅 페이지만 WAF 중투자인 사이트가 많다.
- **성공 캐시 효과**: 재방문 3att/2.3s → 1att/0.23s (10배).
- 외부 증거 (2026 공개 벤치, 651 verdict): Playwright shim 계열은 Runtime.enable 지문으로 최상위 게이트에서 패치 무관하게 실패, nodriver(raw CDP)만 0 blocked, curl_cffi는 CloakBrowser와 동점. → protocol stealth executor의 근거.

---

## 2. omo 측에 적용된 개선 (포팅 대상 전체)

소스 루트: `/Users/chulrolee/oh-my-openagent/packages/omo-senpi/plugin/skills/ultimate-browsing/`

| # | 개선 | 파일 | 검증 |
|---|---|---|---|
| A | 성공 캐시 + fetch 자동 로깅 | `engine/observations.py` (신규), `fetch_chain.py` Phase 0.5 | E2E 캐시 히트 확인 |
| B | TLS 타겟 런타임 필터 | `curl_probe.py` `available_impersonates()/filter_available()` | skew-guard 테스트 |
| C | protocol stealth executor (nodriver→patchright) | `engine/executor.py` `_run_protocol_stealth`, `templates/nodriver_fetch.py`, `templates/patchright_fetch.py` | glassdoor 실투입 확인 |
| D | WAF 프로파일: kasada_ips, imperva_incapsula 추가 + akamai avoid 정리(chrome145/146 제거) + CF/datadome/perimeterx에 `needs_protocol_stealth` | `engine/waf_profiles.yaml` | 감지 테스트 |
| E | validator 2단계 마커 (구조/브랜드) + lookbehind + 크기/동시출현 규칙 | `engine/validators.py` | 회귀 테스트 5종 |
| F | 정적 소형 페이지 fallback 스킵 | `fetch_chain.py` Phase 3 앞 가드 | 테스트 2종 |
| G | scraper forge: 정적 마이너 + 동적 캡처 + 레시피 컨벤션 | `scripts/endpoint_miner.py`, `templates/network_capture_patchright.py`, `recipes/`, `references/insane-search/scraper-forge.md` | 네이버 섹션 12개 API 발굴 |
| H | 레시피 자동 로더 (Phase 0.4, XSSI 스트립 포함) | `engine/recipe_loader.py` (신규) | 라이브: 메인→ajax JSON 1 attempt |
| I | 레시피 실물 2건 (glassdoor=partial, naver section=active) | `recipes/<domain>/recipe.yaml` | 라이브 검증 |
| J | 문서: validator 규칙, 물리적 한계, forge 가이드 | `references/insane-search/README.md` | — |

⚠️ **중복 주의**: A(성공 캐시)는 본가 `learning.py`와 기능이 겹친다.
`observations.py`의 **JSONL 자동 로깅만** 가져오고, 성공 조합 저장은
본가 `learning.py`로 통일하는 것을 권고 (§3-A 참조).

---

## 3. 본가 포팅 계획 (순서대로)

### A. observations 로깅 (learning.py와 병존)
- **하지 말 것**: `observations.py` 통째 복사 → learning.py와 이중 저장.
- **할 것**: `observations.py`에서 `log_fetch()`만 가져와 `observations/fetch-*.jsonl` 기록.
  성공 조합 저장은 기존 `learning.record_success()`가 담당 (더 정교함: TTL, strike, device 키).
- 대상: 본가 `engine/fetch_chain.py`의 결과 반환 지점들에 log_fetch 호출 추가.

### B. TLS 런타임 필터
- omo `curl_probe.py`의 `available_impersonates()`를 본가 `transport.py`로 이식
  (본가는 transport 레이어가 분리돼 있음 — 거기가 정확한 자리).
- `filter_available()`을 본가 `fetch_chain.py`의 격자 구성 지점에 적용.
- 본가 `waf_profiles.yaml`의 `tls_impersonate_avoid`에서 **버전 가드 목적 항목 제거**
  (실증 블랙리스트만 남김 — 런타임 필터가 버전은 처리).

### C. validator 2단계 마커 (본가 HARD/SOFT 위에 개량)
본가는 이미 HARD/SOFT 분리가 있다. 그 위에 세 가지만 추가:
1. **lookbehind 정규식** — `_hard_marker_hits`/`_soft_marker_hits`가 단순 `in` 검색.
   `(?<![a-z0-9_])` + `re.escape(marker)` 패턴으로 교체. **lookahead은 절대 넣지 말 것** (§1-3).
2. **HARD에 구조 마커 추가**: `window._cf_chl_opt`, `orchestrate/chl_page`.
   주의: `/cdn-cgi/challenge-platform/`, `window._cf_chl`(opt 없음)는 **정상 페이지에도 심어지는** 경우가 있어 제외.
3. **SOFT 격하 규칙**: 본문 >20KB + 단일 SOFT 히트면 `marker_mention`으로 격하(challenge 아님),
   2개 이상 동시 히트는 유지. omo `validators.py`의 Layer 1 로직 참조.
- 회귀 테스트 필수 (omo `tests/test_memory_and_filter.py`의 MarkerWordBoundary/MarkerMentionDowngrade/StructuralMarkerAtAnySize 클래스 이식).

### D. protocol stealth executor
- omo `templates/nodriver_fetch.py`, `templates/patchright_fetch.py` 복사.
- 본가 `executor.py`에 `_run_protocol_stealth` 이식 (nodriver 우선, patchright 차선,
  미설치 시 Attempt 에러 후 다음 fallback 진행, `INSANE_AUTO_INSTALL=1` 옵트인 자동설치).
- `waf_detector.py` capabilities 라우팅에 `needs_protocol_stealth` 추가.
- 주의: 본가 JS 템플릿은 이미 node patchright를 쓴다 — **충돌 아님**, protocol stealth는
  "Playwright shim 자체를 안 쓰는" 상위 단계로 추가하는 것.
- `waf_profiles.yaml`: cloudflare/akamai/datadome/perimeterx에 capability 추가 +
  fallback_when_challenge에 `protocol_stealth_chrome` 삽입.

### E. 신규 WAF 프로파일
- omo yaml에서 `kasada_ips`, `imperva_incapsula` 복사.
- omo 측에만 있던 `f5_big_ip`도 본가에 없으니 함께 복사 (omo yaml 참조).

### F. 정적 소형 페이지 fallback 스킵
- omo `fetch_chain.py` Phase 3 앞 가드 이식. 조건: status 200 + verdict challenge +
  reasons가 tiny_body/size_fp뿐 + 본문에 `<script` 없음 → fallback 스킵 + trace에 사유 기록.

### G. scraper forge + 레시피 로더
- `scripts/endpoint_miner.py` → 본가 `scripts/` (없으면 생성) 또는 `tests/` 옆.
- `templates/network_capture_patchright.py` 복사.
- `engine/recipe_loader.py` 이식 + fetch_chain에 Phase 0.4 삽입 (격자 전).
  - XSSI 스트립(`)]}',` 첫 줄) 로직 포함 — 네이버 계열 ajax가 이 가드를 쓴다.
  - CSRF 주의: 일부 ajax는 `Referer` + `X-Requested-With` 필수 (recipe.yaml에 헤더 기록).
- `references/`에 `scraper-forge.md` 추가, `recipes/` 디렉토리 + `.gitignore` 확인.
- 본가 `bias_check.py`의 EXCLUDED_DIR_NAMES에 `observations`, `recipes` 추가 필요 여부 확인
  (recipes는 engine/ 밖이라 기본 스캔 대상 아님 — 스캔 범위 바뀌면 필요).

### H. SKILL.md 하네스 규칙 갱신
- 본가 R6(실패 게이트)는 omo 것보다 상위호환 — **유지**.
- R1 지시문에 "레시피 존재 시 자동 우선(Phase 0.4)" 한 줄 추가.
- Phase 0 표 아래에 scraper-forge.md 링크 추가.

---

## 4. 본가 → omo 역포팅 (별도 작업)

omo 측 ultimate-browsing에도 가져가야 할 본가 기능:
- **R6 실패 게이트** (`untried_routes`, `must_invoke_playwright_mcp`, `stop_reason`, grid_exhausted) — omo fetch_chain은 그냥 포기한다.
- **learning.py** — omo observations 캐시보다 정교. omo 측 캐시를 learning.py로 교체.
- **phase0.py, content_safety.py, safety.py** — omo에 없는 모듈.
- **coverage_battery.py** — Phase-0 라우트 부패 감지. omo tests에 추가.

---

## 5. 검증 절차

### 5.1 단위/회귀
```bash
# 본가
cd /Users/chulrolee/insane_plugins/plugins/insane-search/skills/insane-search
python3 -m unittest discover -s engine/tests -v
python3 engine/bias_check.py

# omo 측
cd /Users/chulrolee/oh-my-openagent/packages/omo-senpi/plugin/skills/ultimate-browsing
python3 -m unittest discover -s engine/tests -v   # 현재 41개 OK
python3 engine/bias_check.py
```

### 5.2 라이브 스모크
```bash
python3 -m engine "https://example.com/" --selector h1 --trace   # strong_ok, 1 attempt
python3 -m engine "https://section.blog.naver.com/" --json       # recipe → ajax JSON (레시피 이식 후)
```

### 5.3 coverage battery (Phase-0 라우트)
```bash
python3 tests/coverage_battery.py --json
```

### 5.4 before/after 벤치
`/tmp/insane-bench/bench.py`를 본가 `tests/live_benchmark/`로 이관할 것 (휘발성 /tmp).
타겟 리스트는 한국 사이트 추가 갱신 권장. 실행:
```bash
python3 tests/live_benchmark/bench.py <engine_dir> out.json <label>
```

### 5.5 성공 선언 전 수동 확인 규칙
weak_ok라도 **내용을 열어** 인터스티셜 여부 확인 (`window._cf_chl_opt` grep).
이번 세션의 glassdoor 거짓 성공이 이 절차 부재에서 나왔다.

---

## 6. 함정 목록 (다시 겪지 말 것)

1. **lookahead 금지** — 마커 정규식은 lookbehind만. 마커가 더 긴 토큰의 접두사인 경우가 흔하다.
2. **CF 마커 이중성** — `/cdn-cgi/challenge-platform/`, `window._cf_chl`(opt 제외)는 정상 페이지에도 심어진다. 인터스티셜 전용은 `window._cf_chl_opt`, `orchestrate/chl_page`.
3. **거짓 성공이 거짓 차단보다 위험** — 큰 바디 + 약한 마커 조합이면 의심.
4. **XSSI 프리픽스** — `)]}',\n` 첫 줄 제거 후 JSON 파싱 (naver ajax 등).
5. **CSRF 헤더** — ajax 직행은 `Referer`+`X-Requested-With`가 필요한 경우가 많다. 200인데 56바이트 `{"result":{"code":"csrf"}}`가 오면 헤더 문제.
6. **CDN 번들** — 엔드포인트 마이닝 시 same-origin 필터 금지. 앱 코드는 CDN에 있다.
7. **learning.py vs observations.py** — 성공 조합 저장은 learning.py 단일화. observations는 로그만.
8. **bias_check** — `captcha-delivery.com` 같은 벤더 아티팩트는 URL_ALLOWLIST에 "제품 식별자" 주석 달고 등록. 사이트명은 절대 금지.
9. **curl_cffi 버전 스큐** — 프로파일 yaml의 impersonate 후보는 설치본과 무관하게 적을 것. 런타임 필터가 교집합을 취한다. avoid 리스트는 실증 블랙리스트 전용.
10. **glassdoor급** — 코드로 해결 불가. 프록시/유료 티어/사람 쿠키 주입 중 선택. 이 사실을 실패 보고에 명시 (거짓 희망 금지).

---

## 7. 다음 로드맵 (우선순위)

1. §3 포팅 (A~H) — 이번 세션 분의 본가 반영
2. §4 역포팅 (R6, learning, coverage_battery) — omo 측 정합성
3. 레시피 자동 로더 완성도: `endpoints`의 `{query}` 템플릿 치환 지원 (검색형 API 직행)
4. 유료 언락커 폴백 티어 (ScrapFly/ZenRows 키 발급 후) — glassdoor급 대응
5. 레지덴셜 프록시 훅 (curl_cffi proxy 파라미터 + shape coherence 문서)
6. forge 실적 축적: 막힌 사이트 만날 때마다 forge → recipes/ 축적 → 주기적 recipe 검증 배터리
