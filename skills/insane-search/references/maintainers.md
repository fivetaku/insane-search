# insane-search — maintainer notes

Moved out of SKILL.md (2026-11 modernization). Needed when changing the engine, profiles or
dependencies — not for ordinary fetches.

## Bias rules (R3/R4)

**R3 — 편향 금지**: `engine/**`, `waf_profiles.yaml`에 특정 사이트 도메인·셀렉터·브랜드명 하드코딩 금지. `python3 engine/bias_check.py`가 CI 게이트. 자세한 규칙은 **No-Site-Name Rule** 섹션.

**R4 — 힌트는 런타임에만**: 사이트 고유 정보(성공 셀렉터, 우선 Referer)는 CLI 인자 또는 `user_hint`로만 전달, 저장소에 고정 금지.

## Dependencies (auto-install details)

최초 호출 시 필요 패키지를 자동 설치한다. **curl_cffi는 0.15.0 이상**을 요구한다 — 0.15부터
`impersonate="chrome"`이 최신 Chrome(146+) 지문으로 갱신되고(0.14는 chrome142에 고정), HTTP/3 지문과
SSRF-safe redirect 기본값이 추가됐다. 아래 가드는 **미설치뿐 아니라 0.15 미만이면 업그레이드**한다:
```bash
python3 -c "import curl_cffi,bs4,yaml,pypdf,markdownify; v=curl_cffi.__version__.split('.'); assert (int(v[0]),int(v[1]))>=(0,15)" 2>/dev/null \
  || pip install -U "curl_cffi>=0.15.0" beautifulsoup4 pyyaml pypdf markdownify -q
```

**콘텐츠 처리 — 기본 동작 + 선택 라이브러리.** 엔진의 실사용자는 대개 LLM 컨텍스트에 넣으려는 에이전트라, 깨끗한 마크다운을 **기본으로** 준다. 라이브러리가 없으면 전부 raw 폴백으로 정상 동작한다(graceful degradation):
- `markdownify`(MIT, 위 가드로 자동 설치) — **기본 ON**: raw HTML → 구조보존 마크다운(표→파이프표, `<pre>/<code>`→펜스). `extraction_source`가 `raw+md`. 끄려면 `--no-markdown` / `enable_markdown=False`(raw HTML 그대로).
- `resiliparse`(Apache-2.0) — **opt-in**: `--maincontent` / `enable_maincontent=True`. nav/footer/광고 제거 후 본문만(`extraction_source`=`maincontent`), markdown보다 우선. 비-article 페이지에선 본문을 과하게 잘라낼 수 있어 기본 off로 둔다.
- `pdfplumber`(MIT) — **자동**: PDF 본문을 pdfplumber(다단컬럼·표 우수) 우선 추출, 미설치 시 pypdf 폴백. **`pymupdf4llm`/`PyMuPDF`는 AGPL이라 사용 금지.**
```bash
pip install resiliparse pdfplumber -q   # 본문추출(opt-in)·PDF 개선을 원할 때
```

실패(`ok=False`) 응답에는 `block_class`가 붙는다 — `bot_detection`(라우트 결과가 엇갈리거나 WAF 시그널 → 브라우저·다른 라우트로 우회 가능) vs `infra_or_auth`(모든 라우트가 균일하게 401/404 → 스텔스로 우회 불가). 재시도 가치 판단에 사용한다.

Playwright 로컬 경로 사용 시 Node가 필요하다. **Node 의존성은 첫 브라우저 폴백에서 자동 설치된다** — `~/.insane-search/node`에 한 번 설치해 플러그인 버전이 올라가도 재사용하고, `NODE_PATH`로 템플릿에 주입한다. (`engine/templates/node_modules`는 gitignore라 마켓플레이스 설치본에는 애초에 없다 — 예전에는 이 때문에 마지막 폴백이 `Cannot find module 'playwright'`로 항상 죽었다.) 번들 Chromium은 받지 않는다(`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`) — 템플릿이 `channel:'chrome'`로 **시스템 Chrome**을 쓰기 때문. **Patchright**는 Playwright drop-in 포크로, Cloudflare/DataDome이 감지하는 CDP `Runtime.enable` 누출을 막아준다 — 설치돼 있으면 최우선 사용하고, 없으면 playwright-extra+stealth → plain playwright로 폴백한다. 수동 설치가 필요하면:
```bash
mkdir -p ~/.insane-search/node && cp "${CLAUDE_PLUGIN_ROOT}/skills/insane-search/engine/templates/package.json" ~/.insane-search/node/
cd ~/.insane-search/node && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install
```

## No-Site-Name Rule

`engine/**`, `waf_profiles.yaml`, `engine/templates/**` 파일에는 **특정 사이트의 도메인/URL/셀렉터/브랜드명을 하드코딩하지 않는다**.

### 금지

- `"coupang.com": {...}` 같은 사이트별 레지스트리 엔트리
- `if "coupang" in url: ...` 같은 도메인 분기
- WAF 프로파일 `notes`에 특정 사이트 이름이나 경험적 byte 크기 박제

### 허용

- `SKILL.md` / `references/*.md`의 **설명 텍스트**에 사이트 이름 예시 (독자 이해용)
- `Phase 0` 공식 API 인덱스 (플랫폼이 공식 공개한 엔드포인트)
- `observations/*.jsonl` 로그 (append-only 관측 데이터 — 코드 경로에 영향 없음)
- 호출자가 제공하는 `success_selectors`, `user_hint` (현재 호출에만 유효)

### 경계 사례 판단 기준

> "이 엔트리가 다른 사이트에서도 같은 WAF를 쓰면 일반적으로 유효한가?" → YES면 `waf_profiles.yaml`, NO면 runtime hint.

### 새 사이트가 안 뚫릴 때

1. 먼저 `result.trace`에서 어느 phase가 실패했는지 확인
2. 사용자의 `user_hint`로 1회 재시도
3. 반복 성공 패턴이 관측되면 `observations/`에 로그 (아직 자동 기록 없음 — 수동)
4. 3회+ 반복 확인되고 **동일 WAF를 쓰는 다른 사이트에도 유효**하면 `waf_profiles.yaml` 해당 프로파일의 `tls_impersonate_candidates` / `url_transform_order`를 튜닝 (사이트명 절대 넣지 않음)
5. 여전히 안 되면 새 WAF 프로파일 후보 검토 (예: DataDome 세부화, Kasada 등)

## Engine code map

| 파일 | 언제 읽는가 |
|------|-------------|
| `engine/phase0.py` | Phase 0 공식-API 라우터 (Reddit/X/YouTube 자동 경로). 플랫폼·경로 추가 시. bias_check 면제 파일(R5 sanctioned) |
| `engine/fetch_chain.py` | 체인 단계 로직·`Attempt`/`FetchResult` schema·`untried_routes`/`must_invoke_playwright_mcp` 실패게이트 |
| `engine/validators.py` | 4-계층 검증 세부 (Verdict 분류, 챌린지 마커 목록) |
| `engine/waf_detector.py` | WAF 랭킹 감지 알고리즘, `_LAST_LOAD_ERROR` 처리 |
| `engine/waf_profiles.yaml` | 프로파일별 detectors·tls_candidates·capabilities_needed |
| `engine/url_transforms.py` | URL 변환 규칙 추가할 때 |
| `engine/executor.py` | Playwright MCP vs local capability 매칭 로직 |
| `engine/templates/*.js` | Playwright 템플릿 튜닝 (warmup, reload, devices) |
| `engine/bias_check.py` | 편향 린터 규칙 — brand denylist, URL_PATTERN, excluded dirs |
