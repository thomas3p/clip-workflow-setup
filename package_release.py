"""Build the public workflow ZIP, excluding the local CapCut snapshot and data."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import zipfile

ROOT_FILES = (
    "SKILL.md", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "INSTALL-WINDOWS.cmd", "install.py", "package_release.py",
    ".gitignore", ".gitattributes",
)
TREES = ("agents", "references", "scripts", "assets", "tests", "evals")
EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml", ".tmpl"}
EXCLUDED_PARTS = {"__pycache__", ".git", ".venv", "node_modules", "vendor", "dist", "local"}


def public_files(root: Path) -> list[Path]:
    files = []
    for name in ROOT_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Required release file missing or linked: {name}")
        files.append(path)
    for tree in TREES:
        directory = root / tree
        if directory.is_symlink():
            raise ValueError(f"Linked release directory is not supported: {tree}")
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(root)
            if EXCLUDED_PARTS.intersection(relative.parts):
                continue
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError(f"Linked release path is not supported: {relative}")
            if not path.is_file() or path.suffix not in EXTENSIONS:
                continue
            if any(term in path.name.lower() for term in ("credential", "token", ".env")):
                raise ValueError(f"Possible local credential file: {relative}")
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def build_release(root: Path, destination: Path) -> int:
    files = public_files(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".workflow-release-", suffix=".zip", dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                name = "clip-workflow-setup/" + path.relative_to(root).as_posix()
                entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, path.read_bytes())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List included files without writing a ZIP")
    parser.add_argument("--output", type=Path, help="ZIP destination (default: dist/clip-workflow-setup.zip)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.list:
        for path in public_files(root):
            print(path.relative_to(root).as_posix())
        return
    output = (args.output or root / "dist/clip-workflow-setup.zip").absolute()
    count = build_release(root, output)
    print(f"Created {output} ({count} workflow files; no vendor or local account data)")


if __name__ == "__main__":
    main()
