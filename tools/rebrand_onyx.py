#!/usr/bin/env python3
"""Rebrand a copy of the upstream Onyx Community Edition source to EvolvXSI.

Default mode is a dry run that prints a report and changes nothing. Pass --apply
to rewrite files and rename paths in place. Run it on a COPY, never on the
upstream checkout.

Forms: Onyx -> EvolvXSI, onyx -> evolvxsi, ONYX -> EVOLVXSI.

Never changed: LICENSE files, NOTICE, UPSTREAM.md, lock files, binary files,
protected strings (upstream repository slug, upstream domains, upstream
copyright holder), and anything under an `ee` directory (excluded from the copy).
External domains are reported so they can be removed or replaced by hand.
"""
import argparse
import collections
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", ".venv"}
SKIP_EE = {"ee"}
SKIP_FILES = {"LICENSE", "NOTICE", "UPSTREAM.md", "uv.lock", "bun.lock",
              "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
TEXT_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".md",
            ".mdx", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".txt", ".css",
            ".scss", ".html", ".sh", ".env", ".sql", ".mako", ".conf", ".pyi", ""}
PROTECT = ["onyx-dot-app", "DanswerAI", "danswer-ai"]
EXTERNAL = re.compile(r"[A-Za-z0-9./:_-]*onyx\.(?:app|dev|ai)[A-Za-z0-9./_-]*", re.I)
PATTERN = re.compile(r"ONYX|Onyx|onyx")
MAP = {"ONYX": "EVOLVXSI", "Onyx": "EvolvXSI", "onyx": "evolvxsi"}


def is_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in TEXT_EXT:
        return False
    try:
        with open(path, "rb") as f:
            return b"\0" not in f.read(4096)
    except OSError:
        return False


def category(path):
    ext = os.path.splitext(path)[1].lower()
    return {".py": "python", ".ts": "web", ".tsx": "web", ".js": "web",
            ".json": "config", ".yml": "config", ".yaml": "config",
            ".toml": "config", ".md": "docs", ".mdx": "docs"}.get(ext, "other")


def rewrite(text):
    placeholders = {}
    for i, p in enumerate(PROTECT):
        token = f"\u0001P{i}\u0001"
        placeholders[token] = p
        text = text.replace(p, token)

    def hold(m):
        token = f"\u0001D{len(placeholders)}\u0001"
        placeholders[token] = m.group(0)
        return token

    text = EXTERNAL.sub(hold, text)  # external upstream domains stay as written
    text = PATTERN.sub(lambda m: MAP[m.group(0)], text)
    for token, p in placeholders.items():
        text = text.replace(token, p)
    return text


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d not in SKIP_EE]
        yield dirpath, dirnames, filenames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="directory containing the COPY to rebrand")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    by_cat = collections.Counter()
    by_file = collections.Counter()
    protected_hits = collections.Counter()
    external = collections.Counter()
    legacy = 0
    changed_files = 0
    renames = []
    binary_named = []

    for dirpath, dirnames, filenames in walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if "onyx" in name.lower():
                (renames if is_text(path) or name.endswith(".py") else binary_named).append(path)
            if name in SKIP_FILES or not is_text(path):
                continue
            try:
                text = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for p in PROTECT:
                protected_hits[p] += text.count(p)
            for m in EXTERNAL.findall(text):
                external[m.lower()] += 1
            legacy += len(re.findall(r"danswer", text, re.I))
            new = rewrite(text)
            if new != text:
                n = len(PATTERN.findall(text))
                by_cat[category(path)] += n
                by_file[os.path.relpath(path, root)] += n
                changed_files += 1
                if args.apply:
                    open(path, "w", encoding="utf-8", newline="").write(new)
        for d in dirnames:
            if "onyx" in d.lower():
                renames.append(os.path.join(dirpath, d))

    print(f"mode: {'APPLY' if args.apply else 'DRY RUN'}  root: {root}")
    print(f"files with changes: {changed_files}; replacements by category: {dict(by_cat)}")
    print(f"paths to rename (files and folders): {len(renames)}; binary files with 'onyx' in the name: {len(binary_named)}")
    print("protected strings left untouched:", dict(protected_hits))
    print(f"legacy 'danswer' mentions (reported only): {legacy}")
    print("\ntop files by replacements:")
    for f, n in by_file.most_common(args.top):
        print(f"  {n:6d}  {f}")
    print("\nexternal upstream domains (NOT replaced, review by hand):")
    for e, n in external.most_common(25):
        print(f"  {n:5d}  {e}")
    if binary_named:
        print("\nbinary files named after upstream (replace with new brand assets):")
        for p in binary_named[:20]:
            print("  ", os.path.relpath(p, root))

    if args.apply:
        for p in sorted(renames, key=lambda x: -x.count(os.sep)):
            base = os.path.basename(p)
            new = os.path.join(os.path.dirname(p), rewrite(base))
            if new != p and os.path.exists(p) and not os.path.exists(new):
                os.rename(p, new)
        print("\nrenamed paths; now run compile, import and web type checks before committing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
