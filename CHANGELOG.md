# Changelog

## 0.16.0 — 2026-08-27

- **마지막 브라우저 폴백이 설치본에서 항상 죽던 문제 수정.** `engine/templates/node_modules`가 gitignore라 마켓플레이스 설치본에는 Node 의존성이 없었고, `playwright_real_chrome`/`playwright_mobile_chrome` 폴백은 매번 `Cannot find module 'playwright'`로 즉사했다. 이제 첫 브라우저 폴백에서 `~/.insane-search/node`에 한 번 설치해 플러그인 버전이 올라가도 재사용하고, `NODE_PATH`로 템플릿에 주입한다. 번들 Chromium은 받지 않는다(템플릿이 `channel:'chrome'`로 시스템 Chrome을 사용).
- **CDP 레인(nodriver)·patchright 레인을 headful로 전환.** headless Chrome은 지문 이전에 신호만으로 봇 점수를 먹어 Cloudflare 챌린지를 통과하지 못했다. Playwright 템플릿과 동일하게 `headless=false`가 기본이며 `{"headless": true}`로 덮어쓸 수 있다.
- **`unknown_challenge` 프로파일에 `protocol_stealth_chrome` 추가.** 저신뢰 탐지로 이 프로파일에 떨어지면 MCP 스텁 → Playwright 순뿐이라 CDP 레인을 아예 건너뛰었다.
- 실측: Cloudflare Turnstile 페이지에서 이전 = 전 라우트 실패, 이후 = nodriver 7.8s `weak_ok`(49KB) / `playwright_real_chrome` 200 (1.2MB).


## 0.15.0 — 2026-08-24

- **X keyword discovery now works without Grok and improves automatically when xAI is available.** Free Brave and Yahoo discovery run in parallel, optional native xAI `x_search` joins when `XAI_API_KEY` or local OMO xAI OAuth is available, and every candidate URL is revalidated through the public tweet-result endpoint before it is returned.
- **Research-grade provenance.** Results expose contributing discovery sources, provider-specific errors, rejected URLs, and per-post discovery attribution. Free-only operation is available through `--free-only` or `INSANE_SEARCH_XAI=off`.
- **Live regression coverage.** The X coverage battery now verifies keyword discovery plus deterministic post extraction, in addition to the existing timeline, tweet-result, and oEmbed routes.


## 0.14.1 — 2026-08-24

- **Fix: first-run setup could wipe `settings.json`** — if the file was corrupted or contained comments (JSONC), the shared update-notifier installer re-wrote it as an empty object plus the hook, silently destroying all user settings. It now refuses to write when parsing fails and writes atomically (tmp + rename). Marketplace-wide propagation of the fix found in the ddiring v0.1.1 external review; reproduction-verified.

## 0.14.0 — 2026-08-06

Removed — 내부/비공개 API 발굴 서브시스템 + 특정 사이트 예시 (범위 축소 · dual-use 정직화).

- `scripts/endpoint_miner.py`(정적 API 프로빙), `engine/auto_forge.py`(자동 내부 API 역공학), `engine/recipe_loader.py`, `engine/templates/network_capture_patchright.py`, `recipes/`(사이트별 레시피) 전면 제거. fetch 체인의 recipe(Phase 0.5)·auto_forge(Phase 4) 단계와 SKILL.md의 R7(API-first 정찰 분기)·R6의 내부 엔드포인트 탐지 지시도 함께 삭제.
- 문서의 특정 사이트 우회 예시를 WAF-제품 기준 일반 가이드로 치환(No-Site-Name 원칙 확장). 남는 기능은 공식 공개 API·피드·메타데이터·범용 impersonation 체인으로 한정.
- DISCLAIMER/README를 실제 동작에 맞게 정직화: "보안장치를 절대 우회하지 않는다"류 단정을 제거하고 dual-use + 사용자 책임을 명시.
- 엔진 테스트 전수 통과, bias_check green.

## 0.13.0 — 2026-07-29

Added — Threads 영상 라우트 (Phase 0).

- yt-dlp에 익스트랙터가 없어 media 경로로 커버 불가하던 Threads(threads.com/threads.net) 영상 포스트를 Phase 0 라우터가 직접 처리: curl_cffi safari 지문 익명 GET → 인라인 JSON에서 URL shortcode(`"code":"…"`) 최근접 `video_versions` 블록 선택(페이지에 관련 포스트 영상 블록이 다수 혼재하므로 필수) → `\/`·유니코드 이스케이프 해제 → 서명 CDN URL 목록을 `{"post_code","video_urls"}` JSON으로 반환. 다운로드는 engine 밖 — 서명 URL은 plain curl로 충분(실측: h264+AAC progressive).
- 영상 없는 포스트·프로필 URL은 ok=False로 일반 체인 폴백 — 라우트가 콘텐츠 종류를 삼키지 않는다.
- `tests/coverage_battery.py`에 threads 케이스 추가, SKILL.md/PLATFORMS.md/references/media.md 문서화(서명 URL 만료·DASH-only·캐러셀 미검증 경계 포함).

## 0.12.1 — 2026-07-23

Fixed — 429 대응·브라우저 예산 (검증 리서치 후속).

- 429(rate-limit)가 TLS 그리드를 멈추는 것을 넘어 브라우저 폴백까지 차단하던 결함 수정 — TERMINAL 셋의 "그리드 중단"과 "벽(브라우저도 무익)" 역할을 분리(`_BROWSER_FUTILE_VALUES`=auth/404). 429 중단 시에도 브라우저 폴백과 R6 백오프 안내가 살아있다.
- Playwright MCP 스텁(파이썬에서 실행 불가 안내용)이 브라우저 예산(max_browser_attempts=2)을 소진해 cloudflare_turnstile 프로필에서 실제 Chrome 폴백이 굶던 결함 수정 — 스텁은 attempts에 기록만 하고 예산은 소비하지 않음.
- 회귀 테스트 `engine/tests/test_t7_browser_gate.py` 5종 추가(오프라인 모킹): 429→브라우저 진행 / 404→스킵 / 스텁 예산 무소비·실행 순서 / 예산 상한 유지 / 스텁 무동작.

## 0.12.0 — 2026-07-23

Adaptive-access engine improvements (verified before/after: 9/14 → 12/14 on a 14-site live bench). Additive to the 0.11.0 content-quality / retry / rescue work.

- **Validator false-positive fixes**: challenge markers now use identifier-boundary matching (a feature-flag token ending in `captcha` is no longer a challenge); CF interstitial structural markers (`window._cf_chl_opt`, `orchestrate/chl_page`) are decisive at any body size; a single SOFT marker inside a large body (>20KB) is treated as a content mention, not a block.
- **curl_cffi runtime target filter**: TLS impersonate candidates are intersected with the installed curl_cffi's supported set, so version skew never wastes attempts; profile `tls_impersonate_avoid` keeps empirical blacklists only.
- **Protocol-stealth fallback**: new `protocol_stealth_chrome` executor drives nodriver (raw CDP, no Playwright shim) then patchright (channel=chrome) for gates that fingerprint the automation protocol; import-guarded, opt-in auto-install.
- **New WAF profiles**: `kasada_ips`, `imperva_incapsula`; `needs_protocol_stealth` added to Akamai/Cloudflare/DataDome/PerimeterX.
- **Scraper forge** (opt-in; **removed in 0.14.0**): added an internal-JSON-API discovery/recipe path. Removed — the engine now stays on generic public-access routes only.
- **Observations log**: every fetch outcome appended to `observations/*.jsonl` for profile tuning (route learning remains in `learning.py`).
- **auto-forge** (opt-in; **removed in 0.14.0**): added an on-the-fly internal-API discovery fallback. Removed in 0.14.0.

## 0.11.0 — 2026-07-23

Content-quality + diagnosis upgrades (research P0 batch). All new libraries are
optional with graceful degradation — the engine still runs (raw fallback) when
they are absent. No public-API break; `content` becomes markdown by default on
the raw-HTML success path (opt out with `--no-markdown` / `enable_markdown=False`).

- **markdownify (MIT), default ON**: a raw-HTML success is converted to
  structure-preserving markdown (tables → pipe tables, `<pre>/<code>` → fenced
  blocks; script/style/head noise stripped first). `extraction_source` becomes
  `raw+md`. The engine's consumers are usually agents feeding an LLM, so clean
  markdown is the natural default; `enable_markdown=False` restores raw HTML.
  markdownify is now in the base dependency auto-install guard.
- **resiliparse (Apache-2.0) main-content extraction, opt-in**
  (`--maincontent` / `enable_maincontent=True`): strips nav/footer/sidebar/ads
  to the article body (`extraction_source=maincontent`), wins over markdown when
  both are on. Opt-in because it can over-trim non-article pages; rejects a
  near-empty extraction and keeps raw.
- **pdfplumber (MIT) PDF extraction, automatic**: `_extract_pdf` tries
  pdfplumber first (better multi-column / table handling) and falls back to
  pypdf. `pymupdf4llm` / `PyMuPDF` are AGPL and are intentionally NOT used.
- **Differential block classification**: on failure, `_classify_block` compares
  the outcomes of the routes already tried and sets `FetchResult.block_class` —
  `bot_detection` (routes disagree or a WAF/challenge signal → escalation may
  help) vs `infra_or_auth` (every route uniformly 401/404 → stealth can't help).
  Additive JSON field; no new dependency. (Idea: Bamberg arXiv:2606.14525 §5.3.)
- Tests: +25 (test_t3_markdown 8, test_t4_maincontent 5, test_t5_pdfplumber 6,
  test_t6_differential 7 — network-free); full engine suite green, live e2e +
  all-libraries-blocked graceful degradation verified.

## 0.10.1 — 2026-07-22

Parser-input ceilings for the v0.10.0 content-rescue paths (hardening
requested in downstream security review — every byte reaching a rescue
parser is attacker controlled):

- **`_SCAN_LIMIT` (2M chars)**: rescue regexes (title / visible-text /
  JSON-LD discovery) only ever scan a bounded prefix of the body; the raw
  `content` surface still carries the full text (that contract predates
  the chain).
- **JSON-LD**: at most 10 `ld+json` blocks parsed per page, blobs over
  200K chars are skipped before `json.loads`, joined output capped at 1M.
- **PDF**: bodies over 25MB are rejected before `PdfReader` ever sees them
  (`pdf_too_large`) — decompression bombs are bounded at their input, not
  their page count; extracted text capped at 1M chars (80-page cap kept).
- **innerText**: capped at 1M chars twice — at the executor's envelope
  parse boundary and again before the render-merge gate.
- Regression tests at every ceiling: 7 new in `test_t2_rescue.py`
  (block count / blob size / output cap / scan window / pdf-too-large /
  pdf text cap / innerText cap) + 1 in `test_u4.py` (envelope boundary).
  Suite 91 green; live E2E battery unchanged (ordinary-path overhead
  still ≈0.2ms).

## 0.10.0 — 2026-07-22

Takeover of the four accepted items from PR #8 (@miter37) — transient-status
retry, PDF extraction, JSON-LD rescue, Playwright render-merge — with the
review fixes applied. The rejected parts of the PR (JS_SHELL / BOT_WALL
verdicts, trafilatura extraction chain, body size cap, cookie-banner removal,
resource blocking) are NOT included; verdict-system changes land with the
upstream validator/scheduler rework instead.

- **`engine/transport.py`**: `POOL.request(max_retries=N)` retries transient
  statuses (429/502/503/504) on the SAME identity with exponential backoff
  (1.5s × 2^n). Review fixes over the PR version: a numeric `Retry-After`
  header overrides the backoff delay, total retry sleep is capped at 10s, and
  the default is `max_retries=0` so only opted-in callers retry.
- **`engine/fetch_chain.py`**: retry fires on the PROBE attempt only — grid
  candidates never retry, so a failing grid cannot multiply backoff sleeps
  into a tens-of-seconds failure path (the amplification flagged in review).
- **`engine/fetch_chain.py`**: content-rescue extraction. The raw body REMAINS
  `content` for ordinary HTML successes (no contract break); a rescue replaces
  it only where the raw body is unusable: PDF bodies (magic-byte sniff +
  content-type, `.pdf`-URL-serving-HTML re-guarded) → pypdf text; SPA shells
  whose visible text is thinner than their JSON-LD articleBody → articleBody.
  The "rescue must beat the visible text" gate is the structural fix for the
  teaser-beats-article failure mode found in the PR's meta fallback. New
  `FetchResult.extraction_quality/source/meta` fields; `--no-extract` /
  `enable_extraction=False` to disable.
- **Render-merge**: both Playwright templates emit `innerText` in the JSON
  envelope; the executor stashes it and the rescue gate keeps whichever of
  (visible body text, innerText) carries more text. Compared against VISIBLE
  text length, not raw markup length. The PR's stylesheet/resource blocking
  and cookie-banner DOM removal are excluded (stealth-fingerprint conflict).
- **`engine/__main__.py`**: new `--no-retry` / `--no-extract` flags.
- **SKILL.md**: content contract documented; `pypdf` added to the dependency
  auto-install guard.
- Tests: `test_t1_retry.py` (8) + `test_t2_rescue.py` (11) added,
  `test_u4.py` envelope tests extended; full suite 83 green.

## 0.9.2 — 2026-07-15

Cross-platform yt-dlp invocation — the YouTube / media route no longer
misreports an installed yt-dlp as missing.

- **`engine/phase0.py`**: the YouTube Phase-0 route invoked yt-dlp only as the
  bare `yt-dlp` console script. With `pip install --user` and on Windows / venv
  installs the script dir is commonly absent from PATH, so `subprocess.run`
  raised `FileNotFoundError` and the route reported `"yt-dlp not installed"`
  even though yt-dlp *was* installed and importable — silently disabling the
  headline media route (1,858 sites) for those users. New `_ytdlp_argv()`
  prefers the `yt-dlp` console script on PATH and falls back to
  `<python> -m yt_dlp`, mirroring the `which yt-dlp || python3 -m yt_dlp`
  fallback already documented in `references/media.md`. Non-regressive:
  environments with `yt-dlp` on PATH are unchanged.
- **`tests/coverage_battery.py`**: the youtube battery uses the same resolution.
- **`engine/bias_check.py`**: the `EXPLICIT_ALLOW_FILES` exemption compared
  `str(rel)`, which is backslash-separated on Windows and therefore never
  matched the POSIX-style allow-list — so the sanctioned `phase0.py` exemption
  silently failed and the No-Site-Name gate reported false positives when run
  on Windows. Now compares `rel.as_posix()`. Same theme (cross-platform); no
  behaviour change on POSIX.
- Adds network-free regression tests in `engine/tests/test_u9.py`.

## 0.9.1 — 2026-07-02

Activate the Patchright fallback and align the self-learning host key.

- **Patchright activated** (`engine/templates/package.json`): added `patchright` (^1.61.1) as a dependency. The real-Chrome template (`playwright_real_chrome.js`) already *preferred* `require('patchright')`, but the package was never declared, so it always fell back to playwright-extra+stealth. Patchright is a Playwright-API-compatible drop-in fork that patches the CDP `Runtime.enable` (console-attach) leak that Cloudflare/DataDome-class detection now keys on — verified end-to-end (`automation:patchright`, HTTP 200, real HTML). When patchright is absent the template still falls back to playwright-extra+stealth → plain playwright, all on `channel:'chrome'`.
- **Learning host-key fix** (`engine/learning.py`): `key_for` used `urlsplit().netloc` (keeps port + userinfo) while the session pool and Playwright profile dir key on `hostname` (`transport._host_of`, `executor._profile_dir_for`). A URL with a port therefore *learned* under a different key than it *fetched* under. Switched to `hostname` so the learned route, warm session, and browser profile all share one host key.
- **Docs**: `SKILL.md` + `references/playwright.md` install instructions updated to the local `engine/templates` npm install with `npx patchright install chrome`.
- Full engine regression 59/59; `bias_check` clean.

## 0.9.0 — 2026-06-28

Prompt-injection surface hardening for fetched public web content.

- **Content-safety metadata and envelope**: fetched text is now annotated as `untrusted_public_web`, reports deterministic prompt-injection risk signals, and the default CLI text output wraps content between collision-resistant `[BEGIN UNTRUSTED WEB CONTENT]` / `[END UNTRUSTED WEB CONTENT]` boundary lines. Python API callers still receive raw `FetchResult.content`, and can use `FetchResult.to_untrusted_text()` for the same safe agent-facing representation as the CLI; JSON output keeps content omitted and adds metadata only. This is a mitigation/packaging boundary, not blocking or complete prompt-injection prevention.
- **Risk-score calibration**: a lone topical keyword (e.g. `secret`/`token`/`password`) on an ordinary page no longer escalates to `medium`, and keyword-only signals without an explicit instruction-override now cap at `medium` instead of `high`. `high` is reserved for an instruction-override combined with a sensitive action. This avoids crying wolf on the technical/API docs this tool routinely fetches — verified against real pages (Wikipedia, MDN, Django/Stripe docs) — so the `high` label stays meaningful for genuine injection attempts.

## 0.8.1 — 2026-06-22

Validator false-positive fix — a small but complete page is no longer mislabelled a challenge.

- **`validators.py`**: the tiny-body heuristic (body < 3000B with no positive proof) used to return a decisive `CHALLENGE` on size alone, so a legitimately short page (e.g. example.com at ~600B) failed with `ok=False` even though it returned a clean 200 with real content. It now checks completeness first — a COMPLETE HTML document (`</html>`/`</body>`) carrying meaningful visible text → `WEAK_OK`; only an incomplete / script-only / empty small body stays `CHALLENGE`. New `_looks_complete_content_page` helper.
- Pre-existing since validator v2 (v0.6.0) — affected *every* complete page under 3000 bytes, not just example.com.
- Adds 3 regression cases to `tests/test_u1.py` (small-complete → weak_ok; script-stub and incomplete-fragment → challenge). Full engine regression 48/48; `bias_check` clean.

## 0.8.0 — 2026-06-22

Per-host self-learning (U5) — the engine now remembers which route got through and tries it first next time. Lab-built (`insane-search-lab`), effect-tested before shipping.

- **`engine/learning.py` (new)** — a bounded, self-pruning JSON store (`~/.insane_search/learned.json`, override with `INSANE_LEARNED_PATH`). For each host it records the route that last succeeded (`transform × impersonate × referer × phase`), keyed by `host::{desktop|mobile}`.
- **Promotion in the first phase** — `fetch()` is now a learning wrapper around the grid (`_fetch_core`): before fetching it looks up the host and promotes the learned route to *both* the probe identity and the front of the grid (`_build_plan` priority). On a 2nd visit the known-good route is retried first instead of being rediscovered.
- **Eviction so the store can't bloat or rot**: (1) a learned route that hits a REAL block (`exhausted`/`challenge`/`blocked`) is struck and deleted after 2 consecutive strikes — transient outcomes (429, network/unknown error, budget cut) and URL-level outcomes (404/401) never strike; (2) entries unused for 30 days are pruned on load (`INSANE_LEARN_TTL_DAYS`); (3) a 500-entry LRU cap (`INSANE_LEARN_MAX`). Disable entirely with `INSANE_LEARN=0`.
- **Safe by construction** — every learning operation is best-effort and swallows its own errors, so it can never break a fetch. It is a DATA file only, so the No-Site-Name Rule (R3) still holds (`bias_check` clean).
- **Measured** (`experiments/effect_e8.py`, offline A/B): 2nd-visit curl attempts drop (3 → 1 on a small grid; scales with grid depth), and a learning-off control matches the cold run — confirming the win comes from learning. Adds `tests/test_u5.py` (14 cases); full engine regression 45/45.

## 0.7.3 — 2026-06-22

- **5-language README** (matches the marketplace root): added `README.zh.md`, `README.ja.md`, `README.es.md` (full translations) and a 5-language switcher header across all files (en · ko · zh · ja · es). The "Impossible is nothing." slogan stays in English in zh/ja/es with a localized second line.
- EN tagline gains a grounding second line: **"Impossible is nothing. If it's public, insane-search gets in."**

## 0.7.2 — 2026-06-22

- Stronger hero tagline. EN: **"Impossible is nothing."** · KO: **"포기는 배추 셀 때나 쓰는 말. 공개된 페이지라면, insane-search는 결국 뚫어낸다."** — the descriptive sub-line still grounds what the plugin is.

## 0.7.1 — 2026-06-22

README overhaul — image-first landing that shows what the plugin does in one glance.

- **New README (en + ko)**: replaces the 234-line manual with a ~110-line sales landing. Two cinematic hero images (a 403/CAPTCHA/WAF wall shattering as `insane-search GETS IN`, and the Phase 0→3 escalation pipeline as an energy rail) under `assets/`. Sections: Install · Try it · Works on · Why it gets through · Default vs `+ insane-search` · How it works · Boundaries.
- **Content preserved, not dropped**: the full platform tables, reference-file map, dependencies, and example prompts moved to `PLATFORMS.md` (linked from the README) — nothing lost, the landing just stops carrying the manual.
- Hero demo uses real, verified data (a public `@claudeai` post via WebSearch → oEmbed, no API key); the "before" reflects the actual default-fetch failure on X (HTTP 402 / a JavaScript-only shell), not a fictional login wall.

## 0.7.0 — 2026-06-22

Harness enforcement — the engine now *makes* itself try every route instead of relying on the agent to remember to. (Motivated by a live failure: `.json`/syndication 403/429'd, the agent declared Reddit/X "blocked", and nobody tried `.rss`/oEmbed.)

- **Phase 0 official-API router** (`engine/phase0.py`, new): `fetch()` now detects recognised platforms by URL and tries the official no-auth endpoint **before** the generic grid — Reddit→`.rss` (then `.json` via curl_cffi), X tweet→`cdn.syndication tweet-result` + `publish oembed`, X profile→`syndication-timeline` (retry), YouTube→`yt-dlp`. This is the *enforced* version of the old agent-driven SKILL snippets, so the route can no longer be skipped. Trace records each as `phase=phase0`; recognised-but-failed falls through to the grid (never gives up early). New `enable_phase0` param + `--no-phase0`. `phase0.py` is the single bias-check-exempt engine file (R5 sanctioned exception).
- **Failure gate** (`fetch_chain.py`, `__main__.py`): on `ok=False`, `FetchResult` now carries `untried_routes[]` and `must_invoke_playwright_mcp`. A terminal wall (404/auth/paywall) returns them empty; **429 is treated as transient** (back off + retry, not a wall); any other give-up names what's left — re-run exhaustive if the grid was budget-cut, and (always, for gated pages) drive Playwright **MCP from the agent session**, which the engine structurally cannot do itself. The CLI prints a `⛔ NOT EXHAUSTED (R6)` block to stderr. SKILL **R6** rewritten as a 4-point blocking checklist that consumes these fields. CLI `--max-attempts` now defaults to exhaustive.
- **Coverage battery** (`tests/coverage_battery.py`, new): hits each platform through ALL candidate routes and reports PASS/FAIL per route, so "did we actually try everything?" is an evidence artifact and a rotted example (was PASS, now FAIL) is caught. Current run: 6/7 reachable (reddit `.rss`, x tweet-result+oembed, youtube, hn, arxiv, naver); flags the stale `reddit json+iPhoneUA` SKILL example.
- **bias_check hardening** (`bias_check.py`): `engine/tests/**` excluded (fixtures legitimately use concrete hosts/IPs), `phase0.py` explicitly allow-listed, `safety.py` metadata-IP comment marked `NOTE-BIAS-OK`. Default scan is clean again.
- Quick-reference + engine-file guide updated: lead with `python3 -m engine <URL>` (Phase 0 is automatic); manual snippets marked debug-only with the verified working routes.

## 0.6.0 — 2026-06-22

Engine overhaul — multi-AI reviewed (GPT-5.5 Pro + council) and effect-tested before shipping.

- **Diversity scheduler** (`fetch_chain.py`): the grid now materializes a plan and varies TLS family × URL transform first, so a small attempt budget touches every family/transform instead of burning out on one. Measured: family×transform class coverage 3/10 → 10/10 at the same cap. `max_attempts=None` is now exhaustive (honours R6); `tls_impersonate_avoid` targets are deprioritized, not deleted; jitter only on a failed attempt; new `grid_exhausted` / `stop_reason` diagnostics.
- **Validator v2** (`validators.py`): adds non-terminal `SUSPECT_OK`, JSON-aware validation (small API responses no longer mislabelled `CHALLENGE`), HARD vs SOFT markers (a `captcha` word can't override a matched selector), byte-accurate size, and 429/401/404/5xx status semantics. Measured: judgment errors 5/11 → 0/11 (incl. 2 false-successes removed).
- **Per-host SessionPool + cookie bridge** (`transport.py`, `executor.py`): cookies and connections persist across attempts/pages; a browser that clears a JS challenge hands its cookies + UA to curl_cffi (FlareSolverr pattern). Proven: an injected clearance cookie converts a 403/challenge into a 200. Adds `fetch_many()` and root warmup.
- **Playwright fallback hardening**: per-host profile isolation, `process.exit` → drained natural exit (no truncated HTML), single shared navigation deadline, JSON envelope (status / final URL / cookies / UA).
- **Patchright support (additive)**: if `patchright` is installed it is used as a drop-in (Runtime.enable-free) Playwright per its official best-practice (`channel='chrome'`, `no_viewport`, no stealth/headers); otherwise behaviour is unchanged. Measured on rebrowser-bot-detector: `runtimeEnableLeak` passes, `navigator.webdriver` hidden.
- **SSRF / redirect guard** (`safety.py`): blocks non-http(s) schemes and requests/redirects to private/loopback/link-local/metadata IPs (with DNS-rebinding check); every redirect hop is validated. `INSANE_ALLOW_PRIVATE=1` opts in for local use.
- **Requires curl_cffi ≥ 0.15.0**: `impersonate="chrome"` now resolves to Chrome 146 (was the stale Chrome 142), plus HTTP/3 fingerprints and an SSRF-safe redirect default. Setup and the runtime guard upgrade an existing older curl_cffi.
- Adds deterministic regression tests (`test_u1.py`, `test_u4.py`, `test_u7.py`).

## 0.5.2 — 2026-06-21

- The GitHub-star prompt is shown in the user's current language; on a fresh session with no language signal yet, it falls back to the language detected from your recent Claude sessions (else English).
- GitHub star is now **opt-in** — on first run the command asks once via AskUserQuestion (`네, ⭐ 눌러주기` / `아니요`) instead of auto-starring. The star logic moved into `setup.sh` and records the choice (`~/.gptaku-setup/<plugin>.star.json`) so it never re-asks. `setup.sh` no longer stars anything automatically.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] — 2026-05-04

### Changed
- SKILL.md R7 (WAF 조기 감지 시 API-first 병행 분기) — 분기 결정은 자동이지만 사용자가 결과 metadata에서 확인 가능. 어떤 접근 경로로 성공/실패했는지 명시

### Preserved (R1-R7 모두 보존)
- R1: WebFetch / 즉흥 curl 금지
- R2: 첫 200에서 탈출 금지 (4-계층 검증)
- **R3: No-Site-Name Rule** (bias_check.py CI 게이트) — fossil-방지 메타-패턴
- R4: 사이트 고유 정보는 CLI/user_hint로만
- R5: Phase 0 공식 API 우선
- R6: 격자 모두 돌린 뒤 "뚫을 수 없음" 결론
- R7: 병행 분기

→ insane-search는 4 진단 대상 중 fossil 의문이 가장 적게 검증된 케이스. R3 + bias_check.py는 다른 fossil-위험 플러그인에 차용 가능한 메타-패턴.

## [0.4.0] — 2026-04-22

### Added
- **`engine/` Python package** — single public entrypoint (`python3 -m engine URL` or `from engine import fetch`) that runs an exhaustive curl_cffi grid over WAF product profiles.
  - `fetch_chain.py` — grid scheduler with internal phases (probe → validate → detect → plan → execute → report), per-attempt jitter, and `FetchResult.trace[]` for diagnostics.
  - `validators.py` — 4-layer challenge classifier (`STRONG_OK / WEAK_OK / CHALLENGE / BLOCKED / UNKNOWN`) replacing naive HTTP 200 heuristics.
  - `waf_detector.py` — ranked `[(profile_id, confidence)]` detection with sticky `last_load_error()` for loader diagnostics.
  - `waf_profiles.yaml` — seven product profiles (`akamai_bot_manager`, `cloudflare_turnstile`, `f5_big_ip`, `aws_waf`, `datadome_probable`, `perimeterx_human`, `unknown_challenge`) with 25+ curl_cffi impersonate candidates and an empirically-derived `tls_impersonate_avoid` list.
  - `url_transforms.py` — generic URL mutations (`original`, `mobile_subdomain`, `am_prefix`, `drop_www`), no site-specific branches.
  - `executor.py` — capability-matched Playwright router, honours each profile's `fallback_when_challenge` ordering.
  - `templates/playwright_real_chrome.js` — Local Node + `channel:'chrome'` + stealth + persistent context, with home warmup and reload-retry against Akamai-grade WAFs.
  - `templates/playwright_mobile_chrome.js` — `devices[...]` emulation while keeping real-Chrome TLS.
  - `bias_check.py` — CI linter enforcing the No-Site-Name Rule via brand denylist + URL/domain regex, with `node_modules`/build-artefact exclusion.
  - `tests/test_smoke.py` — unit + online smoke coverage for validators, profile loader, URL transforms, and network round-trips.
- **SKILL.md harness rules R1–R7** — explicit constraints that keep Claude from improvising around the engine:
  - R1 CLI-first on any blocked URL
  - R2 no early break on HTTP 200
  - R3 No-Site-Name enforcement
  - R4 runtime-only hints
  - R5 Phase 0 official APIs take precedence
  - R6 exhaustive grid before declaring failure
  - **R7 — API-first parallel branch** when a WAF is detected early and the user intent is list/collect: engine keeps running in background while Claude reconnoiters via Playwright MCP `browser_network_requests` to discover internal JSON endpoints, then re-fetches via engine.
- **Full `references/` index (12/12 files)** grouped by role (engine extension, lightweight alternatives, platform APIs, in-tree code) with "when to read" + "what it covers" per entry.
- **`references/playwright.md`** rewritten as Approach 1 (MCP Chromium — Cloudflare-grade) vs Approach 2 (Local Node `channel:'chrome'` + stealth — Akamai-grade), selection driven automatically by profile `capabilities_needed` tags.

### Changed
- `plugin.json` version bumped to `0.4.0` (new public surface + new behavior justify minor bump).
- Graceful degradation paths for missing `PyYAML`, `curl_cffi`, `bs4`, or Node — failures surface as `UNKNOWN` verdicts + trace entries, never silently swallow.
- Per-attempt jitter between curl grid calls, env-tunable via `INSANE_JITTER_MS_MIN` / `INSANE_JITTER_MS_MAX`.

### Notes
- No site-specific logic is introduced anywhere in `engine/**` or `waf_profiles.yaml`; all site knowledge enters at call time (`success_selectors`, `user_hint`) or stays in comments / docs.
- Earlier history kept in git log.

## Earlier releases

Pre-0.4.0 history is documented in git commits only; no structured changelog was maintained before this release.
