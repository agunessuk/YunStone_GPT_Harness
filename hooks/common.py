"""Shared local policy discovery. Python 3.9+, standard library only."""
import fnmatch
import json
import os
from pathlib import Path


def read_event():
    import sys
    event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    if not isinstance(event, dict):
        raise ValueError("event must be an object")
    return event


def emit(event, **fields):
    import sys
    sys.stdout.buffer.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": event, **fields}}, ensure_ascii=False).encode("utf-8"))


def project_root(cwd):
    current = Path(cwd).resolve()
    fallback = current
    for directory in (current, *current.parents):
        if any((directory/".codex"/name).is_file() for name in ("protected.txt", "READONLY")):
            return directory
        if (directory/".git").exists():
            return directory
        if (directory/"PROGRESS.md").is_file():
            fallback = directory
        if directory == Path.home():
            break
    return fallback


def patterns(path):
    if not path.exists():
        return []
    return [line.strip().replace("\\", "/") for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def matches(relative, pattern):
    relative = os.path.normcase(relative).replace("\\", "/")
    pattern = os.path.normcase(pattern).replace("\\", "/")
    if pattern.startswith("./"):
        pattern = pattern[2:]
    return (relative == pattern.rstrip("/") or relative.startswith(pattern.rstrip("/") + "/")
            or fnmatch.fnmatchcase(relative, pattern))
