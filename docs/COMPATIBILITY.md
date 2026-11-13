# 호환성 및 실제 적용 확인

기준 문서 확인일: 2026-11-14.

## 대상

- 로컬 Codex 앱·CLI용. 일반 ChatGPT 웹 대화, Claude Code, Cursor용 설정이 아닙니다.
- 개발 PC: Codex CLI 0.166.0, Python 3.12.10. Python 최소 3.9, 추가 패키지 없음.
- 전역 지침은 `.codex/AGENTS.md`, 사용자 스킬은 `.agents/skills`, 훅은 `.codex/hooks.json`.
- 정책 폴더는 소문자 `.codex`. `.Codex`와 혼용하지 않습니다.
- Windows 훅 명령은 PowerShell 호출 연산자·단일 인용, macOS/Linux는 POSIX 셸 인용을 사용합니다. 각 PC에서 다시 설치해 Python 절대 경로를 기록하세요.
- 사용자 훅은 `/hooks` 신뢰 검토가 필요합니다. 신뢰나 승인·샌드박스 설정을 자동 우회하지 않습니다.
- 기존 config.toml의 같은 이벤트 훅은 함께 실행될 수 있으므로 중복을 검토하세요.

## 입출력

PreToolUse의 Bash와 apply_patch는 `tool_input.command`를 전달합니다. apply_patch는 Edit/Write matcher에도 매칭되지만 실제 이름은 apply_patch입니다. 모든 파일 헤더와 이동 목적지를 검사하고 deny JSON을 출력합니다. ask 또는 자동 allow는 출력하지 않습니다.

SessionStart는 startup/resume/clear/compact/fork를 처리합니다. additionalContext에 넣는 기록은 참고 자료이며 새로운 지시나 권한이 아닙니다. 과거 대화나 인증 파일을 수집하지 않습니다.

## 자동 시험 범위

실제 Python 프로세스에 훅 이벤트를 전달하고 임시 홈에서 설치·갱신·제거와 파일 내용을 비교합니다. Windows에서는 설치된 훅 명령을 PowerShell로 직접 실행합니다. 이 시험은 Codex 앱이 이벤트를 발행하고 신뢰한 훅을 호출하는 것까지 증명하지 않습니다.

GitHub Actions는 Windows/macOS/Linux, Python 3.9/3.12 조합을 시험합니다. 결과는 저장소 Actions에서 확인하세요. 심볼릭 링크 권한이 없으면 해당 시험을 건너뛰며 Windows 전용 시험은 다른 OS에서 제외됩니다.

## 설치 후 실제 세션 확인

버려도 되는 프로젝트에서 진행하세요.

1. `/hooks`에서 두 훅의 경로·내용을 검토하고 신뢰한 뒤 새 세션을 엽니다.
2. input/sample.txt, 보호 목록의 input/, 짧은 PROGRESS.md를 준비합니다.
3. 진행 기록이 복원되는지 로그와 실제 응답을 확인합니다.
4. input/sample.txt 패치는 거부되고 work/sample.txt 패치는 가능한지 확인합니다.
5. 빈 `.codex/READONLY`를 만든 뒤 일반 파일 패치가 거부되는지 확인합니다.
6. 거부 메시지뿐 아니라 파일 해시·내용도 비교합니다.

열린 셸의 write_stdin, MCP 쓰기, 간접 스크립트는 완전 검사 대상이 아닙니다. 중요한 원본은 백업·OS 권한·Codex 샌드박스로도 보호하세요. 훅 오류가 나면 정상 작동으로 간주하지 마세요.

## 공식 근거

- https://learn.chatgpt.com/docs/agent-configuration/agents-md
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/hooks
- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
