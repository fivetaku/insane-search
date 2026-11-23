# Codex에서 실행할 때 (insane-search)

SKILL.md 절차는 그대로 따르고, 아래 차이만 적용한다.

- 이 스킬은 사용자에게 선택지를 묻지 않는다. 질문 도구가 필요 없고, Codex에서는 `codex exec`처럼 사람이 답할 수 없는 실행에서도 그대로 돈다.
- `${CLAUDE_PLUGIN_ROOT}`는 치환되지 않는다. 이 플러그인 루트(SKILL.md에서 두 단계 위 폴더)의 절대경로로 바꿔 `PYTHONPATH="<루트>/skills/insane-search" python3 -m engine "<URL>"`로 실행한다.
- Step 0 첫 실행 설정(`setup/setup.sh`)은 Claude Code 전용이다. Codex에서는 실행하지 않고 건너뛴다.
- Aside 샌드박스: Codex 기본 샌드박스(workspace-write)에서는 Aside CLI의 로컬 인증(키체인)이 막혀 Aside 렌더 단계가 실패한다(2026-11-23 실측, danger-full-access에서는 성공). Aside 렌더링이 필요하면 사용자에게 권한 상승(샌드박스 밖 실행 승인)을 요청한다.
- aside-browser 스킬을 부르라는 단계는 Codex에 `Skill` 도구가 없으므로 그 스킬의 SKILL.md를 열어 따른다. 쓸 수 없으면 SKILL.md의 Playwright 대체 절차를 쓴다.
