"""Check that public packaging cannot accidentally ship the private vendor tree."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_release", ROOT / "package_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class PublicReleaseTests(unittest.TestCase):
    def test_archive_contains_workflow_but_excludes_private_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in release.ROOT_FILES:
                (root / name).write_text("workflow", encoding="utf-8")
            for name in ("vendor/CapCut/codex/plugin.json", "local/account.json", "LOCAL_SETUP_STATUS.json", "answers.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private", encoding="utf-8")
            script = root / "scripts/workflow.py"
            script.parent.mkdir()
            script.write_text("print('workflow')", encoding="utf-8")
            output = root / "dist/release.zip"
            release.build_release(root, output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("clip-workflow-setup/SKILL.md", names)
                self.assertIn("clip-workflow-setup/scripts/workflow.py", names)
                self.assertFalse(any("vendor/" in name or "account.json" in name or "answers.json" in name or "LOCAL_SETUP_STATUS" in name for name in names))
            first = output.read_bytes()
            release.build_release(root, output)
            self.assertEqual(first, output.read_bytes())

    def test_credential_named_file_in_public_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in release.ROOT_FILES:
                (root / name).write_text("workflow", encoding="utf-8")
            directory = root / "references"
            directory.mkdir()
            (directory / "credentials.json").write_text("private", encoding="utf-8")
            with self.assertRaises(ValueError):
                release.public_files(root)


if __name__ == "__main__":
    unittest.main()
