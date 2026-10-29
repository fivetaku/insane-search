# X/Twitter 접근 전략

> WebFetch는 402로 차단됨. 무료 공개 경로를 기준선으로 사용하고, xAI 자격정보가 있으면 X Search를 선택적으로 병합한다.

## 검색 (트윗 발견)

```bash
cd "${CLAUDE_PLUGIN_ROOT}/skills/insane-search"
python3 -m engine.x_search "{검색어}" --limit 10
```

`engine.x_search`는 단일 공급자에 의존하지 않는다.

1. **무료 Brave·Yahoo·Keenable discovery** — 항상 병렬 실행, API 키 불필요. Brave·Yahoo는 공개 검색 HTML을, Keenable은 키 없는 JSON 검색 API(`site: x.com`)를 쓴다. 한 검색엔진이 차단되거나 색인 결과가 없어도 다른 경로로 계속한다.
2. **xAI `x_search`** — `XAI_API_KEY` 또는 로컬 OMO xAI OAuth가 있을 때만 병렬 실행
3. **교차 병합** — 한 공급자가 결과 상한을 독점하지 않도록 URL을 교차 선택
4. **tweet-result 재검증** — 원문·작성자·시각·반응 수를 다시 가져와 최종 근거로 사용

xAI가 없거나 실패해도 무료 검색으로 계속된다. 유료 경로를 명시적으로 끄려면 `--free-only` 또는 `INSANE_SEARCH_XAI=off`를 사용한다. 결과의 `discovery_sources`, `degraded_reason`, `discovery_errors`, `rejected_urls`, 각 post의 `discovered_by`가 provenance를 제공한다.

> ⚠️ **제3자 전송 고지**: Keenable 경로는 검색어(위 두 쿼리 템플릿)를 `api.keenable.ai/v1/search/public`으로 보낸다. 앱 식별 헤더 `X-Keenable-Title: insane-search`만 붙고 API 키·쿠키는 보내지 않는다. 키 없는 한도는 IP당 초당 10회·시간당 1,000회(검색 1회 = 요청 2회). 끄려면 `INSANE_SEARCH_KEENABLE=off`.

> Grok Build를 호출하는 구조가 아니다. X 검색에는 빠른 `grok-4.20-0309-non-reasoning`과 xAI 서버사이드 `x_search`를 사용하며, 핵심 기능은 모델보다 검색 도구다.

## 타임라인 조회 — Syndication API

특정 핸들의 최근 ~100개 트윗 + engagement 수치(likes, RTs) 제공.

### 엔드포인트

```
https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}
```

### 원샷 스크립트

```bash
curl -sL "https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}" | \
python3 -c "
import sys, json, re, html
content = sys.stdin.read()
match = re.search(r'__NEXT_DATA__.*?>(.*?)</script>', content)
if match:
    data = json.loads(match.group(1))
    for e in data['props']['pageProps']['timeline']['entries']:
        if e['type'] == 'tweet':
            t = e['content']['tweet']
            print(f\"@{t['user']['screen_name']} ({t.get('created_at','?')})\")
            print(f\"  {html.unescape(t.get('full_text',''))[:300]}\")
            print(f\"  Likes: {t.get('favorite_count',0)} | RTs: {t.get('retweet_count',0)}\")
            print('---')
"
```

### 가져올 수 있는 데이터

| 필드 | 경로 | 예시 |
|------|------|------|
| 트윗 전문 | `tweet.full_text` | "Give your agent the..." |
| 작성자 핸들 | `tweet.user.screen_name` | "openclaw" |
| 작성자 이름 | `tweet.user.name` | "OpenClaw" |
| 좋아요 수 | `tweet.favorite_count` | 1929 |
| RT 수 | `tweet.retweet_count` | 169 |
| 작성 시각 | `tweet.created_at` | "Mon Apr 06 04:04:08 +0000 2026" |
| 트윗 ID | `tweet.id_str` | "2041003999856406714" |
| 미디어 URL | `tweet.entities.media[].media_url_https` | 이미지/동영상 URL |

### 제한

- 최근 ~100개 반환 (페이지네이션 불가)
- 비공개 계정 접근 불가
- 검색 기능 없음 (타임라인만)
- **저팔로워/신규 계정**: `hasResults: false` 반환 가능. 이 경우 oEmbed 개별 트윗 접근은 정상 동작하므로 "조합 패턴"으로 폴백.
- 비공식 엔드포인트 — X가 변경/차단 가능

## 개별 트윗 조회 — oEmbed API

특정 트윗 URL을 알 때 전문 가져오기.

### 엔드포인트

```
https://publish.twitter.com/oembed?url=https://x.com/{user}/status/{tweet_id}
```

### 사용법

```bash
curl -sL "https://publish.twitter.com/oembed?url=https://x.com/{user}/status/{tweet_id}"
```

### 응답 (JSON)

| 필드 | 설명 |
|------|------|
| `author_name` | 작성자 표시 이름 |
| `author_url` | 작성자 프로필 URL |
| `html` | 트윗 전문이 포함된 HTML blockquote |
| `url` | 트윗 원본 URL |

## 개별 트윗 조회 — tweet-result (가장 안정적, 권장)

oEmbed는 HTML을 주지만, `cdn.syndication.twimg.com/tweet-result`는 **구조화 JSON**(본문 + 좋아요/리트윗 수 + 작성자)을 바로 준다. 실측에서 oEmbed/syndication보다 차단이 적었다 (engine Phase 0의 X 단일-트윗 1순위 경로).

### 엔드포인트 / 사용법

```
https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=a
```
```bash
# plain curl은 TLS로 막힐 수 있어 curl_cffi 지문 권장 (engine이 자동 처리)
python3 -c "from curl_cffi import requests as r; import json; \
d=r.get('https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=a', impersonate='safari').json(); \
print(d['user']['name'], '@'+d['user']['screen_name']); print(d['text']); print('♥', d.get('favorite_count'))"
```

### 응답 (JSON)

| 필드 | 설명 |
|------|------|
| `text` | 트윗 전문 (plain text) |
| `user.name` / `user.screen_name` | 작성자 이름 / 핸들 |
| `favorite_count` / `conversation_count` | 좋아요 / 댓글 수 |
| `created_at` | 작성 시각 |

> `token` 파라미터는 임의 값(`a`)이어도 동작한다. `id`는 `/status/{id}` 경로에서 추출.

## 장문 트윗·X 아티클 — FxTwitter 조건부 폴백 (v0.17.0, 엔진 자동)

tweet-result와 oEmbed는 **장문 트윗을 약 280자에서 자르고, X 아티클은 t.co 링크만** 준다(잘렸다는 표시 없음). 엔진(`engine/phase0.py`)은 tweet-result JSON에 아래 신호가 하나라도 있으면 `api.fxtwitter.com`을 추가로 불러 전문을 받는다.

| 신호 | 의미 |
|---|---|
| `note_tweet` 키 | 장문 트윗 |
| `article` 키 | X 아티클 (본문은 FxTwitter `tweet.article.content.blocks[].text`) |
| 본문 270자 이상 | 장문 가능성 |
| 본문이 t.co 링크 하나뿐 | 아티클·미디어 가능성 |

- 성공하면 `route: fxtwitter`, `content`는 전문 텍스트(아티클은 제목 + 블록 본문).
- 실패하거나 tweet-result보다 길지 않으면 tweet-result 결과를 그대로 돌려주고 `truncated_possible: true`, `truncation_reason: fxtwitter_failed`를 붙인다(`FetchResult.extraction_meta`와 summary에 노출).
- 짧은 트윗은 FxTwitter를 부르지 않는다. 2026-10-08 실측 18건: 장문·아티클 6/6 전문, 짧은 트윗 12/12 미호출, 호출 54회 실패 0.

> ⚠️ **제3자 전송 고지**: 신호가 있으면 조회한 트윗 ID·작성자 핸들이 제3자 서비스(fxtwitter.com, 개인 운영·SLA 없음)로 전송된다. 끄려면 `INSANE_SEARCH_FXTWITTER=0` — 이때 신호가 있는 트윗은 `truncation_reason: fxtwitter_disabled`로 표시된다.

## 조합 패턴 (검색 → 상세)

```
1단계: `python3 -m engine.x_search "{키워드}" --limit 10` → 다중 discovery + 검증된 트윗
2단계: provenance 필드 확인 → 사용 경로, 공급자별 오류, 저하 사유를 결과에 짧게 명시
```

## 실패하는 방법 (사용하지 말 것)

| 방법 | 결과 | 원인 |
|------|------|------|
| WebFetch | 402 Payment Required | Claude Code의 WebFetch 제한 |
| Nitter | 빈 응답 | Nitter 인스턴스 대부분 종료됨 |
| Wayback Machine | OG 메타태그만 | SPA 렌더링 안 됨 |
| Mobile UA curl | OG 메타태그만 | SPA 렌더링 안 됨 |
| RSS | 엔드포인트 없음 | X는 RSS 지원 중단 |
