# YouTube 접근 전략

> yt-dlp로 자막, 메타데이터, 검색, 댓글을 추출한다. API 키 불필요.

## 설치

```bash
pip install yt-dlp
```

## 실행 방법 확인

yt-dlp가 PATH에 등록되지 않은 환경이 있다. 먼저 확인:

```bash
which yt-dlp || python3 -m yt_dlp --version
```

- `yt-dlp` 명령어가 있으면 그대로 사용
- 없으면 `python3 -m yt_dlp`로 대체 (모든 명령어에서 `yt-dlp`를 `python3 -m yt_dlp`로 치환)

## 자막 추출

```bash
# 자막 다운로드 (영상 다운로드 없이)
yt-dlp --write-sub --write-auto-sub --sub-lang "en,ko" --skip-download -o "/tmp/%(id)s" "URL"

# 자막 파일 읽기
cat /tmp/VIDEO_ID.*.vtt
```

자동 생성 자막은 행간 중복 가능 → 후처리 필요.

## 영상 메타데이터

```bash
yt-dlp --dump-json "URL"
```

반환 데이터: `title`, `uploader`, `upload_date`, `view_count`, `like_count`, `duration`, `description`, `tags`, `categories`

## 영상 검색

```bash
# YouTube 검색 (상위 5개)
yt-dlp --dump-json "ytsearch5:{검색어}"
```

## 댓글 추출

```bash
yt-dlp --write-comments --skip-download --write-info-json \
  --extractor-args "youtube:max_comments=20" \
  -o "/tmp/%(id)s" "URL"

# 댓글은 .info.json의 comments 필드에 저장
python3 -c "
import json
data = json.load(open('/tmp/VIDEO_ID.info.json'))
for c in data.get('comments', [])[:10]:
    print(f\"{c['author']} ({c.get('like_count',0)} likes)\")
    print(f\"  {c['text'][:200]}\")
    print('---')
"
```

## Bilibili (B站)

yt-dlp는 Bilibili도 지원. 로컬 환경에서는 바로 작동, 서버에서는 프록시 필요할 수 있음.

```bash
# Bilibili 자막
yt-dlp --write-sub --skip-download -o "/tmp/%(id)s" "https://www.bilibili.com/video/BV..."

# Bilibili 메타데이터
yt-dlp --dump-json "https://www.bilibili.com/video/BV..."
```

## 주의사항

- yt-dlp가 설치되어 있어야 함 (`pip install yt-dlp`)
- 자동 생성 자막은 품질이 낮을 수 있음
- 댓글 추출은 웹 스크래핑 기반으로 일부 누락 가능
- 1800+ 사이트 지원 (YouTube, Bilibili, Vimeo, Dailymotion 등)
