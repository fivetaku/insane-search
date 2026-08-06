[English](README.md) | 한국어 | [中文](README.zh.md) | [日本語](README.ja.md) | [Español](README.es.md)

<div align="center">

# insane-search

**포기는 배추 셀 때나 쓰는 말. 공개된 페이지라면, insane-search는 결국 뚫어낸다.**

차단에 강한 공개 페이지 리더 — Claude Code용. API 키도, 프록시 설정도 없다.

<p>
  <a href="https://docs.anthropic.com/en/docs/claude-code"><img src="https://img.shields.io/badge/platform-Claude_Code-D97757?logo=claude" alt="Claude Code"></a>
  <img src="https://img.shields.io/badge/API_key-not_required-3FB950" alt="No API key">
  <a href="https://github.com/fivetaku/gptaku_plugins"><img src="https://img.shields.io/badge/part_of-gptaku--plugins-6E56CF" alt="part of gptaku-plugins"></a>
  <a href="https://github.com/fivetaku/insane-search/stargazers"><img src="https://img.shields.io/github/stars/fivetaku/insane-search?style=flat&color=F0B72F" alt="stars"></a>
</p>

<!-- Hero — cinematic key-art: a blocked site (403 / CAPTCHA / WAF) shatters as
     insane-search breaks through and returns real public content with its source. -->
<img src="assets/hero.png" width="860" alt="시네마틱 분할: 왼쪽은 403 Forbidden·CAPTCHA·WAF로 막힌 사이트, 가운데가 부서지며 오른쪽에서 insane-search가 뚫고 들어가 @claudeai(Claude Code Plugins)의 실제 공개 포스트를 출처와 함께 가져온다 — API 키 없이.">

</div>

---

## ⚡ 설치

```bash
/plugin marketplace add https://github.com/fivetaku/gptaku_plugins.git
/plugin install insane-search@gptaku-plugins
/reload-plugins
```

외울 명령어는 없다. 평소처럼 Claude Code에게 말하면, fetch가 막히는 순간 insane-search가 알아서 끼어든다.

## 💬 이렇게 써보세요

그냥 평소처럼 부탁하면 됩니다 — 막히는 순간 insane-search가 작동합니다:

> *"레딧에서 Claude Code 관련 반응 찾아서 인기 글들 요약해줘."*
> *"X에서 insane-search 관련 포스트 검색해줘."*
> *"이 유튜브 영상 요약해줘."*

**예상 동작:** Claude가 각 사이트의 공개 경로 — 레딧 피드, X oEmbed, 유튜브 자막 — 로 로그인·API 키 없이 도달해 쓸 수 있는 텍스트를 돌려준다. 플러그인이 없으면 같은 요청에 *"접근할 수 없습니다"* 가 돌아오던 그 자리에서.

## 🌐 어디서 되나

**X · 레딧 · 유튜브 · Hacker News · 네이버 · 쿠팡 · 링크드인 · Medium · Substack · arXiv · GitHub · Stack Overflow · Bluesky · Mastodon** — 그리고 공개 페이지·피드·`/rss`가 있는 모든 사이트. 전체 플랫폼 목록과 방법 → [PLATFORMS.md](PLATFORMS.md).

## ⚙️ 어떻게 뚫리나

- **단정하지 않고 단계를 올린다** — 공개 API 리더 → 신디케이션 게이트웨이 → TLS 임퍼소네이션 → 진짜 헤드리스 브라우저까지, 하나가 뚫릴 때까지 차례로 시도한다.
- **사람처럼 보인다** — User-Agent만 바꾸는 게 아니라 완전한 브라우저 정체성(실제 TLS 지문, 쿠키 워밍, 리퍼러 체인)을 구성한다.
- **숨은 API를 찾는다** — 진짜 브라우저의 네트워크 트래픽을 보고 사이트가 내부적으로 쓰는 JSON을 그대로 재활용한다.
- **셋업 제로** — 필요한 도구(`curl_cffi`, `yt-dlp` 등)를 첫 실행 때 자동 설치한다. API 키도, 가입도 없다.

## 🆚 기본 Claude Code vs `+ insane-search`

| 이런 상황에서… | Claude Code 단독 | `+ insane-search` |
| :--- | :--- | :--- |
| `403` / WAF로 막힌 페이지 | ✖ 포기 | ✓ 하나 뚫릴 때까지 단계 상승 |
| 플랫폼 콘텐츠 (X, 레딧, HN) | ✖ 자주 막히거나 빈 응답 | ✓ 공개 API 리더 + 신디케이션 |
| 안티봇 / CAPTCHA 챌린지 | ✖ 중단 | ✓ TLS 임퍼소네이션, 안 되면 진짜 헤드리스 브라우저 |
| 미디어 페이지 (유튜브 등 1,800+) | ✖ 자막 없음 | ✓ `yt-dlp` 메타데이터 + 자막 |
| 도구 미설치 (`curl_cffi`, `yt-dlp`) | — | ✓ 첫 실행 때 자동 설치 |
| API 키 / 가입 | — | ✓ 불필요 |
| **로그인월 / 페이월** | ✖ | ✖ **여기서 멈추고, 그렇다고 말한다** (Boundaries 참고) |

차이를 만드는 건 기본 fetch가 못 하는 단 하나다: **뚫릴 때까지 공개 경로를 계속 시도한다.**

## ✨ 무슨 일이 일어난 건가

| 없을 때 | insane-search와 함께 |
| :--- | :--- |
| 평범한 fetch가 `403`을 맞고 Claude가 못 읽는다고 한다 | 플러그인이 공개 접근 경로를 골라 쓸 수 있는 텍스트를 돌려준다 |
| 미러·아카이브·모바일 URL을 직접 시도해야 한다 | 폴백이 자동으로 단계 상승 — 전부 공개 경로만 |
| 막힌 페이지는 막다른 길 | 메타데이터·구조화 데이터로 제목·가격·요약은 그래도 건진다 |

## 🔁 동작 방식

<img src="assets/pipeline.png" width="860" alt="Phase 0→3 에스컬레이션 파이프라인: 차단된 URL이 공식 공개 엔드포인트 → 경량 프로브 → TLS 임퍼소네이션 → 진짜 헤드리스 브라우저를 거쳐 하나가 뚫릴 때까지 진행해 깔끔한 공개 콘텐츠를 반환하고, 로그인·페이월이면 'authentication required'로 정지한다. 모든 응답은 OGP / JSON-LD로 스캔된다.">

<details>
<summary><strong>Phase 0→3 적응형 스케줄러 — 상세</strong></summary>

각 단계는 직전 단계가 실패하거나 차단 신호를 감지했을 때만 실행된다:

- **Phase 0** — 제너릭 체인이 스스로 못 찾는 공식 공개 엔드포인트(플랫폼 API, 피드)
- **Phase 1** — 경량 프로브: 공개 API 리더, 신디케이션 게이트웨이, 모바일 / `.json` / `/rss` URL 변형
- **Phase 2** — TLS 임퍼소네이션(curl_cffi: safari → chrome → firefox) + 완전한 브라우저 정체성
- **Phase 3** — 진짜 헤드리스 브라우저, 사이트가 내부적으로 쓰는 공개 JSON API까지 노출시킨다
- **Exit** — 로그인·페이월 감지 시: 가장하지 않고 *"authentication required"* 라고 보고한다

모든 응답은 OGP / JSON-LD로도 스캔되어, 부분 페이지에서도 제목·요약·가격은 건진다.
</details>

## 🔒 경계 (Boundaries)

insane-search는 **공개 콘텐츠를 위한 리더**지, 인증을 건너뛰는 도구가 아니다.

- 공개 페이지·공개 API·피드·아카이브·브라우저의 공개 응답으로 닿을 수 있는 것에 도달한다.
- **로그인과 페이월에서 멈춘다** — 뚫으려 하지 않고 `authentication required`라고 보고한다.
- 사용자를 대신해 로그인하지 않으며, 자격 증명을 저장·전송하지 않는다.
- 모든 경로는 무인증 공개 엔드포인트와 표준적이고 문서화된 기법만 쓴다.

## 라이선스

MIT

---

<div align="center">

**[gptaku-plugins](https://github.com/fivetaku/gptaku_plugins)의 일부** — 다른 모든 게 멈추는 벽을 뚫는 Claude Code 플러그인들.

</div>
