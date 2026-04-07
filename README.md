# Insane Search

> AI 에이전트가 접근 못하는 플랫폼을 뚫어주는 스킬

WebFetch가 차단되는 X/Twitter, Reddit 등의 플랫폼에 API 키 없이 접근하는 방법을 제공합니다.

## 지원 플랫폼

| 플랫폼 | 방법 | 설정 | 데이터 |
|--------|------|------|--------|
| **X/Twitter** | Syndication API, oEmbed API | 제로 | 타임라인 ~100개, 트윗 전문, likes/RTs |
| **Reddit** | JSON API (`.json` + Mobile UA) | 제로 | 포스트, 댓글, 검색 |
| **YouTube** | yt-dlp | pip 1회 | 자막, 메타데이터, 검색, 댓글 |
| **GitHub** | gh CLI | brew/apt 1회 | 저장소/코드/이슈/PR 검색 |
| **범용 웹** | Jina Reader | 제로 | 모든 URL → 마크다운 |
| **RSS** | feedparser | pip 1회 | 블로그/뉴스 최신 포스트 |
| **차단 사이트** | 단계별 Fallback | 제로 | 네이버 블로그, 페이월 등 |

모든 방법은 **API 키 불필요, 인증 불필요**로 동작합니다.

## 설치

### Claude Code

```bash
# 플러그인으로 설치
/plugin install fivetaku/insane-search
```

### 수동 설치

```bash
git clone https://github.com/fivetaku/insane-search.git
# skills/insane-search/ 폴더를 프로젝트에 복사
```

### 선택적 의존성

```bash
# YouTube 자막 추출
pip install yt-dlp

# GitHub 검색
brew install gh  # macOS
sudo apt install gh  # Linux

# RSS 파싱
pip install feedparser
```

설치하지 않아도 해당 플랫폼 접근만 비활성화되고, 나머지는 정상 동작합니다.

## 사용법

별도 명령어 없이, 검색 중 WebFetch가 실패하면 자동으로 플랫폼별 우회 전략이 적용됩니다.

```
사용자: "openclaw 트위터에서 최근 뭐라고 했어?"
→ Claude가 자동으로 Syndication API 사용

사용자: "ClaudeAI 레딧에서 반응이 어때?"
→ Claude가 자동으로 Reddit JSON API 사용

사용자: "이 유튜브 영상 내용 요약해줘"
→ Claude가 자동으로 yt-dlp로 자막 추출
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
│       ├── web.md                ← Jina Reader, RSS
│       └── fallback.md           ← 단계별 우회 + 응답 검증
└── docs/references/              ← 개발 참고 자료
```

## Insane 시리즈

Awesome 시리즈가 큐레이션 목록이라면, **Insane 시리즈는 AI 에이전트가 실제로 쓸 수 있는 도구 전략**입니다.

- **insane-search** — 플랫폼 접근 우회 전략

## License

MIT
