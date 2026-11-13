"""Non-destructive Codex installer. Python 3.9+, no third-party packages."""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import uuid

REPO = Path(__file__).resolve().parent
ID = "yunstone-gpt-harness"
START = "<!-- yunstone-gpt-harness:start -->"
END = "<!-- yunstone-gpt-harness:end -->"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return path.read_bytes() if path.exists() else None


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_json(path, default):
    data = read(path)
    obj = json.loads(data.decode("utf-8-sig")) if data is not None else default
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        path.unlink(missing_ok=True)
        return
    fd, name = tempfile.mkstemp(prefix=".yunstone-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def command(script):
    args = [sys.executable, str(script)]
    if os.name == "nt":
        # Codex Windows commands can be evaluated by PowerShell. Quote as PS literals.
        return "& " + " ".join("'" + a.replace("'", "''") + "'" for a in args)
    return shlex.join(args)


def block_update(current, body, uninstall):
    text = (current or b"").decode("utf-8-sig")
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError("AGENTS.md has malformed/duplicate managed markers")
    block = START + "\n" + body.strip() + "\n" + END
    if START in text:
        begin = text.index(START)
        end = text.index(END) + len(END)
        if end <= begin:
            raise ValueError("AGENTS.md marker order is invalid")
        text = text[:begin] + ("" if uninstall else block) + text[end:]
    elif not uninstall:
        text += ("\n\n" if text and not text.endswith("\n\n") else "") + block + "\n"
    if uninstall and not text.strip():
        return None
    return text.encode("utf-8")


def build(args):
    home = Path(args.home).expanduser().resolve() if args.home else Path.home()
    codex = (home/".codex" if args.home else Path(os.environ.get("CODEX_HOME", str(home/".codex")))).resolve()
    skills = home/".agents/skills"
    state_path = codex/"yunstone-gpt-harness/manifest.json"
    state = read_json(state_path, {"id": ID, "version": 1, "files": {}, "hooks": {}})
    if state.get("id") != ID or state.get("version") != 1:
        raise ValueError("Unknown install manifest")
    state = copy.deepcopy(state)
    changes = {}
    notes = []
    roots = [codex, skills.resolve()]

    def safe(path):
        resolved = path.resolve()
        if not any(resolved == r or r in resolved.parents for r in roots):
            raise ValueError(f"Path escapes installation roots: {path}")
        # Refuse links inside destination trees (including parent directory links).
        for candidate in (path, *path.parents):
            if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
                raise ValueError(f"Linked install destination: {candidate}")
            if candidate == home:
                break

    def plan(path, new):
        safe(path)
        old = read(path)
        if old != new:
            changes[path] = (old, new)

    def managed(path, content, adopt=False):
        safe(path)
        key = str(path)
        previous = state["files"].get(key)
        old = read(path)
        if previous:
            if old is not None and digest(old) != previous["sha256"]:
                raise ValueError(f"Installed file was edited; preserve and compare first: {path}")
        elif old is not None and not adopt:
            raise ValueError(f"Unmanaged destination exists: {path}")
        original = previous.get("original") if previous else (base64.b64encode(old).decode() if old is not None else None)
        plan(path, content)
        state["files"][key] = {"sha256": digest(content), "original": original}

    # Parse all shared config before any writes.
    hooks_path = codex/"hooks.json"
    hooks = read_json(hooks_path, {})
    events = hooks.get("hooks", {})
    if not isinstance(events, dict) or any(not isinstance(v, list) for v in events.values()):
        raise ValueError("hooks.json must contain event arrays")
    events = copy.deepcopy(events)
    had_owned_hooks = bool(state.get("hooks"))
    for event, group in state.get("hooks", {}).items():
        if not args.uninstall and group not in events.get(event, []):
            raise ValueError("Installed hook definition changed; compare hooks.json and manifest before updating")
        events[event] = [g for g in events.get(event, []) if g != group]
        if not events[event]:
            events.pop(event)
    agents_path = codex/"AGENTS.md"
    agents_old = read(agents_path)
    agents_body = (REPO/"global/AGENTS.md").read_text(encoding="utf-8-sig")
    agents_new = block_update(agents_old, agents_body, args.uninstall)
    previous_block = state.get("agents_block")
    if not args.uninstall and previous_block and agents_old:
        current_text = agents_old.decode("utf-8-sig")
        if previous_block not in current_text:
            notes.append("보존: 사용자가 수정한 AGENTS.md 관리 블록")
            agents_new = agents_old
    if args.uninstall and state.get("agents_installed_sha") == digest(agents_old or b""):
        original = state.get("agents_original")
        agents_new = base64.b64decode(original) if original is not None else None
    if args.uninstall:
        for key, info in list(state["files"].items()):
            path = Path(key)
            safe(path)
            old = read(path)
            if old is not None and digest(old) != info["sha256"]:
                notes.append(f"보존: 설치 후 수정한 파일 {path}")
                continue
            plan(path, base64.b64decode(info["original"]) if info.get("original") is not None else None)
            del state["files"][key]
        state["hooks"] = {}
        if agents_old is not None and START in agents_old.decode("utf-8-sig"):
            installed_block = state.get("agents_block")
            current_text = agents_old.decode("utf-8-sig")
            present_block = current_text[current_text.index(START):current_text.index(END) + len(END)]
            if installed_block and present_block != installed_block:
                notes.append("보존: 사용자가 수정한 AGENTS.md 관리 블록")
                agents_new = agents_old
            else:
                state.pop("agents_block", None)
    else:
        for source in sorted((REPO/"skills").iterdir()):
            if not (source/"SKILL.md").is_file():
                continue
            target = skills/source.name
            known = any(str(Path(k).parent) == str(target) for k in state["files"])
            legacy = (target/".local-harness").is_file()
            if target.exists() and not known and not (args.adopt_legacy and legacy):
                notes.append(f"건너뜀: 기존 동명 스킬 {source.name}")
                continue
            sources = sorted(p for p in source.rglob("*") if p.is_file())
            # One modified skill file preserves the whole skill.
            conflict = any(read(Path(k)) is not None and digest(read(Path(k))) != info["sha256"]
                           for k, info in state["files"].items() if target in Path(k).parents)
            if conflict:
                notes.append(f"보존: 사용자가 수정한 스킬 {source.name}")
                continue
            for file in sources:
                managed(target/file.relative_to(source), file.read_bytes(), adopt=args.adopt_legacy and legacy)
        hook_dir = codex/"hooks/yunstone-gpt"
        for file in sorted((REPO/"hooks").glob("*.py")):
            managed(hook_dir/file.name, file.read_bytes())
        installed = {
            "PreToolUse": {"matcher": "^(Bash|PowerShell|exec_command|shell_command|apply_patch|Edit|Write|MultiEdit|NotebookEdit)$",
                           "hooks": [{"type": "command", "command": command(hook_dir/"guard.py"), "timeout": 10}]},
            "SessionStart": {"matcher": "^(startup|resume|clear|compact|fork)$",
                             "hooks": [{"type": "command", "command": command(hook_dir/"session_restore.py"), "timeout": 10}]}}
        for event, group in installed.items():
            events.setdefault(event, []).append(group)
        state["hooks"] = installed
        if agents_new != agents_old or not previous_block:
            if "agents_original" not in state:
                state["agents_original"] = base64.b64encode(agents_old).decode() if agents_old is not None else None
            state["agents_block"] = START + "\n" + agents_body.strip() + "\n" + END
            state["agents_installed_sha"] = digest(agents_new or b"")
    if events:
        hooks["hooks"] = events
    else:
        hooks.pop("hooks", None)
    if not args.uninstall or had_owned_hooks:
        plan(hooks_path, json_bytes(hooks) if hooks else None)
    if not args.uninstall or previous_block:
        plan(agents_path, agents_new)
    # Do not create an empty manifest when uninstalling an absent installation.
    if not args.uninstall or state_path.exists():
        plan(state_path, json_bytes(state))
    return changes, notes, codex


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="YunStone GPT Harness 설치·갱신·제거")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--home", help="격리 시험용 홈. 실제 사용자 홈과 CODEX_HOME 대신 사용")
    parser.add_argument("--adopt-legacy", action="store_true", help=".local-harness 표지가 있는 기존 스킬만 백업 후 인수")
    args = parser.parse_args()
    try:
        changes, notes, codex = build(args)
        for note in notes:
            print(note)
        for path, (old, new) in changes.items():
            action = "제거" if new is None else ("생성" if old is None else "갱신")
            print(("[미리보기] " if args.dry_run else "") + action + ": " + str(path))
        if args.dry_run:
            print(f"미리보기 완료: {len(changes)}개 파일. 파일을 쓰지 않았습니다.")
            return 0
        if not changes:
            print("변경 없음.")
            return 0
        backup = codex/"yunstone-gpt-harness/backups"/uuid.uuid4().hex
        backup.mkdir(parents=True)
        journal = []
        for index, (path, (old, new)) in enumerate(changes.items()):
            name = str(index) + ".bin"
            if old is not None:
                (backup/name).write_bytes(old)
            journal.append({"path": str(path), "backup": name if old is not None else None})
        (backup/"index.json").write_bytes(json_bytes(journal))
        done = []
        try:
            for path, (old, new) in changes.items():
                if read(path) != old:
                    raise RuntimeError(f"File changed during install: {path}")
                atomic(path, new)
                done.append(path)
        except Exception:
            for path in reversed(done):
                atomic(path, changes[path][0])
            raise
        print("백업: " + str(backup))
        print("완료. 새 Codex 세션을 열고 /hooks에서 훅 정의를 검토·신뢰하세요." if not args.uninstall else "제거 완료. 수정된 파일과 백업은 보존합니다.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print("설치 중단: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
