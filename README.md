# Insane Search

> AI 에이전트가 접근 못하는 플랫폼을 뚫어주는 스킬

WebFetch가 차단되는 X/Twitter, Reddit, Threads 등의 플랫폼에 **API 키 없이, 인증 없이** 접근하는 방법을 제공합니다.

## 왜 필요한가?

AI 에이전트(Claude Code, Cursor 등)는 WebSearch와 WebFetch로 웹에 접근합니다. 하지만 **많은 플랫폼이 차단됩니다:**

| 플랫폼 | WebFetch 결과 | 이유 |
|--------|-------------|------|
| X/Twitter | 402 Payment Required | 인증 필요 |
| Reddit | unable to fetch | 봇 감지 |
| Stack Overflow | 도메인 차단 | Claude Code 제한 |
| 네이버 블로그 | 차단 | iframe + UA 차단 |
| Threads | 빈 SPA | JS 렌더링 필요 |
| 클리앙 | 403 | UA 차단 |

**Insane Search는 이 문제를 해결합니다.** 각 플랫폼의 공개 API와 우회 접근법을 활용하여, 에이전트가 자동으로 데이터를 가져옵니다.

## 지원 플랫폼 (30+ 테스트 완료)

### 소셜 미디어

| 플랫폼 | 방법 | 설정 | 가져올 수 있는 데이터 |
|--------|------|------|---------------------|
| **X/Twitter** | Syndication API, oEmbed | 제로 | 타임라인 ~100개, 트윗 전문, likes/RTs, 미디어 |
| **Reddit** | JSON API (`.json` + Mobile UA) | 제로 | 포스트 전문, 댓글 트리, 검색, 점수 |
| **Threads** | Jina Reader | 제로 | 프로필, 포스트 내용, 이미지 |
| **Bluesky** | 공개 API (`public.api.bsky.app`) | 제로 | 프로필, 피드, 인증 불필요 |
| **Mastodon** | 공개 API (`/api/v1/`) | 제로 | 계정 프로필, 게시물 |

### 개발/기술

| 플랫폼 | 방법 | 설정 | 가져올 수 있는 데이터 |
|--------|------|------|---------------------|
| **GitHub** | gh CLI | brew/apt 1회 | 저장소/코드/이슈/PR 검색 |
| **Stack Overflow** | curl + SE API v2.3 | 제로 | Q&A 전문 (WebFetch 차단이지만 curl OK) |
| **Hacker News** | Firebase REST API | 제로 | 스토리, 댓글, 전체 조회 |
| **dev.to** | 공개 API | 제로 | 기사 목록, 전문, JSON |
| **npm Registry** | 공개 API | 제로 | 패키지 메타데이터, 버전, 의존성 |
| **PyPI** | 공개 API | 제로 | 패키지 정보, 버전, 다운로드 수 |

### 동영상/미디어

| 플랫폼 | 방법 | 설정 | 가져올 수 있는 데이터 |
|--------|------|------|---------------------|
| **YouTube** | yt-dlp | pip 1회 | 자막, 메타데이터, 검색, 댓글 |
| **Medium** | Jina Reader | 제로 | 기사 전문 (paywall 제외) |
| **Substack** | Jina Reader + RSS | 제로 | 뉴스레터 전문 |

### 한국 플랫폼

| 플랫폼 | 방법 | 설정 | 가져올 수 있는 데이터 |
|--------|------|------|---------------------|
| **네이버 블로그** | 모바일 URL + iPhone UA | 제로 | 블로그 본문 전체 |
| **네이버 뉴스** | Jina Reader | 제로 | 기사 목록 + 본문 완전 접근 |
| **네이버 증권** | Jina Reader | 제로 | 실시간 주가, 주요 뉴스 |
| **긱뉴스 (GeekNews)** | Jina Reader | 제로 | 토픽 목록 + 개별 본문 |
| **벨로그** | RSS (`v2.velog.io/rss/@{user}`) | 제로 | 사용자별 포스트 구독 |
| **브런치** | Jina Reader + RSS | 제로 | 기사 전문 |
| **클리앙** | Jina Reader | 제로 | 게시글 목록 + 본문 |
| **루리웹** | Jina Reader + curl | 제로 | 게시글 목록 + 본문 |
| **뽐뿌** | Jina Reader + RSS | 제로 | 게시글 + RSS 본문 포함 |
| **44bits** | Jina Reader | 제로 | 기사 목록 |
| **한국경제 (한경)** | Jina Reader + RSS | 제로 | 뉴스 기사 전문 |
| **다음 뉴스** | Jina Reader | 제로 | 뉴스 기사 |

### 범용

| 플랫폼 | 방법 | 설정 | 가져올 수 있는 데이터 |
|--------|------|------|---------------------|
| **범용 웹** | Jina Reader | 제로 | 모든 URL → 마크다운 변환 |
| **RSS** | feedparser | pip 1회 | 블로그/뉴스 최신 포스트 일괄 수집 |
| **차단 사이트** | 단계별 Fallback | 제로 | OGP 메타, Google 캐시, Wayback 등 |

### 접근 불가 (테스트 완료, 우회 불가)

| 플랫폼 | 차단 방식 | 이유 |
|--------|----------|------|
| Quora | Cloudflare Bot Fight Mode | curl/Jina/WebFetch 전부 403 |
| Facebook | JS SPA + 로그인 | 실질 콘텐츠 없음 |
| 쿠팡 | F5 BIG-IP WAF | 403 Access Denied |
| 네이버/다음 카페 | 로그인 + iframe | 이중 장벽 |
| 요즘IT | CloudFront 403 | Jina 차단 |

**모든 "제로 설정" 방법은 API 키 불필요, 인증 불필요로 동작합니다.**

## 설치

### Claude Code

```bash
/plugin install fivetaku/insane-search
```

### 수동 설치

```bash
git clone https://github.com/fivetaku/insane-search.git
```

### 선택적 의존성

```bash
pip install yt-dlp        # YouTube 자막 추출
brew install gh           # GitHub 검색 (Linux: sudo apt install gh)
pip install feedparser     # RSS 파싱
```

설치하지 않아도 해당 플랫폼 접근만 비활성화되고, 나머지는 정상 동작합니다.

## 사용법

별도 명령어 없이, 검색 중 WebFetch가 실패하면 자동으로 플랫폼별 우회 전략이 적용됩니다.

```
"openclaw 트위터에서 최근 뭐라고 했어?"
→ Syndication API로 타임라인 (likes, RTs 포함)

"ClaudeAI 레딧에서 반응이 어때?"
→ Reddit JSON API로 포스트 + 댓글

"@gptaku_ai 스레드 확인해봐"
→ Jina Reader로 Threads 프로필 + 포스트

"이 유튜브 영상 내용 요약해줘"
→ yt-dlp로 자막 추출 후 요약

"이 네이버 블로그 글 읽어줘"
→ 모바일 URL 변환 + curl로 본문

"Hacker News에서 AI 관련 핫한 거 뭐야?"
→ Firebase API로 실시간 조회

"네이버 뉴스에서 클로드 관련 기사 찾아줘"
→ WebSearch + Jina Reader로 기사 전문
```

## 동작 원리

```
1. WebSearch로 검색 → URL 확보
2. WebFetch로 본문 추출 시도
3. 실패 시 → 플랫폼 감지 → 자동 우회
   ├── x.com         → Syndication API / oEmbed
   ├── reddit.com    → JSON API (.json + Mobile UA)
   ├── threads.com   → Jina Reader
   ├── youtube.com   → yt-dlp
   ├── github.com    → gh CLI
   ├── bsky.app      → Bluesky 공개 API
   ├── mastodon.*    → Mastodon 공개 API
   ├── news.ycombinator.com → Firebase API
   ├── stackoverflow.com → curl + SE API
   ├── blog.naver.com → 모바일 URL + iPhone UA
   ├── news.naver.com → Jina Reader
   ├── *.tistory.com → WebFetch / RSS
   └── 기타 → Fallback (Jina → OGP → 캐시 → Wayback)
4. 응답 검증 (로그인 페이지/CAPTCHA/빈 SPA 자동 감지)
```

## 구조

```
insane-search/
├── .claude-plugin/plugin.json
├── skills/insane-search/
│   ├── SKILL.md                  ← 라우터 + 빠른 참조
│   └── references/
│       ├── twitter.md            ← X/Twitter (Syndication, oEmbed)
│       ├── reddit.md             ← Reddit (JSON API)
│       ├── youtube.md            ← YouTube (yt-dlp)
│       ├── github.md             ← GitHub (gh CLI)
│       ├── web.md                ← Jina Reader, RSS, Threads
│       └── fallback.md           ← 네이버 블로그 + 단계별 우회 + 응답 검증
└── docs/references/              ← 개발 참고 자료 (git 미포함)
```

## Insane 시리즈

Awesome 시리즈가 큐레이션 목록이라면, **Insane 시리즈는 AI 에이전트가 실제로 쓸 수 있는 도구 전략**입니다.

- **insane-search** — 플랫폼 접근 우회 전략

## License

MIT
