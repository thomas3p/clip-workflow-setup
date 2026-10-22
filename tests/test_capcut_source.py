"""Offline source-fetch tests; no live network, OAuth or user cache writes."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fetch_capcut_source', ROOT / 'scripts/fetch_capcut_source.py')
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


def metadata(version='0.2.5', filename='plugins_v25.zip'):
    return ('---\nname: capcut-install\nmetadata:\n  plugin-version: "' + version + '"\n---\n'
            + fetch.PUBLISHER_BASE + filename + '\n').encode()


def bundle(version='0.2.5', wrapper='plugins/', extra=None):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w') as archive:
        archive.writestr(wrapper + '.agents/plugins/marketplace.json', json.dumps({'name': 'CapCut'}))
        archive.writestr(wrapper + 'codex/.codex-plugin/plugin.json', json.dumps({'name': 'CapCut', 'version': version}))
        archive.writestr(wrapper + 'codex/skills/mcp-auth/SKILL.md', 'source only')
        if extra:
            archive.writestr(*extra)
    return result.getvalue()


class SourceFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='capcut-source-test-')
        self.destination = Path(self.temp.name) / 'private-cache' / 'CapCut'

    def tearDown(self):
        self.temp.cleanup()

    def run_fetch(self, *responses, replace=False):
        with patch.object(fetch, 'download', side_effect=responses) as mocked:
            result = fetch.fetch_source(self.destination, replace=replace)
            return result, mocked

    def test_current_metadata_and_exact_bundle_url(self):
        version, url = fetch.source_metadata(metadata().decode())
        self.assertEqual(version, '0.2.5')
        self.assertEqual(url, fetch.PUBLISHER_BASE + 'plugins_v25.zip')
        for url in ('http://sf16-sg.tiktokcdn.com/a.zip', fetch.PUBLISHER_BASE + '../plugins_v25.zip',
                    fetch.PUBLISHER_BASE + 'plugins_v25.zip?token=bad', 'https://example.com/plugins_v25.zip'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch.publisher_url(url, 'bundle')

    def test_download_and_wrapper_root_discovery(self):
        result, mocked = self.run_fetch(metadata(), bundle(wrapper='wrapper/nested/plugins/'))
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(fetch.bundle_version(self.destination), '0.2.5')
        self.assertTrue((self.destination / 'codex/skills/mcp-auth/SKILL.md').is_file())
        self.assertFalse((self.destination / 'SKILL.md').exists())
        self.assertEqual(mocked.call_args_list[1].args[0], fetch.PUBLISHER_BASE + 'plugins_v25.zip')

    def test_redirect_is_rejected_before_following_an_external_host(self):
        handler = fetch.PublisherRedirect('metadata')
        request = fetch.Request(fetch.SKILL_URL)
        with self.assertRaises(ValueError):
            handler.redirect_request(request, None, 302, 'Found', {}, 'https://example.com/SKILL.md')
        with self.assertRaises(ValueError):
            handler.redirect_request(request, None, 302, 'Found', {}, fetch.SKILL_URL.replace('https:', 'http:'))

    def test_same_version_is_unchanged_without_bundle_download(self):
        self.run_fetch(metadata(), bundle())
        marker = self.destination / 'local-marker'
        marker.write_text('preserve', 'utf-8')
        result, mocked = self.run_fetch(metadata())
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(marker.read_text('utf-8'), 'preserve')

    def test_different_version_refuses_without_replace(self):
        self.run_fetch(metadata(), bundle())
        before = (self.destination / 'codex/.codex-plugin/plugin.json').read_bytes()
        with patch.object(fetch, 'download', side_effect=[metadata('0.2.6', 'plugins_v26.zip')]) as mocked:
            with self.assertRaisesRegex(ValueError, '--replace'):
                fetch.fetch_source(self.destination)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual((self.destination / 'codex/.codex-plugin/plugin.json').read_bytes(), before)

    def test_failed_download_preserves_existing_version(self):
        self.run_fetch(metadata(), bundle())
        with patch.object(fetch, 'download', side_effect=[metadata('0.2.6', 'plugins_v26.zip'), OSError('download failed')]):
            with self.assertRaises(OSError):
                fetch.fetch_source(self.destination, replace=True)
        self.assertEqual(fetch.bundle_version(self.destination), '0.2.5')
        self.assertEqual(list(self.destination.parent.glob('.CapCut.backup-*')), [])

    def test_replace_retains_unique_backup(self):
        self.run_fetch(metadata(), bundle())
        result, _ = self.run_fetch(metadata('0.2.6', 'plugins_v26.zip'), bundle('0.2.6'), replace=True)
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(fetch.bundle_version(self.destination), '0.2.6')
        backup = Path(result['backup'])
        self.assertEqual(backup.parent, self.destination.parent)
        self.assertEqual(fetch.bundle_version(backup), '0.2.5')

    def test_version_mismatch_preserves_existing_destination(self):
        self.run_fetch(metadata(), bundle())
        with patch.object(fetch, 'download', side_effect=[metadata('0.2.6', 'plugins_v26.zip'), bundle('9.0.0')]):
            with self.assertRaisesRegex(ValueError, 'root/version'):
                fetch.fetch_source(self.destination, replace=True)
        self.assertEqual(fetch.bundle_version(self.destination), '0.2.5')

    def test_traversal_absolute_backslash_and_symlinks_are_rejected(self):
        symlink = zipfile.ZipInfo('plugins/evil-link')
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        for extra in (('../escape.txt', 'bad'), ('/absolute.txt', 'bad'),
                      ('C:/escape.txt', 'bad'), ('..\\escape.txt', 'bad'), (symlink, '../escape.txt')):
            with self.subTest(member=str(extra[0])):
                with patch.object(fetch, 'download', side_effect=[metadata(), bundle(extra=extra)]):
                    with self.assertRaises(ValueError):
                        fetch.fetch_source(self.destination)
                self.assertFalse(self.destination.exists())
                self.assertFalse((Path(self.temp.name) / 'escape.txt').exists())


if __name__ == '__main__':
    unittest.main()
