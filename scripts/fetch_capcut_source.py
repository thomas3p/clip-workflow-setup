"""Fetch publisher source for the Claude adapter; does not install/authenticate a Codex plugin.

Usage: python scripts/fetch_capcut_source.py --destination "<private-cache>/CapCut" [--replace]
Only public metadata and source ZIP are fetched. No upstream scripts are executed.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
import zipfile

PUBLISHER_BASE = 'https://sf16-sg.tiktokcdn.com/obj/eden-sg/962370eh7nupenuhbo/capcut_codex_plugin/'
SKILL_URL = PUBLISHER_BASE + 'SKILL.md'
MAX_ZIP_BYTES = 256 * 1024 * 1024


def publisher_url(url, kind):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'sf16-sg.tiktokcdn.com' or parsed.query or parsed.fragment:
        raise ValueError('Source URL is outside the expected HTTPS publisher location')
    if not url.startswith(PUBLISHER_BASE):
        raise ValueError('Unexpected publisher source path')
    name = url[len(PUBLISHER_BASE):]
    pattern = r'SKILL\.md' if kind == 'metadata' else r'plugins_v[0-9A-Za-z._-]+\.zip'
    if not re.fullmatch(pattern, name):
        raise ValueError('Unexpected publisher source filename')
    return url


class PublisherRedirect(HTTPRedirectHandler):
    def __init__(self, kind):
        self.kind = kind

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        publisher_url(newurl, self.kind)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, limit, kind):
    publisher_url(url, kind)
    request = Request(url, headers={'User-Agent': 'clip-workflow-source-fetch/1.0'})
    with build_opener(PublisherRedirect(kind)).open(request, timeout=60) as response:
        publisher_url(response.geturl(), kind)
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Publisher download exceeds the configured size limit')
    return data


def source_metadata(text):
    frontmatter = re.match(r'\A(?:\ufeff)?---\s*\n(.*?)\n---(?:\s|$)', text, re.S)
    if not frontmatter:
        raise ValueError('Publisher metadata frontmatter is missing')
    version = re.search(r'^\s+plugin-version:\s*[\"\x27]?([0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?)[\"\x27]?\s*$',
                        frontmatter.group(1), re.M)
    urls = set(re.findall(r'https://[^\s<>`\"\x27)]+\.zip', text))
    candidates = [url for url in urls if url.startswith(PUBLISHER_BASE)]
    if not version or len(candidates) != 1:
        raise ValueError('Expected one plugin semantic version and one publisher bundle URL')
    return version.group(1), publisher_url(candidates[0], 'bundle')


def safe_extract(archive_path, destination):
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > 5000 or sum(m.file_size for m in members) > 512 * 1024 * 1024:
            raise ValueError('Source archive exceeds extraction limits')
        seen = set()
        for entry in members:
            name = entry.filename.replace('\\', '/')
            parts = name.rstrip('/').split('/')
            if not name or name.startswith('/') or any(p in ('', '.', '..') or ':' in p or p.endswith((' ', '.')) for p in parts):
                raise ValueError('Unsafe archive member path')
            identity = '/'.join(parts).casefold()
            if identity in seen:
                raise ValueError('Duplicate archive member path')
            seen.add(identity)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('Archive links or special files are not supported')
        archive.extractall(destination)


def bundle_version(root):
    root = Path(root)
    marketplace = json.loads((root / '.agents/plugins/marketplace.json').read_text('utf-8-sig'))
    manifest = json.loads((root / 'codex/.codex-plugin/plugin.json').read_text('utf-8-sig'))
    if marketplace.get('name') != 'CapCut' or manifest.get('name') != 'CapCut':
        raise ValueError('Source is not the expected CapCut marketplace/plugin')
    return manifest.get('version')


def fetch_source(destination, replace=False):
    destination = Path(destination).expanduser().absolute()
    if destination.is_symlink():
        raise ValueError('Destination must not be a symlink')
    version, bundle_url = source_metadata(download(SKILL_URL, 2 * 1024 * 1024, 'metadata').decode('utf-8-sig'))
    if destination.exists():
        try:
            existing_version = bundle_version(destination)
        except (OSError, ValueError, TypeError):
            existing_version = None
        if existing_version == version:
            return {'version': version, 'path': str(destination), 'status': 'unchanged'}
        if not replace:
            raise ValueError('Destination differs from the current publisher version; use --replace to retain a backup and replace it')
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix='.capcut-source-', dir=destination.parent) as temp:
        temp = Path(temp)
        zip_path = temp / 'bundle.zip'
        zip_path.write_bytes(download(bundle_url, MAX_ZIP_BYTES, 'bundle'))
        extracted = temp / 'extracted'
        extracted.mkdir()
        safe_extract(zip_path, extracted)
        roots = [p.parents[2] for p in extracted.rglob('marketplace.json')
                 if p.parent.name == 'plugins' and p.parent.parent.name == '.agents']
        if len(roots) != 1 or bundle_version(roots[0]) != version:
            raise ValueError('Bundle root/version does not match publisher metadata')
        staged = temp / 'ready'
        shutil.copytree(roots[0], staged)
        if destination.exists():
            backup = destination.with_name('.' + destination.name + '.backup-' + uuid.uuid4().hex)
            destination.rename(backup)
        try:
            staged.rename(destination)
        except BaseException:
            if backup is not None and not destination.exists():
                backup.rename(destination)
            raise
    result = {'version': version, 'path': str(destination), 'status': 'updated' if backup else 'downloaded'}
    if backup:
        result['backup'] = str(backup)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--destination', required=True, help='Explicit private source-cache directory, outside skill discovery')
    parser.add_argument('--replace', action='store_true', help='Replace a different version after downloading/validating; retain a unique sibling backup')
    args = parser.parse_args()
    try:
        result = fetch_source(args.destination, args.replace)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(1, 'CapCut source fetch failed: ' + str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
