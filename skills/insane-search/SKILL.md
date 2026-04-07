---
name: insane-search
description: >
  WebFetch가 차단되거나 실패할 때, 또는 X/Twitter, Reddit, YouTube, GitHub 등
  플랫폼에 접근할 때 사용하는 우회 접근 전략. 1,858개 미디어 사이트(yt-dlp),
  범용 웹(Jina Reader), 공개 API(HN, Bluesky, arXiv 등)를 활용한다.
  트위터/X 못 열어, 레딧 안 읽혀, 유튜브 자막 뽑아줘, 깃헙 검색, 사이트 차단됨,
  twitter access, reddit blocked, youtube subtitles, github search, arxiv papers.
  Make sure to use this skill whenever WebFetch returns 402/403/blocked,
  when accessing social media or developer platforms,
  or when extracting media content (video, audio, subtitles).
  Do NOT trigger for simple web searches that WebSearch can handle directly.
---

# Insane Search

> URL 접근이 차단될 때, 플랫폼별 최적 방법을 자동으로 안내한다.

## 사이트별 접근 인덱스

아래 테이블에서 접근하려는 사이트를 찾고, 해당 방법의 reference를 참조한다.

### 소셜 미디어

| 사이트 | 도메인 | 방법 | 상세 |
|--------|--------|------|------|
| X/Twitter | x.com, twitter.com | Syndication API, oEmbed | [twitter.md](references/twitter.md) |
| Reddit | reddit.com | JSON API (.json + Mobile UA) | [json-api.md](references/json-api.md) |
| Threads | threads.com | Jina Reader | [jina.md](references/jina.md) |
| Bluesky | bsky.app | AT Protocol 공개 API | [public-api.md](references/public-api.md) |
| Mastodon | mastodon.social 등 | 공개 API (인스턴스별) | [public-api.md](references/public-api.md) |

### 미디어/영상

| 사이트 | 도메인 | 방법 | 상세 |
|--------|--------|------|------|
| YouTube | youtube.com, youtu.be | yt-dlp (자막/메타/검색/댓글) | [media.md](references/media.md) |
| Vimeo | vimeo.com | yt-dlp | [media.md](references/media.md) |
| Twitch | twitch.tv | yt-dlp (VOD/클립) | [media.md](references/media.md) |
| TikTok | tiktok.com | yt-dlp | [media.md](references/media.md) |
| SoundCloud | soundcloud.com | yt-dlp (검색 가능: scsearch) | [media.md](references/media.md) |
| 1,858개 미디어 사이트 | 다양 | yt-dlp --dump-json | [media.md](references/media.md) |

### 개발/기술

| 사이트 | 도메인 | 방법 | 상세 |
|--------|--------|------|------|
| GitHub | github.com | gh CLI / REST API | [json-api.md](references/json-api.md) |
| Stack Overflow | stackoverflow.com | SE API v2.3 (WebFetch 도메인 차단) | [public-api.md](references/public-api.md) |
| Hacker News | news.ycombinator.com | Firebase JSON API | [json-api.md](references/json-api.md) |
| Lobste.rs | lobste.rs | JSON API | [json-api.md](references/json-api.md) |
| dev.to | dev.to | 공개 API | [json-api.md](references/json-api.md) |
| npm | npmjs.com | Registry API | [json-api.md](references/json-api.md) |
| PyPI | pypi.org | JSON API | [json-api.md](references/json-api.md) |

### 학술/지식

| 사이트 | 도메인 | 방법 | 상세 |
|--------|--------|------|------|
| arXiv | arxiv.org | Atom API | [public-api.md](references/public-api.md) |
| CrossRef | doi.org | REST API | [public-api.md](references/public-api.md) |
| Wikipedia | wikipedia.org | REST API | [json-api.md](references/json-api.md) |
| OpenLibrary | openlibrary.org | JSON API | [public-api.md](references/public-api.md) |
| Wayback Machine | web.archive.org | CDX API | [public-api.md](references/public-api.md) |

### 한국 플랫폼

| 사이트 | 도메인 | 방법 | 상세 |
|--------|--------|------|------|
| 네이버 블로그 | blog.naver.com | 모바일 URL + iPhone UA | [naver.md](references/naver.md) |
| 네이버 뉴스 | news.naver.com | Jina Reader | [naver.md](references/naver.md) |
| 네이버 증권 | finance.naver.com | Jina Reader | [naver.md](references/naver.md) |
| 네이버 TV | tv.naver.com | yt-dlp | [naver.md](references/naver.md) |
| 클리앙 | clien.net | Jina Reader | [jina.md](references/jina.md) |
| 루리웹 | ruliweb.com | Jina Reader | [jina.md](references/jina.md) |
| 뽐뿌 | ppomppu.co.kr | Jina Reader + RSS | [jina.md](references/jina.md) |
| 긱뉴스 | news.hada.io | Jina Reader | [jina.md](references/jina.md) |
| 벨로그 | velog.io | RSS (`v2.velog.io/rss/@{user}`) | [json-api.md](references/json-api.md) |
| 브런치 | brunch.co.kr | Jina Reader + RSS | [jina.md](references/jina.md) |
| 한국경제 | hankyung.com | Jina Reader + RSS | [jina.md](references/jina.md) |
| SBS/JTBC/Kakao | 방송사 | yt-dlp | [media.md](references/media.md) |
| Chzzk/Soop | 스트리밍 | yt-dlp | [media.md](references/media.md) |

### 뉴스/미디어

| 사이트 | 도메인 | 방법 | 상세 |
|--------|--------|------|------|
| Medium | medium.com | Jina Reader | [jina.md](references/jina.md) |
| Substack | *.substack.com | Jina Reader + RSS | [jina.md](references/jina.md) |
| 다음 뉴스 | news.daum.net | Jina Reader | [jina.md](references/jina.md) |

### 접근 불가

| 사이트 | 이유 |
|--------|------|
| Quora | Cloudflare Bot Fight Mode |
| Facebook | JS SPA + 로그인 |
| 쿠팡 | F5 BIG-IP WAF |
| 네이버/다음 카페 | 로그인 + iframe |
| 요즘IT | CloudFront 403 |
| LinkedIn (프로필) | 로그인 벽 (WebSearch→WebFetch 조합은 가능) |

## 접근 순서

1. **인덱스 확인** — 위 테이블에서 사이트 찾기
2. **해당 방법 실행** — reference 파일의 명령어 사용
3. **인덱스에 없는 사이트** → `WebFetch` 시도 → 실패 시 `Jina Reader` → 실패 시 `Fallback`

## 빠른 참조 — 범용 명령어

```bash
# 범용 웹 (Jina Reader)
curl -s "https://r.jina.ai/{URL}"

# 미디어 메타데이터 (yt-dlp — 1,858 사이트)
yt-dlp --dump-json "URL"

# Reddit
curl -sL -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15" "https://www.reddit.com/r/{sub}/hot.json?limit=10"

# X/Twitter 타임라인
curl -sL "https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"

# Hacker News
curl -sL "https://hacker-news.firebaseio.com/v0/topstories.json?limitToFirst=10&orderBy=%22%24key%22"

# YouTube 자막
yt-dlp --write-sub --write-auto-sub --sub-lang "en,ko" --skip-download -o "/tmp/%(id)s" "URL"
```

## 응답 검증

curl로 받은 응답의 성공/실패 판정 기준은 [fallback.md](references/fallback.md)의 "응답 검증 규칙" 참조.
