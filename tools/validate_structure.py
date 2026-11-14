"""Check inventory and inline local Markdown links, not runtime readiness."""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import json
import os
import re
import sys

IGNORED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', 'dist', 'build', 'coverage'}
# Placeholder files that do not make a folder real (decision 0006: folders exist only with code).
PLACEHOLDERS = {'README.md', '.gitkeep', '.gitignore'}
# packs/horizontal/<pack> or packs/vertical/<industry>/<pack>
ACTIVE_PACK = re.compile(r'packs/(horizontal/[a-z0-9][a-z0-9-]*|vertical/[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*)')

def _has_content(folder):
    for directory, folders, files in os.walk(folder):
        folders[:] = [d for d in folders if d not in IGNORED]
        if any(f not in PLACEHOLDERS for f in files):
            return True
    return False


def validate(root):
    root = Path(root).resolve()
    errors = []
    try:
        inventory = json.loads((root / 'modules.json').read_text(encoding='utf-8-sig'))
        if not isinstance(inventory, dict):
            raise ValueError('expected an object')
    except (OSError, ValueError) as exc:
        return [f'Invalid module inventory: {exc}']

    def local_path(value):
        if not isinstance(value, str) or not value or '\\' in value or ':' in value:
            return None
        parts = PurePosixPath(value)
        dest = (root / value).resolve()
        if parts.is_absolute() or '..' in parts.parts or parts.as_posix() != value or not dest.is_relative_to(root) or dest == root:
            return None
        return dest

    seen = set()
    for group in ('modules', 'planned_modules'):
        entries = inventory.get(group, [])
        if not isinstance(entries, list) or (group == 'modules' and not entries):
            errors.append(f'{group} must be a list; existing modules cannot be empty')
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f'Invalid entry in {group}')
                continue
            value = entry.get('path')
            dest = local_path(value)
            if dest is None:
                errors.append(f'Invalid module path: {value!r}')
                continue
            key = value.casefold()
            if key in seen:
                errors.append(f'Duplicate module path: {value}')
            seen.add(key)
            maturity = entry.get('maturity')
            implemented = entry.get('implemented')
            if type(implemented) is not bool or maturity not in {'planned', 'skeleton', 'implemented'} or implemented != (maturity == 'implemented'):
                errors.append(f'Inconsistent maturity: {value}')
            if group == 'planned_modules' and maturity != 'planned':
                errors.append(f'Planned module has non-planned maturity: {value}')
            if group == 'modules' and (maturity == 'planned' or not dest.is_dir()):
                errors.append(f'Missing or incorrectly classified existing module: {value}')
            elif group == 'modules' and not _has_content(dest):
                errors.append(f'Existing module holds only placeholders; list it under planned_modules: {value}')
            if group == 'planned_modules' and dest.exists():
                errors.append(f'Planned module folder already exists; move it to modules: {value}')
            if not entry.get('responsibility'):
                errors.append(f'Missing responsibility: {value}')

    for obsolete in ('apps/api', 'evaluations/runners', 'infrastructure/environments', 'infrastructure/infrastructure', 'infrastructure/monitoring',
                     'services/control-plane', 'services/execution', 'services/knowledge'):
        if (root / obsolete).exists():
            errors.append(f'Obsolete directory: {obsolete}')
    packs = inventory.get('packs', {})
    if not isinstance(packs, dict):
        errors.append('Invalid packs inventory')
    else:
        template = local_path(packs.get('template'))
        if template is None or not template.is_dir():
            errors.append('Missing or invalid pack template')
        if packs.get('namespaces') != ['packs/horizontal', 'packs/vertical'] or packs.get('manifest_file') != 'manifest.yaml':
            errors.append('Pack namespaces or manifest filename differ from the approved structure')
        active = packs.get('active')
        if not isinstance(active, list):
            errors.append('Active packs must be a list of repository-relative paths')
        else:
            for value in active:
                dest = local_path(value)
                if dest is None or not ACTIVE_PACK.fullmatch(value) or not (dest / 'manifest.yaml').is_file():
                    errors.append(f'Invalid active pack or missing manifest: {value!r}')
            pack_ids = {PurePosixPath(v).name for v in active if isinstance(v, str)}
            editions = local_path(packs.get('editions', 'packs/editions'))
            for edition in sorted(editions.glob('*.json')) if editions and editions.is_dir() else []:
                try:
                    named = json.loads(edition.read_text(encoding='utf-8')).get('packs', [])
                except ValueError as exc:
                    errors.append(f'Invalid edition {edition.name}: {exc}')
                    continue
                for pack_id in named if isinstance(named, list) else [named]:
                    if pack_id not in pack_ids:
                        errors.append(f'Edition {edition.name} names a pack that is not active: {pack_id!r}')

    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [d for d in folders if d not in IGNORED and not (Path(directory) / d).is_symlink()]
        for filename in files:
            path = Path(directory) / filename
            if path.suffix != '.md' or path.is_symlink():
                continue
            text = path.read_text(encoding='utf-8-sig')
            if 'apps/api' in text or re.search(r'packs/<[^>]+>', text):
                errors.append(f'Obsolete module reference: {path.relative_to(root)}')
            # Inline links only; fenced examples are not navigable document links.
            prose = re.sub(r'^(```|~~~)[^\n]*\n.*?^\1\s*$', '', text, flags=re.M | re.S)
            for link in re.findall(r'\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)', prose):
                link = link.strip('<>')
                url = urlsplit(link)
                if url.scheme or url.netloc:
                    continue
                dest = (path.parent / unquote(url.path)).resolve() if url.path else path
                if not dest.is_relative_to(root):
                    errors.append(f'{path.relative_to(root)}: local link escapes repository: {link}')
                elif not dest.exists():
                    errors.append(f'{path.relative_to(root)}: missing {link}')
                elif url.fragment and dest.suffix == '.md':
                    target = dest.read_text(encoding='utf-8-sig')
                    headings = re.findall(r'^#+\s+(.+?)\s*$', target, re.M)
                    slugs, counts = set(), {}
                    for heading in headings:
                        base = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
                        number = counts.get(base, 0)
                        slug = f'{base}-{number}' if number else base
                        while slug in slugs:
                            number += 1
                            slug = f'{base}-{number}'
                        counts[base] = number + 1
                        slugs.add(slug)
                    if unquote(url.fragment) not in slugs:
                        errors.append(f'{path.relative_to(root)}: missing anchor {link}')
    return errors

if __name__ == '__main__':
    issues = validate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    print('\n'.join(issues) if issues else 'PASS: inventory, module content, pack locations and supported local Markdown links.')
    sys.exit(bool(issues))
