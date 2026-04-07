# 네이버 계열 접근 전략

> 네이버 서비스별로 접근 방법이 다르다. 블로그는 모바일 URL, 뉴스/증권은 Jina Reader.

## 네이버 블로그

WebFetch 차단. 모바일 URL 변환 + iPhone UA로 접근.

```bash
# blog.naver.com/{ID}/{NO} → m.blog.naver.com 변환
curl -sL \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" \
  -H "Accept-Language: ko-KR,ko;q=0.9" \
  -H "Referer: https://m.naver.com/" \
  "https://m.blog.naver.com/PostView.naver?blogId={ID}&logNo={NO}"
```

RSS도 가능 (최신 50개, 본문 약 300자):
```bash
curl -sL "https://rss.blog.naver.com/{BLOG_ID}.xml"
```

## 네이버 뉴스

Jina Reader로 완전 접근 가능.

```bash
# 기사 목록
curl -s "https://r.jina.ai/https://news.naver.com/"

# 개별 기사
curl -s "https://r.jina.ai/https://n.news.naver.com/article/{press_id}/{article_id}"
```

## 네이버 증권

Jina Reader로 실시간 주가, 주요 뉴스 접근.

```bash
curl -s "https://r.jina.ai/https://finance.naver.com/item/main.naver?code={종목코드}"
```

## 네이버 카페

**접근 불가** — 로그인 + iframe 이중 장벽. 우회 방법 없음.

## 네이버 TV

yt-dlp로 접근 (media.md 참조).

```bash
yt-dlp --dump-json "https://tv.naver.com/v/{video_id}"
```
