# 출처와 변경 기록

## 원본

- [agunessuk/YunStone_claude_Harness](https://github.com/agunessuk/YunStone_claude_Harness), MIT, 기준 커밋 `4a32281490957ddc08efa4060514e27d23bf8c12`.
- 원본 일부 스킬은 FOD-team-org/FOD-skills(MIT, Copyright (c) 2026 FOD-team-org)의 구조·규칙을 바탕으로 작성되었습니다. LICENSE 고지를 유지합니다.
- 원본에서 참고한 개념: kyu1204/oh-my-harness의 규칙·실행 훅 구분, FOD-team-org/codex-task-playbook의 이전 대화를 모르는 AI용 첫 지시.

## v1.0.0 — 2026-11-14

- AGENTS.md, .agents/skills, .codex/hooks.json으로 전환.
- apply_patch 추가·수정·삭제·이동 검사. ask 제거, JSON deny 사용.
- 상위 프로젝트 탐색, 제한된 진행 기록 전달, 검사 내부 오류의 명시적 거부.
- 해시·원래 내용·백업 기반 설치기. dry-run, 격리 홈, 동명 스킬 보존, 명시적 레거시 인수, 제거 시 기존 스킬 복원.
- 스킬 8개 재작성. 이미지 도구 활용, 부분 작업 복구, 번호 피드백, 문서 검수, 실제 근거 보고.
- Python 표준 라이브러리만 사용. 세 운영체제 CI 제공.
- 개인 수집·분석 기록과 사용자 설정은 공개하지 않음.

## 공식 문서

확인일 2026-11-14. 실제 Codex 버전과 함께 대조해야 합니다.

- [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Hooks](https://learn.chatgpt.com/docs/hooks)
- [Rethinking skills and prompts](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
