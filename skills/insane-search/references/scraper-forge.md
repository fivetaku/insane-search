# Scraper Forge — 사이트 분석 → API 발굴 → 레시피/스크래퍼 생성

막힌 사이트를 "한 번 뚫고 끝"이 아니라 **재사용 가능한 수집기로 전환**하는 워크플로우.
특정 사이트 지식은 엔진 코드가 아니라 `recipes/` 데이터로만 축적한다.

## 4단계 흐름

### 1. Recon (발굴) — 세 갈래를 다 돌린다

| 갈래 | 도구 | 잡히는 것 |
|---|---|---|
| 정적 마이닝 | `scripts/endpoint_miner.py <URL>` | HTML/JS 번들 속 `/api/*`, `*.json` 후보 + 자동 프로브(JSON 응답 여부 랭킹) |
| 동적 캡처 | `engine/templates/network_capture_patchright.py` | JS 앱이 실제로 호출하는 XHR/fetch JSON 트래픽 (렌더 중 수집) |
| 문헌 조사 | WebSearch `"{site} scraping api endpoint"`, `"{site} graphql reverse engineer"` | 남이 이미 역공학해 공개한 엔드포인트 |

```bash
# 정적 마이닝 (레시피 디렉토리에 리포트 저장됨)
python3 scripts/endpoint_miner.py "https://example.com/app"

# 동적 캡처 (patchright 필요)
echo '{"url":"https://example.com/app","timeout":45000,"scroll":true}' \
  | python3 engine/templates/network_capture_patchright.py | jq '.network'
```

판정 기준: **HTML 페이지가 403/챌린지여도 `/api*` JSON이 200이면 승리 경로** — 마케팅 페이지만 WAF 중투자, API는 얕은 방어인 사이트가 많다(R7 가설).

### 2. Probe (검증)

발굴한 엔드포인트를 curl_cffi로 재현 호출한다:
- GET 파라미터 조합 확인 (페이지네이션, 쿼리 키)
- 필요 헤더/쿠키 최소화 (Referer, 지역 쿠키 등)
- 응답 스키마 기록 (상위 키 목록, 배열이 들어있는 키 이름)

### 3. Recipe (경량 저장) — `recipes/<domain>/`

엔진 코드가 아니라 **데이터**로 저장한다 (No-Site-Name Rule에서 observations와 같은 취급):

```
recipes/<domain>/
├── miner-report.json     # endpoint_miner 출력 (자동)
├── network.json          # network_capture 출력 (수동 저장)
└── recipe.yaml           # 정제한 최종 레시피
```

`recipe.yaml` 최소 스키마:
```yaml
domain: <domain>
verified_at: <date>
endpoints:
  - name: search
    url: /api/...              # 사이트 상대 경로
    method: GET
    params: {term: "{query}"}
    headers: {Accept: application/json}
    notes: HTML 페이지는 403이지만 이 API는 200
extraction:
  format: json                 # json | apollo_cache | html_selector
  list_key: items              # 배열이 들어있는 상위 키
limits: {rate: "0.5 req/s", known: "429 시 대기"}
```

### 4. Scraper (무거운 생성, 선택)

반복 사용이 확정되면 별도 스크립트 스크래퍼로 승격한다. 권장 계약:
- `bin/` 래퍼 + dispatcher 서브커맨드 (resolve → fetch → bundle)
- exit-code 계약: 0 성공 / 3 입력오류 / 4 모호성(후보 리스트) / 5 fetch 실패·rate-limit / 6 **스키마 drift — 업데이트 필요 신호**
- 결과는 JSON 파일로 저장, stdout은 요약 meta만
- schema drift 감지: 응답 상위 키가 recipe 기록과 다르면 exit 6

## forge가 끝난 도메인의 엔진 연동

레시피가 있는 도메인은 엔진 격자보다 **레시피 우선**:
1. `recipes/<domain>/recipe.yaml` 존재 확인
2. 있으면 엔드포인트 직행 (curl_cffi, 레시피 헤더/파라미터)
3. 레시피가 403/스키마 drift로 깨지면 → 엔진 일반 체인으로 폴백 + recipe에 `broken_at` 기록

> 이 연동은 현재 수행자(에이전트)가 SKILL 흐름에서 수동 적용. 자동 로더는 recipes가 쌓이면 추가한다.

## 금지선

- 레시피/스크립트는 `recipes/` 또는 별도 스킬 디렉토리에 — `engine/**`과 `waf_profiles.yaml`에 사이트명 하드코딩 금지 (bias_check 게이트)
- 발굴 과정에서 로그인 필요 영역·개인정보는 제외
- rate limit 준수: 같은 질의 반복 호출 금지, 429 응답 시 즉시 재시도 금지
