#!/usr/bin/env python3
"""Adapt a locally obtained official CapCut bundle for project-scoped Claude Code.

This creates local skill wrappers and HTTP MCP configuration. It never executes
OAuth, copies account credentials, or proves that the remote server accepts Claude.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ENDPOINTS = {
    "capcut_creation": "https://www.capcut.com/api/external_mcp",
    "capcut_creation_resource": "https://www.capcut.com/api/external_mcp/resource",
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
SKILLS = {
    "capcut-stdraft-builder": "capcut-stdraft-builder",
    "capcut-upload": "capcut-upload",
    "video-editing": "capcut-video-editing",
    "web-collaborative-editing": "capcut-web-collaborative-editing",
}
SOURCE_FOLDERS = {"reference", "references", "scripts", "assets"}
EXCLUDED = {"vendor", "evals", "tests", "__pycache__", ".git", "mcp-auth"}
SENSITIVE = {"auth.json", "credentials.json", "credentials.toml", "credentials.yaml", "credentials.yml", "cookies.json", "cookies.txt", "tokens.json", "token.json", "id_rsa", "id_ed25519", ".credentials"}


class AdapterError(Exception):
    pass


@dataclass
class Change:
    path: Path
    content: dict[str, bytes] | bytes
    before: dict[str, bytes] | bytes | None
    stage: Path | None = None
    backup: Path | None = None
    applied: bool = False


def absolute(value: Path | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(value))))


def info(path: Path):
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def safe(path: Path) -> None:
    for item in reversed((path, *path.parents)):
        found = info(item)
        if found is None:
            continue
        if stat.S_ISLNK(found.st_mode) or getattr(found, "st_file_attributes", 0) & 0x400:
            raise AdapterError(f"Symlink/reparse point is not allowed: {item}")
        if item != path and not stat.S_ISDIR(found.st_mode):
            raise AdapterError(f"Parent is not a directory: {item}")


def name_ok(name: str) -> None:
    if (
        not name or name in {".", ".."} or name[-1] in {".", " "}
        or any(ord(c) < 32 or ord(c) == 127 or c in '<>:"/\\|?*' for c in name)
        or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.I)
    ):
        raise AdapterError(f"Unsafe payload name: {name!r}")


def overlap(left: Path, right: Path) -> bool:
    try:
        common = os.path.normcase(os.path.commonpath((left, right)))
    except ValueError:
        return False
    return common in {os.path.normcase(str(left)), os.path.normcase(str(right))}


def json_read(raw: bytes, label: str) -> dict:
    def pairs(values):
        output = {}
        for key, value in values:
            if key in output:
                raise AdapterError(f"Duplicate JSON key in {label}: {key}")
            output[key] = value
        return output

    def invalid_number(value):
        raise AdapterError(f"Non-JSON numeric constant in {label}")

    try:
        parsed = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=invalid_number)
    except (ValueError, UnicodeError) as error:
        raise AdapterError(f"Invalid JSON in {label}") from error
    if not isinstance(parsed, dict):
        raise AdapterError(f"Expected a JSON object in {label}")
    return parsed


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def regular_bytes(path: Path) -> bytes:
    safe(path)
    found = info(path)
    if found is None or not stat.S_ISREG(found.st_mode):
        raise AdapterError(f"Required regular file is missing: {path}")
    return path.read_bytes()


def tree(path: Path, *, upstream: bool = False) -> dict[str, bytes]:
    safe(path)
    if not path.is_dir():
        raise AdapterError(f"Expected a regular directory: {path}")
    output = {}

    def visit(entry: Path):
        name_ok(entry.name)
        safe(entry)
        found = info(entry)
        if found is None:
            raise AdapterError(f"Payload changed during inspection: {entry}")
        if upstream:
            lowered = entry.name.lower()
            if lowered in SENSITIVE or lowered == ".env" or lowered.startswith(".env."):
                raise AdapterError(f"Credential-like file is forbidden in the adapted payload: {entry}")
            if stat.S_ISDIR(found.st_mode) and lowered in EXCLUDED:
                return
        if stat.S_ISDIR(found.st_mode):
            for child in sorted(entry.iterdir(), key=lambda p: p.name):
                visit(child)
        elif stat.S_ISREG(found.st_mode):
            output[entry.relative_to(path).as_posix()] = entry.read_bytes()
        else:
            raise AdapterError(f"Special files are not supported: {entry}")

    for child in sorted(path.iterdir(), key=lambda p: p.name):
        if not upstream or child.name == "SKILL.md" or child.name in SOURCE_FOLDERS:
            visit(child)
    return output


HOST_GUIDE = """# Claude Code host adaptation

This wrapper adapts locally obtained CapCut reference files. It is not an official
Claude CapCut plugin. Apply these host substitutions whenever original references
mention Codex; do not execute their Codex setup/authentication/browser commands.

- Discover tools by their exact suffix and inspect the current schema. Do not
  assume a Codex namespace or infer connection from a configuration file.
- Ask the user to trust this project and approve `.mcp.json`, then run `/mcp` in
  Claude Code and authenticate `capcut_creation` using Claude's native browser
  OAuth flow. Never run `codex`, `capcut-login.mjs`, or the original `mcp-auth`.
  Never authenticate `capcut_creation_resource`; it is the identity-free renderer.
  A failed/misconfigured OAuth flow is a blocker, not permission to copy tokens.
- A safe protected read check is `search_capcut_material` with type `font`,
  prompt `font`, top_n 1. Only a successful real tool response verifies protected
  access. It verifies neither rendering nor upload/save/export.
- Use Claude's actual shell/file tools for local Python/Node operations; never
  pass Codex-only `sandbox_permissions`, `tty`, session APIs or approval flags to
  a tool that does not support them. Respect the current host's permissions.
- For scripts, SKILL_ROOT means this wrapper's `references/original` directory.
  Internal upstream script imports and file paths are preserved byte-for-byte.
  Resolve sibling skill references using the installed wrappers below, rather
  than following original `../../<skill>` paths from their relocated files:
  `capcut-stdraft-builder`, `capcut-upload`, `capcut-video-editing` (original
  `video-editing`), `capcut-web-collaborative-editing` (original
  `web-collaborative-editing`). Load the sibling wrapper's SKILL.md first.
- No template-search, media-generation or mcp-auth skill is installed. Those
  original cross-links do not authorize an unsupported workflow.
- MCP Apps, CapCut cards, `window.openai`, and Codex's embedded browser are host
  integrations, not generic text. If a required card renderer/native bridge is
  unavailable, stop that card-dependent operation and report the exact missing
  capability. Never fabricate a card response or replace mandatory billing/UI
  confirmation with an assumed approval. Do not start new paid generation.
- For cloud-draft links, return the exact `web_editor_url` with the server's
  `web_editor_text` after a successful save. If a real compatible browser tool
  exists, open/reuse the exact returned URL there; otherwise give the link and
  say live visual inspection remains unverified. Do not invent embed/browser
  session state or claim to inspect a preview that Claude cannot observe.
- Preserve session/version checks, source URLs, caption routing, conflict rules,
  result schemas and upload security from the original references. A local
  STDraft is a cloud interchange document, not CapCut PC draft_content.json.
  Do not claim native CapCut PC control or a completed export.
"""

SPECIFIC = {
    "capcut-stdraft-builder": (
        "Edit and validate complete CapCut STDraft documents locally using the bundled Python atomic functions.",
        "Read `references/original/SKILL.md` and `reference/application.md` under that original root. "
        "Use Python 3 with -B; add that root's scripts directory to sys.path in the caller before "
        "importing apply_materials, apply_captions or manage_materials. These functions need no "
        "MCP/OAuth and no third-party package installation. Return and inspect the validated draft; "
        "cloud saving is a separate capability. Do not execute untrusted Python from a draft.",
    ),
    "capcut-upload": (
        "Upload selected local media through available CapCut MCP tools and the original Node uploader when safe stdin is supported.",
        "Read `references/original/SKILL.md` and its `references/codex-local.md` with the host substitutions. "
        "Request version 2 upload authorization only for an authorized batch. Node.js 14+ is required. "
        "The upload_ticket is a short-lived bearer capability: never put it in shell arguments, a heredoc, "
        "environment variables, logs or a temporary file. The upstream uploader requires a live protected "
        "TTY/stdin channel. If this Claude host has no such channel, stop before requesting a ticket; "
        "explain that the local-upload step needs a compatible secure process bridge. Reuse an already "
        "uploaded VID/workspace resource, or let the user upload in CapCut and identify it. Do not ask "
        "the user to paste tickets or account credentials. A local uploader/finalize failure is not "
        "evidence of MCP OAuth failure and must not trigger login.",
    ),
    "video-editing": (
        "Route CapCut rough cuts, automatic captions and post-editing through available Claude MCP capabilities.",
        "Read `references/original/SKILL.md`, then only the relevant original reference. Caption-only "
        "requests use auto_caption_submit/query and local application, never AI Lab. Discover required "
        "remote tools before starting. For rough cuts, first confirm that all required plan/result "
        "renderers are available in this Claude host; if not, stop before creating the task and report "
        "the missing UI capability. Do not imitate required native cards with invented actions. "
        "Use the wrapped local builder for prepared captions/materials and the wrapped cloud-session "
        "workflow to check, save and preserve conflicts. Recognition alone is not applied subtitles.",
    ),
    "web-collaborative-editing": (
        "Coordinate CapCut cloud STDraft sessions, version checks and saves from Claude Code tools.",
        "Read `references/original/SKILL.md` and its conflict-recovery reference. Discover "
        "start_stdraft_session, check_stdraft_state, get_stdraft_snapshot and push_stdraft_snapshot "
        "by exact suffix; create a session only for an authorized editing task. Session IDs and AI Lab "
        "task IDs are different. Check immediately before editing, use the latest baseline, preserve "
        "the user's cloud changes and never overwrite a version conflict. Return the saved editor link "
        "even when Claude has no embedded browser. State that missing preview/visual verification "
        "separately; do not treat a link as proof of preview inspection or export.",
    ),
}


def wrapper_payload(source: Path, upstream: str, version: str) -> dict[str, bytes]:
    original = tree(source / "skills" / upstream, upstream=True)
    if not original.get("SKILL.md"):
        raise AdapterError(f"Required original SKILL.md is missing: {upstream}")
    name = SKILLS[upstream]
    description, instructions = SPECIFIC[upstream]
    wrapper = (
        f"---\nname: {name}\ndescription: {description}\n---\n\n"
        f"# CapCut / Claude Code: {upstream}\n\n"
        "Read and apply [Claude host adaptation](references/host-adaptation.md) first. "
        "It supplies the Claude-specific replacements for the original host procedures.\n\n"
        f"{instructions}\n\n"
        "The original files are local third-party references, preserved under "
        "[references/original/SKILL.md](references/original/SKILL.md). Their original "
        "license remains unchanged; do not publish those copied files as part of this workflow repo.\n"
    )
    payload = {f"references/original/{key}": value for key, value in original.items()}
    payload["SKILL.md"] = wrapper.encode("utf-8")
    payload["references/host-adaptation.md"] = HOST_GUIDE.encode("utf-8")
    payload["adapter-manifest.json"] = json_bytes({
        "adapter": "clip-workflow-setup/claude-capcut-v1",
        "upstream_skill": upstream,
        "upstream_version": version,
        "original_files_sha256": {key: hashlib.sha256(value).hexdigest() for key, value in original.items()},
        "authentication_verified": False,
        "host_cards_verified": False,
    })
    return payload


def converted_servers(source: Path) -> dict:
    config = json_read(regular_bytes(source / ".mcp.json"), "official CapCut .mcp.json")
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != set(ENDPOINTS):
        raise AdapterError("Official source must contain exactly the two supported CapCut servers")
    output = {}
    for name, url in ENDPOINTS.items():
        entry = servers[name]
        if not isinstance(entry, dict) or entry.get("url") != url or entry.get("oauth_resource", url) != url:
            raise AdapterError(f"Unsupported CapCut endpoint/resource for {name}; canonical HTTPS endpoint required")
        incoming = entry.get("http_headers", {})
        if not isinstance(incoming, dict):
            raise AdapterError(f"Invalid source headers for {name}")
        allowed = {key.lower(): value for key, value in HEADERS.items()}
        for key, value in incoming.items():
            if key.lower() not in allowed or value != allowed[key.lower()]:
                raise AdapterError(f"Unsupported source header for {name}; no credentials or custom routing are copied")
        if any(key in entry for key in ("headers", "headersHelper", "env", "command", "args", "oauth", "token", "api_key")):
            raise AdapterError(f"Unexpected authentication/launch fields in official server {name}")
        output[name] = {"type": "http", "url": url, "headers": dict(HEADERS)}
    return output


def current(change: Change):
    safe(change.path)
    if info(change.path) is None:
        return None
    return tree(change.path) if isinstance(change.content, dict) else regular_bytes(change.path)


def cleanup_stage(change: Change) -> None:
    stage = change.stage
    if stage is None or info(stage) is None:
        return
    if stage.parent != change.path.parent or not stage.name.startswith(".capcut-claude-stage-"):
        raise AdapterError(f"Refusing to clean an unowned stage: {stage}")
    safe(stage)
    if stage.is_dir():
        shutil.rmtree(stage)
    else:
        stage.unlink()


def apply(changes: list[Change], backup_root: Path) -> None:
    prepared = []
    rollback_incomplete = False
    try:
        for change in changes:
            safe(change.path)
            change.path.parent.mkdir(parents=True, exist_ok=True)
            safe(change.path)
            if isinstance(change.content, dict):
                change.stage = Path(tempfile.mkdtemp(prefix=".capcut-claude-stage-", dir=change.path.parent))
                prepared.append(change)
                for key, value in change.content.items():
                    target = change.stage / key
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as stream:
                        stream.write(value)
                if tree(change.stage) != change.content:
                    raise AdapterError("Staged skill did not match its payload")
            else:
                descriptor, tempname = tempfile.mkstemp(prefix=".capcut-claude-stage-", dir=change.path.parent)
                change.stage = Path(tempname)
                prepared.append(change)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(change.content)
            if current(change) != change.before:
                raise AdapterError(f"Destination changed after preflight: {change.path}")
        if any(current(change) != change.before for change in changes):
            raise AdapterError("A destination changed after preflight; no changes were committed")
        for change in changes:
            if change.before is not None:
                safe(backup_root)
                backup_root.mkdir(parents=True, exist_ok=True)
                safe(backup_root)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                change.backup = backup_root / f"{change.path.name}-{stamp}-{uuid.uuid4().hex}"
                change.path.rename(change.backup)
            change.stage.rename(change.path)
            change.applied = True
    except (OSError, AdapterError) as error:
        rollback_errors = []
        # Include a current item whose original was moved but new install failed.
        for change in reversed(prepared):
            try:
                if change.applied:
                    safe(change.path)
                    change.path.rename(change.stage)
                if change.backup is not None and info(change.backup) is not None:
                    change.backup.rename(change.path)
                change.applied = False
            except OSError as rollback_error:
                rollback_errors.append(f"{change.path}: {rollback_error}")
        if rollback_errors:
            rollback_incomplete = True
            raise AdapterError("Rollback incomplete; preserve reported backup/stage files: " + "; ".join(rollback_errors)) from error
        raise AdapterError(f"Adaptation stopped; original destinations preserved: {error}") from error
    finally:
        # If rollback failed, preserve every stage for recovery rather than delete.
        if not rollback_incomplete:
            for change in prepared:
                cleanup_stage(change)


def adapt(source: Path | str, project: Path | str, *, replace: bool = False, dry_run: bool = False) -> list[str]:
    source, project = absolute(source), absolute(project)
    safe(source)
    safe(project)
    plugin = source / "codex" if (source / "codex").is_dir() else source
    safe(plugin)
    if overlap(source, project):
        raise AdapterError("Official source and target project must not overlap")
    metadata = json_read(regular_bytes(plugin / ".codex-plugin/plugin.json"), "official plugin manifest")
    if metadata.get("name") != "CapCut" or not isinstance(metadata.get("version"), str):
        raise AdapterError("Source is not a versioned official CapCut bundle")
    servers = converted_servers(plugin)
    skills_root = project / ".claude/skills"
    backup_root = project / ".claude/skill-backups"
    safe(backup_root)
    found = info(backup_root)
    if found is not None and not stat.S_ISDIR(found.st_mode):
        raise AdapterError(f"Backup parent is not a directory: {backup_root}")
    changes: list[Change] = []
    output = []
    for upstream, name in SKILLS.items():
        payload = wrapper_payload(plugin, upstream, metadata["version"])
        change = Change(skills_root / name, payload, None)
        change.before = current(change)
        if change.before == payload:
            output.append(f"unchanged: {change.path}")
        elif change.before is not None and not replace:
            raise AdapterError(f"Different skill exists: {change.path}; use --replace to preserve a backup")
        else:
            changes.append(change)
            output.append(f"{'replace' if change.before is not None else 'install'}: {change.path}")
    mcp_path = project / ".mcp.json"
    safe(mcp_path)
    before = None if info(mcp_path) is None else regular_bytes(mcp_path)
    config = {} if before is None else json_read(before, "project .mcp.json")
    existing = config.setdefault("mcpServers", {})
    if not isinstance(existing, dict):
        raise AdapterError("Project .mcp.json mcpServers must be an object")
    needs_config = False
    for name, entry in servers.items():
        if name in existing and existing[name] != entry and not replace:
            raise AdapterError(f"Conflicting project server {name}; use --replace to preserve a backup")
        if existing.get(name) != entry:
            existing[name] = entry
            needs_config = True
    if needs_config:
        changes.append(Change(mcp_path, json_bytes(config), before))
        output.append(f"{'replace' if before is not None else 'install'}: {mcp_path}")
    else:
        output.append(f"unchanged: {mcp_path}")
    if dry_run:
        return ["dry-run: " + line for line in output]
    if changes:
        apply(changes, backup_root)
        output.extend(f"backup: {change.backup}" for change in changes if change.backup is not None)
    output.append("Configured locally; OAuth, server access, upload, cards, preview and export remain unverified.")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Locally obtained official CapCut marketplace or codex plugin folder")
    parser.add_argument("--project", required=True, type=Path, help="Target Claude Code project; never edits user-global config")
    parser.add_argument("--scope", choices=("project",), default="project")
    parser.add_argument("--replace", action="store_true", help="Back up and replace conflicting adapter skills/CapCut server entries")
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args(argv)
    try:
        for line in adapt(options.source, options.project, replace=options.replace, dry_run=options.dry_run):
            print(line)
    except (OSError, AdapterError) as error:
        print(f"Claude adaptation stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
