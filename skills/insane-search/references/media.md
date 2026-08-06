# 미디어 추출 — yt-dlp

> yt-dlp는 YouTube 전용 도구가 아니라 **1,858개 사이트**를 지원하는 범용 미디어 추출 도구.
> 영상, 오디오, 팟캐스트, 라이브 스트리밍 — 미디어 URL이면 yt-dlp를 먼저 시도한다.

## 설치 확인

```bash
which yt-dlp || python3 -m yt_dlp --version
```

- `yt-dlp` 명령어가 PATH에 있으면 그대로 사용
- 없으면 `python3 -m yt_dlp`로 대체 (아래 모든 명령어에서 치환)
- 미설치 시: `pip install yt-dlp`

## 핵심 명령어 (모든 지원 사이트 공통)

### 메타데이터 추출 (가장 범용)

```bash
yt-dlp --dump-json "URL"
```

title, uploader, duration, view_count, description, tags 등 구조화 JSON 반환.
전용 extractor가 있는 사이트에서 ~95% 성공.

### 자막 추출

```bash
yt-dlp --write-sub --write-auto-sub --sub-lang "en,ko" --skip-download -o "/tmp/%(id)s" "URL"
cat /tmp/VIDEO_ID.*.vtt
```

YouTube는 100개 언어 자동자막 지원. 다른 사이트는 자체 자막 제공 시에만 동작.

### 검색

```bash
# YouTube
yt-dlp --dump-json "ytsearch5:{검색어}"

# SoundCloud
yt-dlp --dump-json "scsearch5:{검색어}"

# Dailymotion
yt-dlp --dump-json "dailymotionsearch5:{검색어}"

# Yahoo
yt-dlp --dump-json "yahoosearch5:{검색어}"
```

### 채널/플레이리스트 목록 (다운로드 없이)

```bash
yt-dlp --flat-playlist --dump-json "채널_URL"
```

title, id, url, duration 반환. 채널 전체 영상 목록을 초고속 수집.

### 댓글 추출 (YouTube)

```bash
yt-dlp --write-comments --skip-download --write-info-json \
  --extractor-args "youtube:max_comments=20" \
  -o "/tmp/%(id)s" "URL"
```

## 지원 플랫폼 카테고리

### 영상

| 사이트 | 메타데이터 | 자막 | 검색 | 비고 |
|--------|----------|------|------|------|
| YouTube | O | O (자동생성 포함) | `ytsearch` | 최고 지원 |
| Vimeo | O | O (사이트 제공 시) | X | 학술/다큐 콘텐츠 풍부 |
| Twitch | O (VOD/클립) | X | X | 기술 스트리밍 |
| TikTok | O | X | X | 공개 계정만 |
| Dailymotion | O | O | `dailymotionsearch` | |
| Rumble | O | X | X | |
| PeerTube | O | X | X | 탈중앙화 |

### 오디오/팟캐스트

| 사이트 | 메타데이터 | 검색 | 비고 |
|--------|----------|------|------|
| SoundCloud | O | `scsearch` | 검색까지 가능 — 최고 |
| Apple Podcasts | O | X | RSS 기반 |
| TuneIn | O | X | |
| acast | O | X | 채널 단위 지원 |
| Spreaker | O | X | |
| Audius | O | X | 블록체인 기반 |

### 한국 플랫폼

| 사이트 | Extractor | 비고 |
|--------|-----------|------|
| Naver TV | `Naver`, `Naver:live` | |
| Kakao | `Kakao` | |
| SBS | `SBS`, `sbs.co.kr` | |
| JTBC | `JTBC`, `JTBC:program` | |
| Chzzk | `chzzk:video`, `chzzk:live` | 네이버 스트리밍 |
| Soop (구 AfreecaTV) | `soop`, `soop:live` | |
| Daum | `daum.net`, `daum.net:clip` | |
| Weverse | `Weverse`, `WeverseLive` | K-팝 팬덤 |

### 뉴스 VOD

| 사이트 | 비고 |
|--------|------|
| BBC | 공개 VOD |
| ABC (호주) | iview |
| CBS News | |
| NBC News | 차단 많음 |

> 뉴스 사이트는 직접 URL보다 **YouTube 공식 채널 경유**가 더 안정적.
> 예: `ytsearch:BBC News {키워드}`

## yt-dlp 미지원 플랫폼 — Threads

yt-dlp에는 Threads 익스트랙터가 없다 (2026.03 기준 `--list-extractors` 0건, generic 폴백도 `Unsupported URL`).
영상 포스트는 engine Phase 0 라우트(`engine/phase0.py::_threads`)가 처리한다:

```bash
python3 -m engine "https://www.threads.com/@{handle}/post/{shortcode}"
# → content = {"post_code": "...", "video_urls": ["https://scontent-….cdninstagram.com/…"]}
curl -sL -o /tmp/threads.mp4 "{video_urls[0]}"        # 서명 CDN URL은 plain curl로 충분
ffprobe -v error -show_entries stream=codec_type,codec_name /tmp/threads.mp4
# 실측(2026-07-26): h264 720×1280 + AAC progressive 먹싱본 — DASH 합성 불필요
```

동작 원리 (수동 재현 시): 익명 GET(curl_cffi safari 지문, WAF 챌린지 없이 1회 통과) → HTML 인라인 JSON에
`video_versions` 블록이 여러 개(관련/추천 포스트 포함, 실측 7개) → URL shortcode(`"code":"…"`)에
**문자 거리 최근접 블록**이 본 포스트 → URL의 `\/`·유니코드 이스케이프 해제 → 첫 항목(type 101) 사용.

미검증 경계 (실패 시 참고):

- **서명 URL 만료**: `oe` 파라미터가 만료 시각으로 추정 — 추출 즉시 다운로드할 것. URL만 저장해두고 나중에 받는 흐름 금지.
- **DASH-only 포스트**: 실측 샘플은 progressive였으나 일부 포스트는 `video_dashinit`/`audio_dashinit` 분리 가능성 — 다운로드 후 ffprobe로 오디오 스트림 존재 확인.
- **캐러셀(다중 영상) 포스트**: 최근접 1블록 규칙이 부족할 수 있음 (미테스트).
- **이미지/텍스트 포스트**: 라우트가 ok=False로 반환해 일반 체인이 본문을 처리한다.
- **로그인 월**: 현재 익명 GET 통과. Meta가 막으면 engine이 격자→Playwright로 에스컬레이션.

## 주의사항

- 자동 생성 자막은 행간 중복 → 후처리 필요
- generic extractor는 성공률 ~30% — 전용 extractor 있는 사이트 우선
- 페이월/로그인 사이트는 대부분 실패
- `--dump-json`이 가장 안전한 범용 명령 (다운로드 없음, 메타데이터만)
