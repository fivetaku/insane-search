# 접근 불가 시 우회 전략 (Fallback)

> WebSearch/WebFetch/플랫폼별 전략 모두 실패했을 때 아래 순서로 시도.

## 1. 모바일 URL 변환 + curl

도메인별 최적 방법:

| 도메인 패턴 | 최적 방법 |
|-----------|---------|
| `blog.naver.com` | 모바일 URL + iPhone UA |
| `*.tistory.com` | WebFetch (정상) 또는 RSS |
| `brunch.co.kr` | WebFetch (정상) |
| `linkedin.com` | WebSearch → WebFetch (정상) |
| `*.naver.com` (기타) | Playwright MCP (JS 렌더링 필요) |
| 페이월 사이트 | Google 캐시 → Wayback |

```bash
# 네이버 블로그
curl -sL \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: ko-KR,ko;q=0.9" \
  -H "Referer: https://m.naver.com/" \
  "https://m.blog.naver.com/PostView.naver?blogId={ID}&logNo={NO}"

# 일반 사이트
curl -sL \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15" \
  "{URL}"
```

## 2. OGP 메타태그 추출

최소한 제목+요약 확보.

```bash
curl -sL \
  -H "User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" \
  "{URL}" \
  | grep -E '<meta property="og:|<meta name="description'
```

## 3. Google 캐시 / Wayback Machine

```bash
curl -sL "https://webcache.googleusercontent.com/search?q=cache:{URL}"
curl -sL "https://web.archive.org/web/{URL}"
```

iframe 기반 사이트(네이버)는 캐시도 실패할 수 있음.

## 4. curl_cffi (TLS 핑거프린트 우회)

Cloudflare 등 TLS 핑거프린트 차단 우회.

```python
# pip install curl_cffi 필요
from curl_cffi import requests
response = requests.get("{URL}", impersonate="chrome124")
print(response.text)
```

## 5. Playwright MCP (최후 수단)

JS 렌더링이 필수인 SPA 사이트에만 사용.

```bash
# 설치: claude mcp add playwright npx @playwright/mcp@latest
```

## 응답 검증 규칙

curl로 받은 응답이 실제 콘텐츠인지 판별:

| 판정 | 조건 | 조치 |
|------|------|------|
| **성공** | 본문 1,000자 이상 + 주제 관련 키워드 | 소스로 사용 |
| **부분 성공** | OG 메타/제목+요약만 | 보조 소스, `partial_content` 태그 |
| **실패 — 로그인** | `login`, `sign in`, `로그인` 집중 | 다음 방법 시도 |
| **실패 — CAPTCHA** | `captcha`, `verify`, `robot` 또는 200자 미만 | 다음 방법 시도 |
| **실패 — 에러** | 4xx/5xx 또는 `not found`, `access denied` | 다음 방법 시도 |
| **실패 — 빈 SPA** | `<div id="root"></div>` 외 콘텐츠 없음 | Playwright 또는 포기 |

## Fallback 실행 규칙

1. **우회 성공 시**: `via_fallback` 태그 + 방법 기록
2. **모든 실패 시**: 실패 URL + 시도 결과 기록
3. **대체 소스 재검색**: 동일 주제의 다른 소스를 WebSearch로 재검색
