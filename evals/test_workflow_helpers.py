"""Offline regression checks; synthetic files only, never the user's real CapCut drafts.

Run: python -m unittest discover -s evals -p 'test_*.py' -v
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='clip-workflow-test-')
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def setup_run(self, answers, workspace, *extra):
        answer_file = self.base / 'answers.json'
        answer_file.write_text(json.dumps(answers, ensure_ascii=False), encoding='utf-8-sig')
        return subprocess.run([sys.executable, str(SCRIPTS / 'setup_workspace.py'), '--answers', str(answer_file),
                               '--root', str(workspace), *extra], capture_output=True, encoding='utf-8')

    def test_setup_mcp_preserves_unicode_and_yaml_description(self):
        ws = self.base / 'ร้าน demo'
        brand = 'ร้าน "ตัวอย่าง": ของอร่อย'
        result = self.setup_run({'brand': brand, 'slug': 'demo', 'mode': 'mcp',
                                 'products': [{'id': 'p1', 'name': 'สินค้า'}]}, ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        meta = json.loads((ws / 'clip-workspace.json').read_text('utf-8'))
        self.assertEqual(meta['brand'], brand)
        self.assertEqual(meta['mode'], 'mcp')
        skill = (ws / 'brand-skill/demo-clips/SKILL.md').read_text('utf-8')
        description = next(line.split(': ', 1)[1] for line in skill.splitlines() if line.startswith('description: '))
        self.assertIn(brand, json.loads(description))
        self.assertNotIn('{{', skill)
        self.assertIn('Codex', skill)
        self.assertIn('Claude Code', skill)

    def test_repeat_setup_preserves_manual_edits_and_force_keeps_each_backup(self):
        ws = self.base / 'workspace'
        answers = {'brand': 'Example', 'slug': 'example'}
        self.assertEqual(self.setup_run(answers, ws).returncode, 0)
        products = ws / 'brand/products.md'
        products.write_text('manual edit one', 'utf-8')
        self.assertEqual(self.setup_run(answers, ws).returncode, 0)
        self.assertEqual(products.read_text('utf-8'), 'manual edit one')
        self.assertEqual(self.setup_run(answers, ws, '--force').returncode, 0)
        products.write_text('manual edit two', 'utf-8')
        self.assertEqual(self.setup_run(answers, ws, '--force').returncode, 0)
        backups = [p.read_text('utf-8') for p in products.parent.glob('products.md.*.bak')]
        self.assertCountEqual(backups, ['manual edit one', 'manual edit two'])

    def test_general_tutorial_needs_no_products_or_sales_cta(self):
        ws = self.base / 'tutorial'
        result = self.setup_run({'brand': 'Tutorial Channel', 'slug': 'tutorial', 'content_type': 'general'}, ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        meta = json.loads((ws / 'clip-workspace.json').read_text('utf-8'))
        self.assertEqual(meta['source_of_truth'], 'brand/content-facts.md')
        self.assertTrue((ws / meta['source_of_truth']).exists())
        self.assertFalse((ws / 'brand/products.md').exists())
        self.assertNotIn('กดตะกร้าเลย', (ws / 'brand/style-guide.md').read_text('utf-8'))

    def test_invalid_input_has_no_workspace_side_effect(self):
        for bad in ({'brand': 'Example', 'slug': '../escape'},
                    {'brand': 'Example', 'slug': 'example', 'products': [{'id': 'p'}, {'id': 'p'}]},
                    {'brand': 'Example', 'slug': 'example', 'platforms': 'TikTok'}):
            ws = self.base / 'not-created'
            self.assertNotEqual(self.setup_run(bad, ws).returncode, 0)
            self.assertFalse(ws.exists())

    def project_fixture(self):
        project = self.base / 'drafts' / 'demo'
        active = project / 'Timelines' / 'timeline-1'
        active.mkdir(parents=True)
        asset = self.base / 'asset.mp4'
        asset.write_bytes(b'fixture: not decoded by this metadata-only checker')
        doc = {'duration': 1_000_000, 'materials': {'videos': [
            {'id': 'video-1', 'path': str(asset), 'duration': 1_000_000, 'type': 'video'}]},
            'tracks': [{'type': 'video', 'segments': [{'id': 'segment-1', 'material_id': 'video-1',
                'target_timerange': {'start': 0, 'duration': 1_000_000},
                'source_timerange': {'start': 0, 'duration': 1_000_000}}]}]}
        for file in (project / 'draft_content.json', active / 'draft_content.json'):
            file.write_text(json.dumps(doc), 'utf-8')
        (project / 'Timelines/project.json').write_text(json.dumps({'main_timeline_id': 'timeline-1',
            'timelines': [{'id': 'timeline-1', 'name': 'Main'}]}), 'utf-8')
        return project, doc

    def test_inspector_finds_missing_refs_and_root_active_divergence(self):
        mod = load('capcut_inspect')
        project, doc = self.project_fixture()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mod.check('Main', project / 'draft_content.json'), 0)
            self.assertEqual(mod.root_active_check(project), 0)
            doc['tracks'][0]['segments'][0]['extra_material_refs'] = ['missing-effect']
            (project / 'draft_content.json').write_text(json.dumps(doc), 'utf-8')
            self.assertGreater(mod.check('Main', project / 'draft_content.json'), 0)
            self.assertEqual(mod.root_active_check(project), 1)

    def test_inspector_returns_nonzero_on_invalid_draft(self):
        project, doc = self.project_fixture()
        doc['materials']['videos'][0]['path'] = str(self.base / 'missing.mp4')
        for file in (project / 'draft_content.json', project / 'Timelines/timeline-1/draft_content.json'):
            file.write_text(json.dumps(doc), 'utf-8')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'capcut_inspect.py'), str(project),
                                 '--root', str(project.parent)], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1)

    def test_backup_cannot_recurse_into_source_and_never_overwrites(self):
        mod = load('capcut_backup')
        project, _ = self.project_fixture()
        def run(destination):
            with patch.object(sys, 'argv', ['capcut_backup.py', str(project), '--root', str(project.parent),
                                           '--to', str(destination)]), patch.object(mod, 'capcut_running', return_value=False), \
                 contextlib.redirect_stdout(io.StringIO()):
                mod.main()
        with self.assertRaises(SystemExit):
            run(project / 'recursive-backup')
        self.assertFalse((project / 'recursive-backup').exists())
        destination = self.base / 'backups'
        run(destination)
        run(destination)
        self.assertEqual(len(list(destination.iterdir())), 2)
        for backup in destination.iterdir():
            self.assertEqual((backup / 'draft_content.json').read_bytes(), (project / 'draft_content.json').read_bytes())

    def test_failed_process_check_is_not_reported_as_closed(self):
        mod = load('capcut_backup')
        with patch.object(mod.platform, 'system', return_value='Windows'), \
             patch.object(mod.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'tasklist')):
            with self.assertRaises(subprocess.CalledProcessError):
                mod.capcut_running()


if __name__ == '__main__':
    unittest.main()
