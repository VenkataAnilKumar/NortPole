"""Rename EvolvXSI references to NortPole throughout a repository.

The command is intentionally a dry run unless ``--apply`` is supplied. It
rewrites UTF-8 text files and can optionally rename matching file and folder
names with ``--rename-paths``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


REPLACEMENTS = {
    "EVOLVXSI": "NORTPOLE",
    "EvolvXSI": "NortPole",
    "evolvxsi": "nortpole",
}
IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "coverage",
}


def replace_names(value: str) -> str:
    """Return *value* with the supported product-name variants replaced."""

    for source, destination in REPLACEMENTS.items():
        value = value.replace(source, destination)
    return value


def iter_files(root: Path) -> Iterable[Path]:
    """Yield repository files while skipping generated and VCS directories."""

    for directory, folders, filenames in os.walk(root):
        folders[:] = [name for name in folders if name not in IGNORED_DIRECTORIES]
        for filename in filenames:
            path = Path(directory) / filename
            if not path.is_symlink():
                yield path


def rewrite_file(path: Path, apply: bool) -> bool:
    """Replace names in one UTF-8 file and return whether it changed."""

    try:
        original = path.read_bytes()
        if b"\x00" in original:
            return False
        text = original.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return False

    updated = replace_names(text)
    if updated == text:
        return False
    if apply:
        encoding = "utf-8-sig" if original.startswith(b"\xef\xbb\xbf") else "utf-8"
        path.write_text(updated, encoding=encoding, newline="")
    return True


def rename_paths(root: Path, apply: bool) -> int:
    """Rename matching path components from deepest paths to shallowest."""

    candidates = [
        path
        for path in root.rglob("*")
        if path != root
        and not any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts)
        and replace_names(path.name) != path.name
    ]
    count = 0
    for path in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        destination = path.with_name(replace_names(path.name))
        print(f"PATH {path.relative_to(root)} -> {destination.relative_to(root)}")
        count += 1
        if apply:
            path.rename(destination)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
    parser.add_argument("--rename-paths", action="store_true", help="also rename matching files and directories")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    tool_path = Path(__file__).resolve()
    fixture_path = tool_path.parent / "tests" / "test_rename_nortpole.py"
    changed = 0
    for path in iter_files(root):
        if path.resolve() in {tool_path, fixture_path}:
            continue
        if rewrite_file(path, args.apply):
            print(f"TEXT {path.relative_to(root)}")
            changed += 1
    renamed = rename_paths(root, args.apply) if args.rename_paths else 0
    action = "Applied" if args.apply else "Would apply"
    print(f"{action}: {changed} text file(s), {renamed} path rename(s).")
    if not args.apply:
        print("Re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
