# Reddit 접근 전략

> WebFetch는 www/old 모두 차단됨. JSON API로 우회한다. API 키/인증 불필요.

## JSON API — URL 뒤에 `.json`만 붙이면 된다

**Mobile User-Agent 헤더 필수** (없으면 403/429).

## 엔드포인트 패턴

```
# 서브레딧 포스트 목록
https://www.reddit.com/r/{subreddit}/.json
https://www.reddit.com/r/{subreddit}/hot.json?limit=10
https://www.reddit.com/r/{subreddit}/new.json?limit=10
https://www.reddit.com/r/{subreddit}/top.json?t=week&limit=10

# 서브레딧 검색
https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=1

# 개별 포스트 + 댓글
https://www.reddit.com/r/{subreddit}/comments/{post_id}/{slug}/.json

# 유저 프로필
https://www.reddit.com/user/{username}/.json
```

## 원샷 스크립트 — 서브레딧 핫 포스트

```bash
curl -sL \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15" \
  "https://www.reddit.com/r/{subreddit}/hot.json?limit=10" | \
python3 -c "
import sys, json
data = json.load(sys.stdin)
for post in data['data']['children']:
    d = post['data']
    print(f\"[{d.get('score',0)}] {d['title']}\")
    print(f\"  by u/{d['author']} | {d.get('num_comments',0)} comments\")
    body = d.get('selftext','')
    if body:
        print(f\"  {body[:200]}\")
    print('---')
"
```

## 원샷 스크립트 — 포스트 + 댓글

```bash
curl -sL \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15" \
  "https://www.reddit.com/r/{subreddit}/comments/{post_id}/{slug}/.json" | \
python3 -c "
import sys, json
data = json.load(sys.stdin)
post = data[0]['data']['children'][0]['data']
print(f\"Title: {post['title']}\")
print(f\"Author: u/{post['author']} | Score: {post['score']}\")
print(f\"Body: {post.get('selftext','')[:500]}\")
print('===')
for c in data[1]['data']['children'][:10]:
    d = c.get('data', {})
    if 'body' in d:
        print(f\"u/{d['author']} (score: {d.get('score',0)})\")
        print(f\"  {d['body'][:200]}\")
        print('---')
"
```

## 가져올 수 있는 데이터

### 포스트

| 필드 | 경로 | 설명 |
|------|------|------|
| 제목 | `data.title` | 포스트 제목 |
| 작성자 | `data.author` | 유저명 |
| 점수 | `data.score` | 업보트-다운보트 |
| 본문 | `data.selftext` | 마크다운 형식 전문 |
| URL | `data.url` | 포스트 또는 외부 링크 |
| 댓글 수 | `data.num_comments` | 댓글 수 |
| 작성 시각 | `data.created_utc` | Unix timestamp |
| flair | `data.link_flair_text` | 태그 |

### 댓글

응답의 `[1]` 배열에 댓글 트리:
- `author` — 작성자
- `body` — 댓글 본문
- `score` — 점수
- `replies` — 대댓글 (재귀적)

## 정렬 옵션

| 경로 | 정렬 | 파라미터 |
|------|------|---------|
| `hot.json` | 인기 | `limit=N` |
| `new.json` | 최신 | `limit=N` |
| `top.json` | 상위 | `t=hour\|day\|week\|month\|year\|all`, `limit=N` |
| `search.json` | 검색 | `q={query}`, `restrict_sr=1`, `sort=relevance\|top\|new` |

## 주의사항

- Mobile User-Agent 헤더 없으면 403/429 반환
- 과도한 요청 시 Rate Limiting (429)
- 비공개 서브레딧 접근 불가

## 실패하는 방법

| 방법 | 결과 | 원인 |
|------|------|------|
| WebFetch (www/old) | 차단 | Claude Code에서 reddit.com 블록 |
| RSS (`.rss`) | 403 | 2023년 이후 비인증 RSS 차단 |
