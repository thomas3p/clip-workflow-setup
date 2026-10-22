#!/usr/bin/env python3
"""Install only the portable workflow skill; never configure CapCut or OAuth."""

from __future__ import annotations

import argparse
import hashlib
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
from typing import Iterable


SKILL_NAME = "clip-workflow-setup"
PAYLOAD_DIRS = ("agents", "references", "scripts", "assets")
REQUIRED_FILES = ("SKILL.md",)
EXCLUDED_DIRS = {"vendor", "evals", "tests", "__pycache__", ".git"}
SENSITIVE_NAMES = {
    "auth.json", "credentials.json", "credentials.toml", "credentials.yaml",
    "credentials.yml", "cookies.json", "cookies.txt", "tokens.json",
    "token.json", "id_rsa", "id_ed25519", ".credentials",
}


class InstallError(Exception):
    """A safe, user-readable refusal or installation failure."""


@dataclass(frozen=True)
class Snapshot:
    directories: tuple[str, ...]
    files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Plan:
    destination: Path
    previous: Snapshot | None
    action: str


@dataclass(frozen=True)
class Result:
    destination: Path
    action: str
    backup: Path | None = None


def absolute(path: Path | str) -> Path:
    # Do not resolve(): it would hide symlink or junction components.
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _is_link(info: os.stat_result) -> bool:
    # Reparse points include Windows directory junctions, even on Python 3.10.
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def assert_safe_ancestors(path: Path) -> None:
    for item in reversed((path, *path.parents)):
        info = _lstat(item)
        if info is None:
            continue
        if _is_link(info):
            raise InstallError(f"Symlink/reparse point is not allowed: {item}")
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise InstallError(f"Parent is not a directory: {item}")


def _validate_name(name: str) -> None:
    if (
        not name or name in {".", ".."} or name[-1] in {".", " "}
        or any(ord(ch) < 32 or ord(ch) == 127 or ch in '<>:"/\\|?*' for ch in name)
        or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name, re.I)
    ):
        raise InstallError(f"Unsafe or non-portable payload name: {name!r}")


def _secret_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in SENSITIVE_NAMES or lowered == ".env" or lowered.startswith(".env.")


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _scan(root: Path, entries: Iterable[Path], *, payload: bool) -> Snapshot:
    directories: list[str] = []
    files: list[tuple[str, str]] = []

    def visit(path: Path) -> None:
        _validate_name(path.name)
        info = _lstat(path)
        if info is None:
            raise InstallError(f"File changed or disappeared during inspection: {path}")
        if _is_link(info):
            raise InstallError(f"Symlink/reparse point is not allowed: {path}")
        if payload and _secret_name(path.name):
            raise InstallError(f"Credential-like file is not part of a workflow payload: {path}")
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            if payload and path.name.lower() in EXCLUDED_DIRS:
                return
            directories.append(relative)
            for child in sorted(path.iterdir(), key=lambda item: item.name):
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            files.append((relative, _digest(path)))
        else:
            raise InstallError(f"Only regular files and directories are supported: {path}")

    for entry in entries:
        visit(entry)
    return Snapshot(tuple(sorted(directories)), tuple(sorted(files)))


def payload_snapshot(source: Path) -> Snapshot:
    assert_safe_ancestors(source)
    if not source.is_dir():
        raise InstallError(f"Workflow source is not a directory: {source}")
    entries: list[Path] = []
    for filename in REQUIRED_FILES:
        path = source / filename
        info = _lstat(path)
        if info is None or _is_link(info) or not stat.S_ISREG(info.st_mode):
            raise InstallError(f"Required regular payload file is missing: {path}")
        entries.append(path)
    try:
        skill_text = (source / "SKILL.md").read_text(encoding="utf-8-sig")
    except UnicodeError as error:
        raise InstallError("SKILL.md must be UTF-8 text") from error
    frontmatter = re.match(r"\A---\s*\r?\n(.*?)\r?\n---(?:\s*\r?\n|\Z)", skill_text, re.S)
    if frontmatter is None:
        raise InstallError("SKILL.md must have YAML frontmatter")
    metadata = frontmatter.group(1)
    if not re.search(rf"(?m)^name:\s*[\"']?{re.escape(SKILL_NAME)}[\"']?\s*$", metadata):
        raise InstallError(f"SKILL.md must declare name: {SKILL_NAME}")
    if not re.search(r"(?m)^description:\s*\S", metadata):
        raise InstallError("SKILL.md must declare a non-empty description")
    for dirname in PAYLOAD_DIRS:
        path = source / dirname
        info = _lstat(path)
        if info is None:
            continue
        if _is_link(info) or not stat.S_ISDIR(info.st_mode):
            raise InstallError(f"Payload folder must be a regular directory: {path}")
        entries.append(path)
    return _scan(source, entries, payload=True)


def _existing_snapshot(destination: Path) -> Snapshot | None:
    assert_safe_ancestors(destination)
    info = _lstat(destination)
    if info is None:
        return None
    if not stat.S_ISDIR(info.st_mode):
        raise InstallError(f"Destination already exists and is not a directory: {destination}")
    return _scan(destination, destination.iterdir(), payload=False)


def _overlap(first: Path, second: Path) -> bool:
    try:
        common = os.path.normcase(os.path.commonpath((first, second)))
    except ValueError:  # Different Windows drives.
        return False
    return common in {os.path.normcase(str(first)), os.path.normcase(str(second))}


def _backup_parent(destination: Path) -> Path:
    # A backup containing SKILL.md must not remain in a skill-discovery folder.
    return destination.parent.parent / "skill-backups"


def _check_backup_parent(source: Path, destination: Path) -> Path:
    parent = _backup_parent(destination)
    if _overlap(source, parent):
        raise InstallError(f"Source and backup directory must not overlap: {parent}")
    assert_safe_ancestors(parent)
    info = _lstat(parent)
    if info is not None and not stat.S_ISDIR(info.st_mode):
        raise InstallError(f"Backup parent is not a directory: {parent}")
    return parent


def destinations(*, agent: str, home: Path | str | None, project: Path | str | None) -> list[Path]:
    base = absolute(project if project is not None else (home if home is not None else Path.home()))
    names = ("codex", "claude") if agent == "both" else (agent,)
    if any(name not in {"codex", "claude"} for name in names):
        raise InstallError(f"Unknown agent: {agent}")
    return [base / (".agents" if name == "codex" else ".claude") / "skills" / SKILL_NAME for name in names]


def _remove_own_stage(stage: Path, parent: Path) -> None:
    # Existing installations and backups are never recursively deleted.
    if stage.parent != parent or not stage.name.startswith(f".{SKILL_NAME}.stage-"):
        raise InstallError(f"Refusing to clean an unowned staging directory: {stage}")
    if _lstat(stage) is not None:
        assert_safe_ancestors(stage)
        shutil.rmtree(stage)


def _copy_payload(source: Path, stage: Path, snapshot: Snapshot) -> None:
    for dirname in snapshot.directories:
        (stage / dirname).mkdir(parents=True, exist_ok=True)
    for filename, expected_digest in snapshot.files:
        original = source / filename
        assert_safe_ancestors(original)
        if not original.is_file():
            raise InstallError(f"Payload file is no longer a regular file: {original}")
        copied = stage / filename
        copied.parent.mkdir(parents=True, exist_ok=True)
        with original.open("rb") as reader, copied.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
        if _digest(copied) != expected_digest:
            raise InstallError(f"Source payload changed during installation: {original}")
    staged = _scan(stage, stage.iterdir(), payload=False)
    if staged != snapshot:
        raise InstallError("Staged payload did not match the validated source")


def _apply_plan(source: Path, snapshot: Snapshot, plan: Plan) -> Result:
    destination = plan.destination
    if plan.action == "unchanged":
        return Result(destination, "unchanged")
    assert_safe_ancestors(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert_safe_ancestors(destination)
    stage = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}.stage-", dir=destination.parent))
    backup: Path | None = None
    try:
        _copy_payload(source, stage, snapshot)
        if _existing_snapshot(destination) != plan.previous:
            raise InstallError(f"Destination changed after preflight; nothing replaced: {destination}")
        if plan.previous is not None:
            backup_parent = _check_backup_parent(source, destination)
            backup_parent.mkdir(parents=True, exist_ok=True)
            assert_safe_ancestors(backup_parent)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = backup_parent / f"{SKILL_NAME}-{stamp}-{uuid.uuid4().hex}"
            destination.rename(backup)
        try:
            stage.rename(destination)
        except OSError as error:
            if backup is not None:
                try:
                    backup.rename(destination)
                except OSError as rollback_error:
                    raise InstallError(
                        f"Install and rollback failed. Original files remain in {backup}; "
                        f"destination: {destination}. Rollback error: {rollback_error}"
                    ) from error
            raise InstallError(f"Install failed; original destination restored: {destination}: {error}") from error
        return Result(destination, plan.action, backup)
    finally:
        _remove_own_stage(stage, destination.parent)


def install(
    source: Path | str,
    *,
    agent: str = "both",
    home: Path | str | None = None,
    project: Path | str | None = None,
    dry_run: bool = False,
    replace: bool = False,
) -> list[Result]:
    source = absolute(source)
    snapshot = payload_snapshot(source)
    targets = destinations(agent=agent, home=home, project=project)
    plans: list[Plan] = []
    # Validate every target before even creating a parent directory.
    for index, destination in enumerate(targets):
        if _overlap(source, destination) or any(_overlap(destination, other) for other in targets[:index]):
            raise InstallError(f"Source and installation destinations must not overlap: {destination}")
        previous = _existing_snapshot(destination)
        if previous == snapshot:
            action = "unchanged"
        elif previous is None:
            action = "installed"
        elif replace:
            _check_backup_parent(source, destination)
            action = "replaced"
        else:
            raise InstallError(f"Different installation already exists: {destination}. Use --replace to preserve it as a backup.")
        plans.append(Plan(destination, previous, action))
    if dry_run:
        return [Result(plan.destination, f"dry-run: {plan.action}") for plan in plans]
    return [_apply_plan(source, snapshot, plan) for plan in plans]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--project", type=Path, help="Install repository-scoped skills into this project")
    parser.add_argument("--home", type=Path, help="Override the user home directory (ignored with --project)")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show destinations without writing")
    parser.add_argument("--replace", action="store_true", help="Back up and replace a different existing installation")
    options = parser.parse_args(argv)
    try:
        results = install(
            Path(__file__).absolute().parent, agent=options.agent, home=options.home,
            project=options.project, dry_run=options.dry_run, replace=options.replace,
        )
        for result in results:
            print(f"{result.action}: {result.destination}")
            if result.backup is not None:
                print(f"backup: {result.backup}")
    except (InstallError, OSError) as error:
        print(f"Installation stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
