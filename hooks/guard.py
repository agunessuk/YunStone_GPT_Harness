"""Codex PreToolUse guard. Never emits unsupported ask/automatic allow."""
import os
import re
from pathlib import Path
from common import emit, matches, patterns, project_root, read_event

DANGEROUS = re.compile(
    r"\brm\s+(?:-[a-z]*r[a-z]*|--recursive)\b|\b(?:rd|rmdir)\s+/s\b"
    r"|\bRemove-Item\b[^;|\n]*-Recurse|\bgit\s+reset\s+--hard\b"
    r"|\bgit\s+clean\s+-[a-z]*f|\bgit\s+push\b[^;|\n]*(?:--force(?:-with-lease)?\b|\s-f\b)"
    r"|\bgit\s+(?:checkout|restore)\s+(?:--\s+)?\.\s*(?:$|[;&|])"
    r"|\bformat(?:\.com)?\s+[a-z]:", re.I)
MUTATING = re.compile(
    r"\b(?:rm|mv|cp|del|erase|rd|rmdir|move|copy|ren|rename|tee|touch|mkdir|truncate)\b"
    r"|\b(?:Remove|Move|Copy|Rename|Set|Add|Clear)-Item\b|\b(?:Set|Add|Clear)-Content\b"
    r"|\b(?:Out-File|New-Item)\b|\bsed\s+-i|(?<![\d&>])>{1,2}(?!&)"
    r"|\bgit\s+(?:commit|checkout|reset|restore|clean|stash|merge|rebase|pull|apply|rm|mv)\b"
    r"|\b(?:python[\d.]*|py|node|ruby|perl|bash|sh|cmd|powershell|pwsh)(?:\.exe)?\b"
    r"|\b(?:npm|pnpm|yarn|pip)\s+(?:install|uninstall|add|remove|run|exec)\b", re.I)


def inside(path, parent):
    try:
        return path.relative_to(parent).as_posix()
    except ValueError:
        return None


def check_path(raw, root, cwd):
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cwd)/path
    lexical = Path(os.path.abspath(path))
    path = path.resolve()
    codex = Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex"))).resolve()
    if path in (codex/"hooks.json", codex/"config.toml") or inside(path, codex/"hooks"/"yunstone-gpt") is not None:
        return "하네스 훅 또는 Codex 설정 변경은 별도 유지보수 작업으로 처리하세요."
    relative = inside(path, root)
    if relative in (".codex/protected.txt", ".codex/READONLY"):
        return "보호 정책 변경은 사용자가 별도 터미널에서 검토 후 처리하세요."
    for candidate in (relative, inside(lexical, root)):
        if candidate is not None:
            for pattern in patterns(root/".codex/protected.txt"):
                if matches(candidate, pattern):
                    return "보호된 원본입니다. 복사본에서 작업하세요: " + candidate
    readonly = root/".codex/READONLY"
    if readonly.exists() and (relative is None or not any(matches(relative, p) for p in patterns(readonly))):
        return "읽기 전용 모드의 허용 경로 밖입니다: " + str(path)
    return None


def patch_paths(patch):
    if not isinstance(patch, str) or not patch.startswith("*** Begin Patch") or "*** End Patch" not in patch:
        raise ValueError("invalid patch envelope")
    found = re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", patch, re.M)
    if not found:
        raise ValueError("patch paths could not be inspected")
    return found


def evaluate(data):
    cwd = data.get("cwd") or os.getcwd()
    root = project_root(cwd)
    tool = data.get("tool_name", "")
    args = data.get("tool_input", {})
    if not isinstance(args, dict):
        raise ValueError("tool_input must be an object")
    if tool == "apply_patch":
        for path in patch_paths(args.get("command", "")):
            reason = check_path(path, root, cwd)
            if reason:
                return reason
    elif tool in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        path = args.get("file_path") or args.get("notebook_path")
        if not path:
            raise ValueError("missing edit path")
        return check_path(path, root, cwd)
    elif tool in {"Bash", "PowerShell", "exec_command", "shell_command"}:
        command = args.get("command", args.get("cmd", ""))
        if not isinstance(command, str):
            raise ValueError("command must be text")
        if DANGEROUS.search(command):
            return "위험 명령을 차단했습니다. 대상과 백업을 확인하고 필요한 경우 사용자가 별도 터미널에서 실행하세요."
        if MUTATING.search(command):
            if (root/".codex/READONLY").exists():
                return "읽기 전용 모드에서는 쓰기 가능 셸 명령을 차단합니다. 허용 보고서는 파일 패치로 작성하세요."
            normalized = command.replace("\\", "/")
            for pattern in patterns(root/".codex/protected.txt"):
                prefix = re.split(r"[?*\[]", pattern, maxsplit=1)[0]
                if prefix and os.path.normcase(prefix) in os.path.normcase(normalized):
                    return "보호 경로가 포함된 쓰기 가능 명령입니다: " + pattern
            if re.search(r"(?:\.codex[/\\](?:hooks|config|protected|READONLY))", command, re.I):
                return "하네스 또는 Codex 설정을 변경할 수 있는 셸 명령입니다."
    return None


def main():
    try:
        reason = evaluate(read_event())
    except Exception as exc:
        reason = "보호 검사에 실패하여 이 호출을 차단했습니다: " + type(exc).__name__
    if reason:
        emit("PreToolUse", permissionDecision="deny", permissionDecisionReason="[YunStone GPT] " + reason)


if __name__ == "__main__":
    main()
