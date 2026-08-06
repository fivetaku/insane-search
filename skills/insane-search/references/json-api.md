# JSON API 직접 호출

> URL 변형이나 공개 엔드포인트로 구조화된 JSON을 직접 가져오는 패턴.
> 인증 불필요. Jina Reader보다 빠르고 정확한 구조화 데이터 획득.

## Reddit

> ⚠️ **비인증 `.json`은 WAF로 차단됨** (2026-06 실측). `www`·`old` 서브도메인 모두 403(189KB 챌린지 HTML 반환), curl_cffi TLS impersonation 격자(safari/chrome/firefox/safari_ios × referer) 전수 시도도 전부 403. 비인증 JSON 경로는 더 이상 신뢰할 수 없다.
>
> ✅ **대체 경로: 공식 Atom/RSS 피드(`.rss`)** — WAF 예외라 깨끗한 XML로 통과한다.

### 작동하는 경로 — Atom/RSS (비인증)

```bash
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"

# 서브레딧 피드 (실측: hot.rss·new.rss는 200 안정적)
curl -sL -H "User-Agent: $UA" "https://www.reddit.com/r/{subreddit}/hot.rss?limit=25"

# 정렬:   hot.rss · new.rss · rising.rss · top.rss?t=week
# 검색:   search.rss?q={query}&restrict_sr=1
# 유저:   https://www.reddit.com/user/{name}.rss
# 글 댓글: https://www.reddit.com/r/{subreddit}/comments/{post_id}.rss
```

획득 필드 (Atom `entry`): `title`, `author/name`(`/u/...`), `updated`(작성일), `link@href`(글 URL), `content`(본문 HTML 전문), `category`(서브레딧)

❌ RSS에 **없는** 것: `score`(추천수)·`num_comments`(댓글수)·`flair` — 이건 차단된 `.json`에만 존재. 필요하면 아래 OAuth.

파싱 (표준 라이브러리만, feedparser 불필요):
```python
import xml.etree.ElementTree as ET  # Reddit 공식 피드(신뢰 출처)라 OK. 신뢰 못 할 XML이면 defusedxml 권장(XXE 방지)
ns = {"a": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(xml_text)
for e in root.findall("a:entry", ns):
    title  = e.findtext("a:title", default="", namespaces=ns)
    author = e.findtext("a:author/a:name", default="", namespaces=ns)
    url    = e.find("a:link", ns).get("href")
    body   = e.findtext("a:content", default="", namespaces=ns)  # HTML 전문
```

> **rate-limit 주의 (실측)**: `hot.rss`·`new.rss`는 200 안정적. 반면 `top.rss`·`search.rss`는 429를 자주 반환(IP 기준 — 연속 재시도로도 안 풀릴 때 있음). 요청 간격을 벌리거나, 그래도 막히면 아래 OAuth로 전환.

### score·댓글수·flair가 필요하면 — OAuth API (유일한 정식 경로)

비인증 JSON이 막혀, 점수·댓글수는 application-only OAuth(무료, 사용자 로그인 불필요)로만 안정적으로 얻는다:

```bash
# 1) https://www.reddit.com/prefs/apps 에서 'script' 타입 앱 등록 → client_id / secret
# 2) application-only 토큰 발급
TOKEN=$(curl -s -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=client_credentials" -A "insane-search/1.0" \
  https://www.reddit.com/api/v1/access_token \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 3) oauth.reddit.com (www가 아니라 oauth 서브도메인 — 여기는 WAF 차단 없음)
curl -s -H "Authorization: bearer $TOKEN" -A "insane-search/1.0" \
  "https://oauth.reddit.com/r/{subreddit}/hot?limit=25"
```

데이터: `title`, `author`, `score`, `selftext`(전문), `num_comments`, `created_utc`, `link_flair_text`
댓글: `https://oauth.reddit.com/r/{subreddit}/comments/{post_id}` → 응답 `[1]` 배열에 재귀 트리
한도: OAuth 클라이언트 기준 100 req/min (차단된 비인증 `.json`보다 안정적)

## Hacker News (Firebase API)

Rate limit 사실상 없음.

```bash
# 탑 스토리 ID 목록
curl -sL "https://hacker-news.firebaseio.com/v0/topstories.json?limitToFirst=10&orderBy=%22%24key%22"

# 개별 아이템
curl -sL "https://hacker-news.firebaseio.com/v0/item/{id}.json"

# 변형: beststories / newstories / askstories / showstories
```

데이터: `title`, `url`, `score`, `by`(작성자), `descendants`(댓글수), `kids`(댓글 ID)

배치 조회:
```bash
python3 -c "
import urllib.request, json
ids = json.load(urllib.request.urlopen('https://hacker-news.firebaseio.com/v0/topstories.json?limitToFirst=5&orderBy=\"\$key\"'))
for id in ids:
    item = json.load(urllib.request.urlopen(f'https://hacker-news.firebaseio.com/v0/item/{id}.json'))
    print(f'[{item.get(\"score\",0)}] {item.get(\"title\")}')
    print(f'  {item.get(\"url\",\"N/A\")[:60]}')
"
```

## Lobste.rs

Rate limit 없음. HN보다 작지만 고품질 큐레이션.

```bash
# 핫 스토리
curl -sL "https://lobste.rs/hottest.json"

# 태그별 (ai, programming, web, security 등)
curl -sL "https://lobste.rs/t/ai.json"

# 최신
curl -sL "https://lobste.rs/newest.json"

# 개별 스토리 + 댓글
curl -sL "https://lobste.rs/s/{short_id}.json"
```

데이터: `title`, `url`, `score`, `comment_count`, `tags`, `submitter_user`

## dev.to

```bash
# 태그별 최신
curl -sL "https://dev.to/api/articles?tag=ai&per_page=5"

# 이번 주 탑
curl -sL "https://dev.to/api/articles?top=7&per_page=5"

# 특정 유저
curl -sL "https://dev.to/api/articles?username={user}&per_page=5"
```

데이터: `title`, `user.name`, `public_reactions_count`, `reading_time_minutes`, `tags`

## npm Registry

```bash
# 패키지 최신 버전
curl -sL "https://registry.npmjs.org/{package}/latest"

# 패키지 검색
curl -sL "https://registry.npmjs.org/-/v1/search?text={query}&size=5"

# 다운로드 통계
curl -sL "https://api.npmjs.org/downloads/range/last-month/{package}"
```

## PyPI

```bash
# 패키지 정보
curl -sL "https://pypi.org/pypi/{package}/json"

# 다운로드 통계
curl -sL "https://pypistats.org/api/packages/{package}/recent"
```

## Wikipedia

```bash
# 페이지 요약
curl -sL "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
# 한국어: https://ko.wikipedia.org/api/rest_v1/page/summary/{title}

# 검색
curl -sL "https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=5&format=json"
```

## V2EX

```bash
curl -sL "https://www.v2ex.com/api/topics/hot.json" -H "User-Agent: insane-search/1.0"
```

## RSS 피드

→ [rss.md](rss.md)로 이동. 한국 언론 RSS, Google News RSS, feedparser 사용법 등 상세 가이드 참조.
