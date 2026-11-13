# YunStone GPT Harness

한국어로 일하는 **Codex 앱·CLI용 개인 작업 하네스**입니다. 중단 후 재개, 원본 보존, 번호별 피드백, 문서 시각 검수, AI 간 인계를 돕습니다.

[YunStone Claude Harness](https://github.com/agunessuk/YunStone_claude_Harness)를 Codex 지침·스킬·훅 규격에 맞춰 다시 만들었습니다. 일반 ChatGPT 대화에 파일을 업로드하는 설치 방식은 아닙니다.

## 설치

Python **3.9 이상**과 로컬 Codex가 필요합니다. Python을 자동 설치하거나 권한 설정을 완화하지 않습니다.

```powershell
# Windows: 저장소 폴더에서
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 --dry-run
powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
```

```sh
# macOS / Linux
sh install.sh --dry-run
sh install.sh
```

미리보기 목록을 확인한 뒤 설치하세요. **새 Codex 세션을 열고 CLI의 `/hooks`에서 훅 정의를 검토·신뢰해야 합니다.** 설치만으로 보호가 작동한다고 가정하지 마세요. 앱의 관리 UI는 버전에 따라 다릅니다.

## 바뀌는 파일

| 위치 | 내용 |
|---|---|
| `~/.codex/AGENTS.md` | 표지 주석 사이 작업 원칙 |
| `~/.agents/skills/` | 공통 스킬 8개 |
| `~/.codex/hooks/yunstone-gpt/` | 보호·상태 복원 훅과 공통 모듈 |
| `~/.codex/hooks.json` | PreToolUse·SessionStart 연결 |
| `~/.codex/yunstone-gpt-harness/` | 설치 파일 해시·원래 내용·백업 |

`CODEX_HOME`을 지정했다면 `.codex` 대신 그 경로를 사용합니다. 스킬은 사용자 홈의 `.agents/skills`를 사용합니다. `config.toml`과 Claude 설정은 바꾸지 않습니다. `AGENTS.override.md`가 있으면 전역 지침을 가릴 수 있으므로 확인하세요.

## 기존 설정 보존

- 기존 동명 스킬은 기본적으로 건너뜁니다.
- 설치 후 사용자가 수정한 스킬·전역 지침은 보존합니다. 수정된 훅 파일·훅 연결은 갱신을 중단합니다.
- 변경 전 파일을 고유한 백업 폴더에 저장합니다. 적용 중 오류가 나면 이번 변경을 되돌립니다. 전원 장애까지 보장하는 트랜잭션은 아닙니다.
- 제거는 설치 목록의 파일과 정확히 일치하는 훅 정의만 대상으로 합니다. 다른 파일과 훅은 유지합니다.
- 오래된 `.local-harness` 표지가 있는 스킬을 인수할 때만 아래 옵션을 사용합니다. 기존 내용은 백업하며 제거 시 복원합니다.

```sh
python install.py --adopt-legacy --dry-run
python install.py --adopt-legacy
```

인수 옵션은 **스킬만** 대상으로 합니다. 기존 `local-harness` 전역 지침 블록은 새 블록과 중복될 수 있으므로 별도로 비교·정리하세요. 무조건 덮어쓰는 옵션은 없습니다.

## 스킬 8개

| 이름 | 용도 |
|---|---|
| resume-work | 중단·압축·인계 뒤 상태 대조와 재개 |
| feedback-round | 번호 피드백과 확정 영역 보존 |
| handoff-pack | 압축본·파일 목록·새 AI 첫 지시 |
| gpt-collab | 이미지 생성 도구와 협업, 외부 명세·검수 반영 |
| print-doc-qa | 렌더링으로 여백·정렬·누락 확인 |
| status-report | 확인한 결과와 미확인 구분 |
| project-index | 프로젝트 지도와 안정된 파일 ID |
| env-and-cleanup | 한글 경로·셸 차이·서버·임시 파일 관리 |

구현은 현재 Codex가 수행하며 이미지 생성 도구가 있으면 직접 활용합니다. 외부 AI 의견은 실제 파일과 대조한 뒤 채택합니다.

## 프로젝트 보호와 재개

`templates/project/`의 필요한 파일을 기존 파일을 덮어쓰지 않고 프로젝트 루트로 복사하세요.

- `.codex/protected.txt`: 프로젝트 기준 원본 경로. 예: `input/`, `인계용/*.zip`.
- `.codex/READONLY.example`: `READONLY`로 이름을 바꾸면 적힌 경로의 파일 패치만 허용. 빈 파일이면 전부 차단.
- `PROGRESS.md`: 현재 단계·다음 행동·확정 사항·미확인.
- `docs/QUALITY_BAR.md`: 반복 지적과 검증 방법.

보호 훅은 apply_patch의 추가·수정·삭제·이동 경로와 알려진 위험 명령 패턴을 검사합니다. 읽기 전용 모드에서는 알려진 쓰기 가능 셸 명령을 차단합니다. 상태 복원은 하위 폴더에서도 프로젝트를 찾아 진행 기록 앞 6,000자를 전달합니다.

**차단은 확인 창이 아닙니다.** Codex에서 현재 지원하지 않는 `permissionDecision: ask`를 쓰지 않습니다. 원본은 복사본에서 작업하세요. 필요한 위험 명령·정책 변경은 이유와 대상을 확인한 사용자가 별도 터미널에서 수행합니다. 하네스는 자동 우회 권한을 만들지 않습니다.

## 한계

훅은 보조 장치이며 완전한 보안 경계가 아닙니다. 셸 변수·별칭·간접 스크립트·동적 경로를 모두 해석하지 못합니다. MCP·호스팅 도구·일부 도구 경로·열린 셸의 후속 입력은 검사 밖입니다. 검사 코드 내부 오류는 거부하지만 훅 실행 실패·시간 초과·미신뢰 상태에서는 런타임이 호출을 계속할 수 있습니다.

엄격한 분석 작업은 Codex 자체 읽기 전용 샌드박스도 사용하세요. [호환성 및 실제 적용 확인](docs/COMPATIBILITY.md)에 검증 범위와 절차가 있습니다.

## 시험·제거

```sh
python -m unittest discover -s tests -v
python tests/test_hooks.py
python install.py --uninstall --dry-run
python install.py --uninstall
```

제거 후 사용자 수정 파일·추가 파일·백업·빈 디렉터리·설치 기록은 남을 수 있습니다. 새 세션을 여세요. 시험용 홈은 `python install.py --home ./temporary-home --dry-run`처럼 지정합니다.

백업의 `index.json`은 원래 경로와 번호별 `.bin` 파일을 연결합니다. 수동 복구 전 현재 파일과 비교하세요. 백업에는 개인 설정 내용이 있으므로 공개하지 마세요.

## Codex에 붙여 넣는 설치 프롬프트

```text
YunStone GPT Harness를 내 Codex에 설치해줘.
저장소: https://github.com/agunessuk/YunStone_GPT_Harness

1. 홈 아래 YunStone_GPT_Harness로 clone해. 이미 있으면 remote와 로컬 변경을 확인하고, 변경이 없을 때만 git pull --ff-only로 갱신해.
2. README.md와 global/AGENTS.md를 읽고 변경 대상과 훅의 한계를 짧게 설명해.
3. Python 3.9 이상인지 확인해. 없으면 자동 설치하지 말고 알려줘.
4. python install.py --dry-run으로 생성·갱신·건너뜀 목록을 보여줘.
5. 내가 확인하면 설치해. 기존 동명 스킬은 보존해. .local-harness 스킬 인수는 차이와 백업 방식을 보여준 뒤 별도 확인해.
6. python -m unittest discover -s tests -v를 실행하고 결과를 알려줘.
7. 새 세션과 /hooks 신뢰 검토가 필요함을 알려줘. 자동 시험 통과와 실제 Codex 적용 확인을 구분해.
8. 제거 명령 python install.py --uninstall도 알려줘.
```

## 라이선스

MIT. 원본과 참고 스킬의 저작권 고지를 유지합니다. [NOTES.md](NOTES.md)에 출처와 변경 내용이 있습니다. 개인 대화·수집·분석 기록은 배포하지 않습니다.
