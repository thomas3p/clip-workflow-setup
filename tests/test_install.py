"""Portable workflow installer tests; only temporary directories are modified."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "distribution"
        self.source.mkdir()
        self.home = self.root / "home"
        self.write("SKILL.md", "---\nname: clip-workflow-setup\ndescription: Test workflow.\n---\nHello\n")
        self.write("agents/openai.yaml", "display_name: Workflow\n")
        self.write("references/guide.md", "Reference\n")
        self.write("scripts/helper.py", "print('helper')\n")
        self.write("assets/example.txt", "Asset\n")

    def write(self, relative, content):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def target(self, agent="codex", base=None):
        return (base or self.home) / (".agents" if agent == "codex" else ".claude") / "skills" / installer.SKILL_NAME

    def run_install(self, **options):
        return installer.install(self.source, home=self.home, **options)

    def link(self, target, link, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (NotImplementedError, OSError) as error:
            if os.name == "nt" and directory:
                # Windows junctions need no symlink privilege. Exercise the
                # same reparse-point guard with real filesystem links.
                result = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                    capture_output=True, text=True, check=False,
                )
                if result.returncode == 0:
                    return
            self.skipTest(f"Symlinks unavailable: {error}")

    def test_default_installs_both_agents(self):
        results = self.run_install()
        self.assertEqual([result.action for result in results], ["installed", "installed"])
        for agent in ("codex", "claude"):
            destination = self.target(agent)
            self.assertEqual((destination / "SKILL.md").read_bytes(), (self.source / "SKILL.md").read_bytes())
            self.assertTrue((destination / "agents/openai.yaml").is_file())
            self.assertTrue((destination / "references/guide.md").is_file())
            self.assertTrue((destination / "scripts/helper.py").is_file())
            self.assertTrue((destination / "assets/example.txt").is_file())
        self.assertEqual([result.destination for result in results], [self.target(), self.target("claude")])

    def test_project_scope_and_single_agent(self):
        project = self.root / "project"
        results = self.run_install(agent="claude", project=project)
        self.assertEqual(results[0].destination, self.target("claude", project))
        self.assertTrue((self.target("claude", project) / "SKILL.md").is_file())
        self.assertFalse(self.home.exists())
        self.assertFalse((project / ".agents").exists())

    def test_identical_install_is_no_op(self):
        self.run_install()
        marker = self.target() / "SKILL.md"
        before = marker.stat().st_mtime_ns
        results = self.run_install(replace=True)
        self.assertEqual([result.action for result in results], ["unchanged", "unchanged"])
        self.assertEqual(marker.stat().st_mtime_ns, before)
        self.assertFalse(installer._backup_parent(self.target()).exists())

    def test_changed_existing_refuses_and_preflights_both(self):
        existing = self.target("claude")
        existing.mkdir(parents=True)
        marker = existing / "mine.txt"
        marker.write_text("Keep my existing files", encoding="utf-8")
        with self.assertRaisesRegex(installer.InstallError, "Different installation"):
            self.run_install()
        self.assertEqual(marker.read_text(encoding="utf-8"), "Keep my existing files")
        self.assertEqual(list(existing.iterdir()), [marker])
        self.assertFalse(self.target().exists())
        self.assertFalse((self.home / ".agents").exists())

    def test_replace_preserves_unique_backup(self):
        self.run_install(agent="codex")
        destination = self.target()
        (destination / "local.txt").write_text("First local edit", encoding="utf-8")
        first = self.run_install(agent="codex", replace=True)[0]
        self.assertEqual(first.action, "replaced")
        self.assertEqual(first.backup.parent, self.home / ".agents/skill-backups")
        self.assertFalse(first.backup.is_relative_to(destination.parent))
        self.assertEqual((first.backup / "local.txt").read_text(encoding="utf-8"), "First local edit")
        self.assertFalse((destination / "local.txt").exists())
        (destination / "local.txt").write_text("Second local edit", encoding="utf-8")
        second = self.run_install(agent="codex", replace=True)[0]
        self.assertNotEqual(first.backup, second.backup)
        self.assertFalse(second.backup.is_relative_to(destination.parent))
        self.assertEqual((first.backup / "local.txt").read_text(encoding="utf-8"), "First local edit")
        self.assertEqual((second.backup / "local.txt").read_text(encoding="utf-8"), "Second local edit")

    def test_excludes_distribution_files_vendor_tests_and_evals(self):
        for name in ("README.md", "install.py", "auth.json", "vendor/auth.json", "evals/case.json", "tests/test.py", "scripts/tests/test_nested.py"):
            self.write(name, "Must never be installed\n")
        self.run_install(agent="codex")
        destination = self.target()
        for name in ("README.md", "install.py", "auth.json", "vendor", "evals", "tests", "scripts/tests"):
            self.assertFalse((destination / name).exists(), name)

    def test_credential_in_payload_is_rejected(self):
        self.write("scripts/.env", "Not a real secret\n")
        with self.assertRaisesRegex(installer.InstallError, "Credential-like"):
            self.run_install()
        self.assertFalse(self.home.exists())

    def test_dry_run_creates_no_files(self):
        results = self.run_install(dry_run=True)
        self.assertEqual([result.action for result in results], ["dry-run: installed", "dry-run: installed"])
        self.assertFalse(self.home.exists())
        self.assertEqual(set(self.root.iterdir()), {self.source})

    def test_source_destination_overlap_is_rejected(self):
        with self.assertRaisesRegex(installer.InstallError, "must not overlap"):
            self.run_install(project=self.source)
        self.assertFalse((self.source / ".agents").exists())

    def test_source_payload_symlink_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "private.txt").write_text("Do not copy", encoding="utf-8")
        self.link(outside, self.source / "assets/linked", directory=True)
        with self.assertRaisesRegex(installer.InstallError, "Symlink/reparse"):
            self.run_install()
        self.assertFalse(self.home.exists())

    def test_source_parent_symlink_is_rejected(self):
        linked = self.root / "linked-distribution"
        self.link(self.source, linked, directory=True)
        with self.assertRaisesRegex(installer.InstallError, "Symlink/reparse"):
            installer.install(linked, home=self.home)
        self.assertFalse(self.home.exists())

    def test_destination_parent_symlink_is_rejected(self):
        self.home.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        self.link(outside, self.home / ".agents", directory=True)
        with self.assertRaisesRegex(installer.InstallError, "Symlink/reparse"):
            self.run_install(replace=True)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.home / ".claude").exists())

    def test_destination_symlink_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        destination = self.target()
        destination.parent.mkdir(parents=True)
        self.link(outside, destination, directory=True)
        with self.assertRaisesRegex(installer.InstallError, "Symlink/reparse"):
            self.run_install(agent="codex", replace=True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_inside_destination_is_rejected(self):
        self.run_install(agent="codex")
        outside = self.root / "outside"
        outside.mkdir()
        marker = outside / "private.txt"
        marker.write_text("Do not overwrite", encoding="utf-8")
        self.link(outside, self.target() / "linked", directory=True)
        with self.assertRaisesRegex(installer.InstallError, "Symlink/reparse"):
            self.run_install(agent="codex", replace=True)
        self.assertEqual(marker.read_text(encoding="utf-8"), "Do not overwrite")

    def test_link_detection_handles_posix_and_windows(self):
        self.assertTrue(installer._is_link(mock.Mock(st_mode=stat.S_IFLNK, st_file_attributes=0)))
        self.assertTrue(installer._is_link(mock.Mock(st_mode=stat.S_IFDIR, st_file_attributes=0x400)))
        self.assertFalse(installer._is_link(mock.Mock(st_mode=stat.S_IFREG, st_file_attributes=0)))

    def test_missing_or_invalid_required_skill_is_rejected(self):
        (self.source / "SKILL.md").unlink()
        with self.assertRaisesRegex(installer.InstallError, "Required regular"):
            self.run_install()
        self.write("SKILL.md", "No metadata\n")
        with self.assertRaisesRegex(installer.InstallError, "YAML frontmatter"):
            self.run_install()
        self.write("SKILL.md", "---\nname: wrong-name\ndescription: Test\n---\n")
        with self.assertRaisesRegex(installer.InstallError, "must declare name"):
            self.run_install()
        self.assertFalse(self.home.exists())

    def test_payload_directory_cannot_be_regular_file(self):
        self.write("agents/openai.yaml", "valid\n")
        # Use another optional directory to avoid deleting a directory tree.
        (self.source / "assets/example.txt").unlink()
        (self.source / "assets").rmdir()
        self.write("assets", "not a directory\n")
        with self.assertRaisesRegex(installer.InstallError, "Payload folder"):
            self.run_install()
        self.assertFalse(self.home.exists())

    def test_unsafe_payload_names_are_rejected(self):
        for name in ("../escape", "bad:stream", "NUL", "CON.txt", "bad\\name", "trailing.", "control\nname"):
            with self.subTest(name=name), self.assertRaises(installer.InstallError):
                installer._validate_name(name)

    def test_replacement_failure_rolls_back_original(self):
        self.run_install(agent="codex")
        destination = self.target()
        marker = destination / "local.txt"
        marker.write_text("Keep after failure", encoding="utf-8")
        original_rename = Path.rename

        def fail_stage_rename(path, target):
            if path.name.startswith(f".{installer.SKILL_NAME}.stage-"):
                raise OSError("Simulated rename failure")
            return original_rename(path, target)

        with mock.patch.object(Path, "rename", fail_stage_rename):
            with self.assertRaisesRegex(installer.InstallError, "original destination restored"):
                self.run_install(agent="codex", replace=True)
        self.assertEqual(marker.read_text(encoding="utf-8"), "Keep after failure")
        self.assertFalse(list(destination.parent.glob(f".{installer.SKILL_NAME}.stage-*")))
        self.assertEqual(list(installer._backup_parent(destination).iterdir()), [])

    def test_backup_parent_link_is_rejected_before_mutating_either_target(self):
        self.run_install()
        for agent in ("codex", "claude"):
            (self.target(agent) / "local.txt").write_text("Keep local edit", encoding="utf-8")
        outside = self.root / "outside"
        outside.mkdir()
        self.link(outside, installer._backup_parent(self.target("claude")), directory=True)
        with self.assertRaisesRegex(installer.InstallError, "Symlink/reparse"):
            self.run_install(replace=True)
        for agent in ("codex", "claude"):
            self.assertEqual((self.target(agent) / "local.txt").read_text(encoding="utf-8"), "Keep local edit")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(installer._backup_parent(self.target()).exists())


if __name__ == "__main__":
    unittest.main()
