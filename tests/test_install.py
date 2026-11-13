"""Installation lifecycle tests, never touching the real user's home."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="yunstone-install-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)/"한글 home"
        self.home.mkdir()

    def run_install(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(ROOT/"install.py"), "--home", str(self.home), *args],
                                capture_output=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def put(self, name, content):
        path = self.home/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def snapshot(self):
        return {p.relative_to(self.home).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.home.rglob("*") if p.is_file()}

    def test_dry_run_no_writes(self):
        before = self.snapshot()
        self.run_install("--dry-run")
        self.assertEqual(before, self.snapshot())

    def test_install_idempotent(self):
        self.run_install()
        before = self.snapshot()
        self.run_install()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(list((self.home/".agents/skills").glob("*/SKILL.md"))), 8)

    def test_preserve_other_settings(self):
        self.put(".codex/AGENTS.md", "# My instructions\nKeep this.\n")
        self.put(".codex/config.toml", 'model = "user-choice"\n')
        original = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo user"}]}]}, "description": "mine"}
        self.put(".codex/hooks.json", json.dumps(original))
        self.run_install()
        self.run_install("--uninstall")
        self.assertEqual(json.loads((self.home/".codex/hooks.json").read_text()), original)
        self.assertIn("Keep this.", (self.home/".codex/AGENTS.md").read_text())
        self.assertEqual((self.home/".codex/config.toml").read_text(), 'model = "user-choice"\n')

    def test_unmanaged_skill_skipped(self):
        path = self.put(".agents/skills/resume-work/SKILL.md", "user content")
        result = self.run_install()
        self.assertIn("건너뜀", result.stdout.decode("utf-8"))
        self.assertEqual(path.read_text(), "user content")
        self.run_install("--uninstall")
        self.assertEqual(path.read_text(), "user content")

    def test_modified_skill_preserved(self):
        self.run_install()
        path = self.put(".agents/skills/resume-work/SKILL.md", "user changed")
        self.run_install()
        self.run_install("--uninstall")
        self.assertEqual(path.read_text(), "user changed")

    def test_adopt_legacy_restores_original(self):
        path = self.put(".agents/skills/resume-work/SKILL.md", "legacy original")
        self.put(".agents/skills/resume-work/.local-harness", "legacy")
        self.run_install()
        self.assertEqual(path.read_text(), "legacy original")
        self.run_install("--adopt-legacy")
        self.assertNotEqual(path.read_text(), "legacy original")
        self.run_install("--uninstall")
        self.assertEqual(path.read_text(), "legacy original")

    def test_invalid_config_no_partial_install(self):
        self.put(".codex/hooks.json", "{invalid")
        before = self.snapshot()
        self.run_install(ok=False)
        self.assertEqual(before, self.snapshot())

    def test_bad_markers_no_partial_install(self):
        self.put(".codex/AGENTS.md", "<!-- yunstone-gpt-harness:start -->")
        before = self.snapshot()
        self.run_install(ok=False)
        self.assertEqual(before, self.snapshot())

    def test_modified_hook_aborts(self):
        self.run_install()
        self.put(".codex/hooks/yunstone-gpt/guard.py", "user modified")
        before = self.snapshot()
        self.run_install(ok=False)
        self.assertEqual(before, self.snapshot())

    def test_uninstall_preserves_added_file(self):
        self.run_install()
        path = self.put(".codex/hooks/yunstone-gpt/user.py", "mine")
        self.run_install("--uninstall")
        self.assertEqual(path.read_text(), "mine")
        self.assertFalse((self.home/".codex/hooks/yunstone-gpt/guard.py").exists())
        self.assertFalse((self.home/".codex/hooks.json").exists())

    def test_uninstall_absent_no_writes(self):
        self.run_install("--uninstall")
        self.assertEqual(self.snapshot(), {})

    def test_uninstall_dry_run(self):
        self.run_install()
        before = self.snapshot()
        self.run_install("--dry-run", "--uninstall")
        self.assertEqual(before, self.snapshot())

    def test_user_edited_agents_preserved(self):
        self.run_install()
        path = self.home/".codex/AGENTS.md"
        path.write_text(path.read_text(encoding="utf-8").replace("한국어", "English"), encoding="utf-8")
        before = path.read_bytes()
        self.run_install("--uninstall")
        self.assertEqual(before, path.read_bytes())

    def test_agents_update_preserves_user_change(self):
        self.run_install()
        path = self.home/".codex/AGENTS.md"
        path.write_text(path.read_text(encoding="utf-8").replace("한국어", "English"), encoding="utf-8")
        before = path.read_bytes()
        self.run_install()
        self.assertEqual(path.read_bytes(), before)

    def test_agents_roundtrip_exact(self):
        path = self.put(".codex/AGENTS.md", "# Mine\nKeep exact spacing.\n")
        before = path.read_bytes()
        self.run_install()
        self.run_install("--uninstall")
        self.assertEqual(path.read_bytes(), before)

    def test_absent_uninstall_preserves_other_configs(self):
        self.put(".codex/AGENTS.md", "# Mine\n")
        self.put(".codex/hooks.json", '{ "description": "mine" }')
        before = self.snapshot()
        self.run_install("--uninstall")
        self.assertEqual(self.snapshot(), before)

    def test_changed_hook_definition_stops_update(self):
        self.run_install()
        path = self.home/".codex/hooks.json"
        hooks = json.loads(path.read_text(encoding="utf-8"))
        hooks["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 25
        path.write_text(json.dumps(hooks), encoding="utf-8")
        before = self.snapshot()
        self.run_install(ok=False)
        self.assertEqual(self.snapshot(), before)

    @unittest.skipUnless(os.name == "nt", "PowerShell entrypoint")
    def test_installed_windows_hook_command(self):
        self.run_install()
        hooks = json.loads((self.home/".codex/hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        payload = json.dumps({"cwd": str(self.home), "tool_name": "Bash", "tool_input": {"command": "git reset --hard"}}).encode()
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], input=payload,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_manifest_cannot_delete_outside(self):
        self.run_install()
        manifest = self.home/".codex/yunstone-gpt-harness/manifest.json"
        state = json.loads(manifest.read_text(encoding="utf-8"))
        victim = Path(self.tmp.name)/"outside"
        victim.write_bytes(b"keep")
        state["files"][str(victim)] = {"sha256": hashlib.sha256(b"keep").hexdigest(), "original": None}
        manifest.write_text(json.dumps(state), encoding="utf-8")
        self.run_install("--uninstall", ok=False)
        self.assertEqual(victim.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
