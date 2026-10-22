"""No network, authorization, or real user configuration is used by these tests."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/adapt_capcut_claude.py"
SPEC = importlib.util.spec_from_file_location("capcut_claude_adapter", MODULE_PATH)
adapter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


class ClaudeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "official"
        self.plugin = self.source / "codex"
        self.project = self.root / "project"
        self.write(".codex-plugin/plugin.json", json.dumps({"name": "CapCut", "version": "0.2.5", "license": "UNLICENSED"}))
        self.source_config = {"mcpServers": {
            name: {"url": url, "oauth_resource": url, "http_headers": adapter.HEADERS,
                   "omit_tools_from": ["code_mode"], "tool_timeout_sec": 600}
            for name, url in adapter.ENDPOINTS.items()
        }}
        self.write(".mcp.json", json.dumps(self.source_config))
        for name in adapter.SKILLS:
            self.write(f"skills/{name}/SKILL.md", f"---\nname: {name}\ndescription: Original.\n---\nRead scripts/helper.py\n")
            self.write(f"skills/{name}/scripts/helper.py", "VALUE = 42\n")
            self.write(f"skills/{name}/references/guide.md", "Original reference\n")
        self.write("skills/mcp-auth/SKILL.md", "Never copy Codex OAuth\n")
        self.write("skills/mcp-auth/scripts/capcut-login.mjs", "throw new Error('must not run')\n")
        self.write("skills/search-templates/SKILL.md", "Codex browser\n")
        self.write("skills/generate-media/SKILL.md", "Paid cards\n")

    def write(self, relative, content):
        path = self.plugin / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_adapter(self, **kwargs):
        return adapter.adapt(self.source, self.project, **kwargs)

    def target(self, upstream):
        return self.project / ".claude/skills" / adapter.SKILLS[upstream]

    def config(self):
        return json.loads((self.project / ".mcp.json").read_text(encoding="utf-8"))

    def existing_config(self, value):
        self.project.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, indent=3).encode("utf-8") + b"\n"
        (self.project / ".mcp.json").write_bytes(raw)
        return raw

    def link(self, target, link):
        try:
            link.symlink_to(target, target_is_directory=True)
        except (NotImplementedError, OSError) as error:
            if os.name == "nt":
                result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=False)
                if result.returncode == 0:
                    return
            self.skipTest(f"Symlinks unavailable: {error}")

    def test_creates_four_host_wrappers_and_canonical_http_config(self):
        report = self.run_adapter()
        self.assertIn("remain unverified", report[-1])
        for upstream, name in adapter.SKILLS.items():
            target = self.target(upstream)
            wrapper = (target / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"name: {name}\n", wrapper)
            self.assertIn("host-adaptation.md", wrapper)
            self.assertEqual((target / "references/original/scripts/helper.py").read_bytes(), (self.plugin / f"skills/{upstream}/scripts/helper.py").read_bytes())
            self.assertEqual((target / "references/original/SKILL.md").read_bytes(), (self.plugin / f"skills/{upstream}/SKILL.md").read_bytes())
            guide = (target / "references/host-adaptation.md").read_text(encoding="utf-8")
            self.assertIn("Never authenticate `capcut_creation_resource`", guide)
            self.assertIn("never run", guide.lower())
            manifest = json.loads((target / "adapter-manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["authentication_verified"])
        self.assertEqual(set(self.config()["mcpServers"]), set(adapter.ENDPOINTS))
        for name, url in adapter.ENDPOINTS.items():
            self.assertEqual(self.config()["mcpServers"][name], {"type": "http", "url": url, "headers": adapter.HEADERS})

    def test_plugin_subfolder_is_an_accepted_source(self):
        adapter.adapt(self.plugin, self.project)
        self.assertTrue((self.target("capcut-upload") / "SKILL.md").exists())

    def test_excludes_codex_auth_templates_generation_and_credentials(self):
        self.write("skills/capcut-upload/auth.json", "Not a real credential\n")
        self.write("skills/capcut-upload/tests/test.py", "Not payload\n")
        self.run_adapter()
        files = [path.relative_to(self.project).as_posix() for path in self.project.rglob("*") if path.is_file()]
        self.assertFalse(any("mcp-auth" in path or "capcut-login.mjs" in path for path in files))
        self.assertFalse(any("search-templates" in path or "generate-media" in path for path in files))
        self.assertFalse(any(path.endswith("auth.json") or "/tests/" in path for path in files))

    def test_preserves_unrelated_server_and_top_level_config(self):
        original = {"description": "Keep this", "mcpServers": {"other": {"command": "my-tool", "args": ["--local"], "env": {"EXAMPLE": "unchanged"}}}}
        self.existing_config(original)
        self.run_adapter()
        updated = self.config()
        self.assertEqual(updated["description"], original["description"])
        self.assertEqual(updated["mcpServers"]["other"], original["mcpServers"]["other"])

    def test_idempotent_run_does_not_rewrite_or_create_backup(self):
        self.run_adapter()
        path = self.project / ".mcp.json"
        first = path.read_bytes(), path.stat().st_mtime_ns
        report = self.run_adapter()
        self.assertTrue(all(line.startswith("unchanged:") for line in report[:-1]))
        self.assertEqual(first, (path.read_bytes(), path.stat().st_mtime_ns))
        self.assertFalse((self.project / ".claude/skill-backups").exists())

    def test_dry_run_writes_nothing(self):
        report = self.run_adapter(dry_run=True)
        self.assertTrue(all(line.startswith("dry-run:") for line in report))
        self.assertFalse(self.project.exists())

    def test_conflicting_server_refuses_before_any_skill_is_created(self):
        raw = self.existing_config({"mcpServers": {"capcut_creation": {"type": "http", "url": "https://different.example/mcp"}}})
        with self.assertRaisesRegex(adapter.AdapterError, "Conflicting project server"):
            self.run_adapter()
        self.assertEqual((self.project / ".mcp.json").read_bytes(), raw)
        self.assertFalse((self.project / ".claude").exists())

    def test_conflicting_skill_preflights_all_destinations(self):
        target = self.target("video-editing")
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("Keep my version", encoding="utf-8")
        with self.assertRaisesRegex(adapter.AdapterError, "Different skill exists"):
            self.run_adapter()
        self.assertFalse(self.target("capcut-stdraft-builder").exists())
        self.assertFalse((self.project / ".mcp.json").exists())
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "Keep my version")

    def test_replace_backs_up_config_and_changed_skill_outside_discovery(self):
        self.run_adapter()
        target = self.target("capcut-upload")
        (target / "my-edit.txt").write_text("Keep", encoding="utf-8")
        raw = self.existing_config({"keep": 17, "mcpServers": {"capcut_creation": {"url": "https://different.example/mcp"}, "other": {"command": "keep"}}})
        self.run_adapter(replace=True)
        backups = list((self.project / ".claude/skill-backups").iterdir())
        self.assertEqual(len(backups), 2)
        self.assertTrue(any(path.is_file() and path.read_bytes() == raw for path in backups))
        self.assertTrue(any(path.is_dir() and (path / "my-edit.txt").read_text(encoding="utf-8") == "Keep" for path in backups if path.is_dir()))
        self.assertTrue(all(not path.is_relative_to(self.project / ".claude/skills") for path in backups))
        self.assertEqual(self.config()["mcpServers"]["other"], {"command": "keep"})
        self.assertEqual(self.config()["keep"], 17)
        self.assertFalse((target / "my-edit.txt").exists())

    def test_noncanonical_source_url_and_custom_header_are_rejected(self):
        for field, value in (("url", "http://www.capcut.com/api/external_mcp"), ("url", "https://evil.example/mcp"), ("http_headers", {"Authorization": "fake-test-only"})):
            with self.subTest(field=field, value=value):
                config = json.loads(json.dumps(self.source_config))
                config["mcpServers"]["capcut_creation"][field] = value
                self.write(".mcp.json", json.dumps(config))
                with self.assertRaises(adapter.AdapterError):
                    self.run_adapter()
                self.assertFalse(self.project.exists())

    def test_credentials_inside_supported_payload_are_rejected(self):
        self.write("skills/capcut-upload/scripts/credentials.json", "Not real credentials\n")
        with self.assertRaisesRegex(adapter.AdapterError, "Credential-like"):
            self.run_adapter()
        self.assertFalse(self.project.exists())

    def test_missing_upstream_skill_is_rejected_before_writes(self):
        (self.plugin / "skills/video-editing/SKILL.md").unlink()
        with self.assertRaisesRegex(adapter.AdapterError, "Required original SKILL.md"):
            self.run_adapter()
        self.assertFalse(self.project.exists())

    def test_source_target_overlap_is_rejected(self):
        with self.assertRaisesRegex(adapter.AdapterError, "must not overlap"):
            adapter.adapt(self.source, self.source / "nested-project")
        self.assertFalse((self.source / "nested-project").exists())

    def test_source_junction_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.link(outside, self.plugin / "skills/capcut-upload/scripts/linked")
        with self.assertRaisesRegex(adapter.AdapterError, "Symlink/reparse"):
            self.run_adapter()
        self.assertFalse(self.project.exists())

    def test_destination_parent_junction_is_rejected(self):
        self.project.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        self.link(outside, self.project / ".claude")
        with self.assertRaisesRegex(adapter.AdapterError, "Symlink/reparse"):
            self.run_adapter(replace=True)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.project / ".mcp.json").exists())

    def test_existing_invalid_json_or_server_shape_is_not_overwritten(self):
        self.project.mkdir()
        config = self.project / ".mcp.json"
        for raw in (b"broken", b'{"mcpServers":[]}', b'{"mcpServers":{},"mcpServers":{}}'):
            with self.subTest(raw=raw):
                config.write_bytes(raw)
                with self.assertRaises(adapter.AdapterError):
                    self.run_adapter(replace=True)
                self.assertEqual(config.read_bytes(), raw)
                self.assertFalse((self.project / ".claude").exists())

    def test_late_commit_failure_restores_config_and_all_prior_skills(self):
        raw = self.existing_config({"mcpServers": {"other": {"command": "keep"}}})
        original_rename = Path.rename

        def fail_config_stage(path, target):
            if path.name.startswith(".capcut-claude-stage-") and Path(target).name == ".mcp.json":
                raise OSError("Simulated config commit failure")
            return original_rename(path, target)

        with mock.patch.object(Path, "rename", fail_config_stage):
            with self.assertRaisesRegex(adapter.AdapterError, "original destinations preserved"):
                self.run_adapter()
        self.assertEqual((self.project / ".mcp.json").read_bytes(), raw)
        self.assertTrue(all(not self.target(name).exists() for name in adapter.SKILLS))
        self.assertFalse(list(self.project.rglob(".capcut-claude-stage-*")))
        self.assertEqual(list((self.project / ".claude/skill-backups").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
