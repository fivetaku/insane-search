# 범용 웹 접근 전략

> WebFetch 실패 시 Jina Reader나 RSS로 대체한다.

## Jina Reader

URL 앞에 `r.jina.ai/`를 붙이면 마크다운으로 변환. 설정 불필요.

```bash
curl -s "https://r.jina.ai/https://example.com/article"
```

대부분의 일반 웹페이지에서 동작. CAPTCHA 보호 사이트(위챗 공중호 등)는 실패.

## RSS 피드

API 키 불필요. 블로그/뉴스 사이트의 최신 포스트 일괄 수집.

feedparser 설치: `pip install feedparser`

```bash
# 네이버 블로그 RSS — 최신 50개 포스트
curl -sL "https://rss.blog.naver.com/{BLOG_ID}.xml"

# 티스토리 RSS
curl -sL "https://{blogname}.tistory.com/rss"

# 워드프레스 RSS
curl -sL "https://{domain}/feed"

# Python feedparser로 파싱
python3 -c "
import feedparser
for e in feedparser.parse('FEED_URL').entries[:10]:
    print(f'{e.title} — {e.link}')
    print(f'  {e.get(\"summary\",\"\")[:200]}')
    print('---')
"
```

## WebSearch + WebFetch 조합

기본 패턴:

```python
# 1단계: 검색
WebSearch(query="{검색어}")

# 2단계: 발견한 URL에서 본문 추출
WebFetch(url="{URL}", prompt="Extract key findings")
```

WebFetch가 실패하면 Jina Reader로 전환:

```bash
curl -s "https://r.jina.ai/{URL}"
```
