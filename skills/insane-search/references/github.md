# GitHub 접근 전략

> gh CLI로 검색, 이슈, PR, 코드를 조회한다. 공개 검색은 로그인 불필요.

## 설치

```bash
# macOS
brew install gh

# Linux
sudo apt install gh
```

로그인(`gh auth login`)하면 비공개 저장소, Fork, Issue 생성 등 추가 기능 사용 가능.

## 제한 사항

- 비인증 상태에서 rate limit: 시간당 60회 요청
- 인증 시: 시간당 5,000회
- 비공개 저장소: `gh auth login` 필수
- 코드 검색: GitHub 인덱싱 지연으로 최신 커밋 반영에 시간 소요
- gh CLI 미설치 시: `brew install gh` (macOS) / `sudo apt install gh` (Linux)

## 저장소 검색

```bash
gh search repos "{query}" --sort stars --limit 10
gh search repos "{query}" --language python --sort stars --limit 10
```

## 코드 검색

```bash
gh search code "{query}" --language python --limit 10
gh search code "{query}" --repo {owner}/{repo} --limit 10
```

## 이슈 검색

```bash
gh search issues "{query}" --repo {owner}/{repo} --limit 10
gh search issues "{query}" --state open --limit 10
```

## PR 검색

```bash
gh search prs "{query}" --repo {owner}/{repo} --limit 10
```

## 저장소 정보

```bash
# README 읽기
gh api repos/{owner}/{repo}/readme --jq '.content' | base64 -d

# 저장소 메타데이터
gh repo view {owner}/{repo} --json name,description,stargazerCount,forkCount,primaryLanguage

# 최근 릴리즈
gh release list --repo {owner}/{repo} --limit 5
```

## 파일 읽기

```bash
# 특정 파일
gh api repos/{owner}/{repo}/contents/{path} --jq '.content' | base64 -d

# 디렉토리 목록
gh api repos/{owner}/{repo}/contents/{path} --jq '.[].name'
```
