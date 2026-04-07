---
name: insane-search
description: >
  WebFetch가 차단되거나 실패할 때, 또는 X/Twitter, Reddit, YouTube, GitHub에
  접근할 때 사용하는 플랫폼별 우회 접근 전략.
  트위터/X 못 열어, 레딧 안 읽혀, 유튜브 자막 뽑아줘, 깃헙 검색, 사이트 차단됨,
  twitter access, reddit blocked, youtube subtitles, github search.
  Make sure to use this skill whenever WebFetch returns 402/403/blocked,
  when accessing X/Twitter/Reddit/YouTube/GitHub content,
  or when curl-based platform access is needed.
  Do NOT trigger for simple web searches that WebSearch can handle directly.
---

# Insane Search

> WebSearch/WebFetch만으로 접근 불가한 플랫폼에 대한 우회 접근 전략을 제공한다.

## 사용 순서

1. **WebSearch**로 검색하여 URL 확보
2. **WebFetch**로 본문 추출 시도
3. WebFetch 실패 시 → 아래 플랫폼별 전략 또는 Fallback으로 자동 전환

## 플랫폼별 접근 전략

| 플랫폼 | WebFetch | 우회 방법 | 상세 |
|--------|----------|----------|------|
| X/Twitter | 402 차단 | Syndication API, oEmbed API | [references/twitter.md](references/twitter.md) |
| Reddit | 차단 | JSON API (`.json` + Mobile UA) | [references/reddit.md](references/reddit.md) |
| YouTube | - | yt-dlp 자막/메타데이터 | [references/youtube.md](references/youtube.md) |
| GitHub | - | gh CLI | [references/github.md](references/github.md) |
| 범용 웹 | 일부 차단 | Jina Reader, RSS | [references/web.md](references/web.md) |
| 차단 사이트 | 실패 | 단계별 우회 | [references/fallback.md](references/fallback.md) |

## 빠른 참조 — 즉시 사용 가능한 명령어

```bash
# X/Twitter 타임라인
curl -sL "https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"

# X/Twitter 개별 트윗
curl -sL "https://publish.twitter.com/oembed?url=https://x.com/{user}/status/{id}"

# Reddit 서브레딧
curl -sL -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15" \
  "https://www.reddit.com/r/{subreddit}/hot.json?limit=10"

# YouTube 자막 (yt-dlp가 PATH에 있을 때)
yt-dlp --write-sub --write-auto-sub --sub-lang "en,ko" --skip-download -o "/tmp/%(id)s" "URL"
# PATH에 없으면: python3 -m yt_dlp 으로 대체

# 범용 웹 (Jina Reader)
curl -s "https://r.jina.ai/{URL}"

# GitHub 검색
gh search repos "{query}" --sort stars --limit 10
```

모든 방법은 **API 키 불필요, 인증 불필요**로 동작한다. 상세 사용법과 데이터 파싱은 각 references 파일을 참조.

## 응답 검증

curl로 받은 응답의 성공/실패 판정 기준은 [references/fallback.md](references/fallback.md)의 "응답 검증 규칙" 참조.
