"""Behavioral tests: fake hook events, real subprocesses, temporary projects."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Hooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="yunstone-test-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)/"한글 project"
        (self.project/".codex").mkdir(parents=True)
        (self.project/".git").mkdir()
        self.write(".codex/protected.txt", "input/\n인계용/*.zip\n원본.pdf\n")

    def write(self, name, content=""):
        path = self.project/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_hook(self, tool="apply_patch", args=None, script="guard.py", cwd=None, raw=None):
        event = {"tool_name": tool, "tool_input": args or {}, "cwd": str(cwd or self.project), "source": "compact"}
        payload = raw if raw is not None else json.dumps(event).encode()
        env = dict(os.environ, CODEX_HOME=str(Path(self.tmp.name)/"home/.codex"), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, str(ROOT/"hooks"/script)], input=payload,
                                capture_output=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else {}

    def patch(self, text):
        return self.run_hook(args={"command": "*** Begin Patch\n" + text + "\n*** End Patch"})

    def test_protected_patch_operations(self):
        for action in ("Add File", "Update File", "Delete File"):
            with self.subTest(action=action):
                result = self.patch(f"*** {action}: input/a.txt\n+x")
                self.assertEqual(result.get("permissionDecision"), "deny")

    def test_move_destination(self):
        self.assertEqual(self.patch("*** Update File: work/a.txt\n*** Move to: input/a.txt\n-x\n+y").get("permissionDecision"), "deny")

    def test_multi_file_patch(self):
        self.assertEqual(self.patch("*** Add File: work/a\n+x\n*** Add File: 原本\n+x\n*** Delete File: 원본.pdf").get("permissionDecision"), "deny")

    def test_allowed_edit(self):
        self.assertEqual(self.patch("*** Add File: work/input/a.txt\n+x"), {})

    def test_glob(self):
        self.assertEqual(self.patch("*** Delete File: 인계용/a.zip").get("permissionDecision"), "deny")
        self.assertEqual(self.patch("*** Add File: 인계용/README.md\n+x"), {})

    def test_parent_path_normalization(self):
        self.assertEqual(self.patch("*** Update File: work/../input/a\n-x\n+y").get("permissionDecision"), "deny")

    def test_legacy_file_tool(self):
        self.assertEqual(self.run_hook("Write", {"file_path": "input/a"}).get("permissionDecision"), "deny")

    def test_readonly_allowlist(self):
        self.write(".codex/READONLY", "review/\n")
        self.assertEqual(self.patch("*** Add File: review/r.md\n+x"), {})
        self.assertEqual(self.patch("*** Add File: src/a\n+x").get("permissionDecision"), "deny")
        self.assertEqual(self.patch("*** Add File: ../outside.txt\n+x").get("permissionDecision"), "deny")

    def test_readonly_empty(self):
        self.write(".codex/READONLY")
        self.assertEqual(self.patch("*** Add File: review/r.md\n+x").get("permissionDecision"), "deny")

    def test_readonly_shell(self):
        self.write(".codex/READONLY", "review/")
        for command in ('echo hi > review/r.md', 'python -c "open(\'a\',\'w\')"', 'Set-Content a x'):
            self.assertEqual(self.run_hook("Bash", {"command": command}).get("permissionDecision"), "deny")
        self.assertEqual(self.run_hook("Bash", {"command": "rg foo src 2>&1"}), {})

    def test_dangerous(self):
        for cmd in ('rm -rf build', 'Remove-Item -LiteralPath dist -Recurse', 'git reset --hard HEAD',
                    'git push --force-with-lease origin main', 'git clean -fd', 'rmdir /s tmp'):
            with self.subTest(command=cmd):
                self.assertEqual(self.run_hook("Bash", {"command": cmd}).get("permissionDecision"), "deny")

    def test_normal_shell(self):
        for cmd in ('git status --short', 'git push origin main', 'Get-Content input/a.txt', 'rm work/tmp.txt'):
            self.assertEqual(self.run_hook("Bash", {"command": cmd}), {})

    def test_protected_shell(self):
        self.assertEqual(self.run_hook("Bash", {"command": 'python -c "open(\'input/a\',\'w\')"'}).get("permissionDecision"), "deny")

    def test_corrupt_input_denies(self):
        self.assertEqual(self.run_hook(raw=b"invalid-json").get("permissionDecision"), "deny")
        self.assertEqual(self.run_hook(args={"command": "invalid patch"}).get("permissionDecision"), "deny")

    def test_subdirectory(self):
        sub = self.project/"src/deep"
        sub.mkdir(parents=True)
        self.assertEqual(self.run_hook("Write", {"file_path": "../../input/a"}, cwd=sub).get("permissionDecision"), "deny")

    def test_self_protection(self):
        self.assertEqual(self.patch("*** Delete File: .codex/protected.txt").get("permissionDecision"), "deny")
        path = Path(self.tmp.name)/"home/.codex/hooks.json"
        self.assertEqual(self.run_hook("Write", {"file_path": str(path)}).get("permissionDecision"), "deny")

    def test_restore_from_subdirectory(self):
        self.write("PROGRESS.md", "# 진행\n다음 할 일: 문서 확인")
        sub = self.project/"src"
        sub.mkdir()
        result = self.run_hook(script="session_restore.py", cwd=sub)
        self.assertEqual(result["hookEventName"], "SessionStart")
        self.assertIn("문서 확인", result["additionalContext"])
        self.assertIn("신뢰되지 않은", result["additionalContext"])

    def test_nested_progress_does_not_hide_protection(self):
        self.write("src/PROGRESS.md", "nested")
        self.assertEqual(self.run_hook("Write", {"file_path": "../input/a"}, cwd=self.project/"src").get("permissionDecision"), "deny")

    def test_protected_symlink_outward(self):
        outside = Path(self.tmp.name)/"outside"
        outside.mkdir()
        try:
            (self.project/"input").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.patch("*** Add File: input/a\n+x").get("permissionDecision"), "deny")

    def test_restore_bounded(self):
        self.write("PROGRESS.md", "x"*20000)
        self.assertLess(len(self.run_hook(script="session_restore.py")["additionalContext"]), 7000)

    def test_restore_missing(self):
        plain = Path(self.tmp.name)/"empty"
        plain.mkdir()
        self.assertEqual(self.run_hook(script="session_restore.py", cwd=plain), {})

    def test_symlink_resolved(self):
        self.write("input/a", "original")
        try:
            (self.project/"alias").symlink_to(self.project/"input", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.patch("*** Delete File: alias/a").get("permissionDecision"), "deny")


if __name__ == "__main__":
    unittest.main(verbosity=2)
