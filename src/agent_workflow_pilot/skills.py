"""Validate portable skill bundles and compare or sync ordinary provider copies.

This is a strict repository format, not a general YAML parser or a security
sandbox. No skill text is executed and no runtime discovery is inferred.
"""
import argparse
import json
from pathlib import Path
import re
import stat
import sys
import unicodedata


class SkillError(ValueError):
    """Malformed bundle or unsafe filesystem layout."""


def _safe_tree(root):
    # Check ancestors too: a redirected provider root must never be written.
    for path in (root, *root.parents):
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
                raise SkillError('symlinks and reparse points are forbidden')
            if not stat.S_ISDIR(info.st_mode):
                raise SkillError('provider root or ancestor is not a directory')
    if not root.exists():
        return {}
    files = {}
    aliases = set()
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
            raise SkillError('symlinks and reparse points are forbidden')
        relative = path.relative_to(root).as_posix()
        for part in path.relative_to(root).parts:
            if (not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', part)
                    or part.split('.')[0].lower() in {'con', 'prn', 'aux', 'nul'}
                    or re.fullmatch(r'(com|lpt)[1-9]', part.split('.')[0], re.I)):
                raise SkillError('nonportable bundle path')
        if relative.lower() in aliases:
            raise SkillError('case-insensitive duplicate path')
        aliases.add(relative.lower())
        if path.is_file():
            if info.st_nlink != 1:
                raise SkillError('hardlinks are forbidden')
            files[relative] = path.read_bytes()
        elif not path.is_dir():
            raise SkillError('unsupported filesystem entry')
    return files


def validate_bundle(root):
    """Return sorted relative file bytes after metadata/link/requirement checks."""
    root = Path(root).absolute()
    files = _safe_tree(root)
    skills = [name for name in files if name.endswith('/SKILL.md') and name.count('/') == 1]
    if not skills:
        raise SkillError('no skills found')
    ids = set()
    for name in skills:
        text = files[name].decode('utf-8')
        lines = text.splitlines()
        if not lines or lines[0] != '---' or '---' not in lines[1:]:
            raise SkillError('missing frontmatter')
        end = lines.index('---', 1)
        metadata = {}
        for line in lines[1:end]:
            key, sep, value = line.partition(': ')
            if not sep or key in metadata or key not in {'name', 'description'}:
                raise SkillError('unknown or duplicate metadata; requirements are not supported')
            try:
                metadata[key] = json.loads(value)
            except ValueError as exc:
                raise SkillError('metadata must use JSON-quoted YAML strings') from exc
        if set(metadata) != {'name', 'description'}:
            raise SkillError('name and description required')
        ident = metadata['name']
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', ident):
            raise SkillError('invalid skill ID')
        if ident in ids:
            raise SkillError('duplicate skill ID')
        ids.add(ident)
        if ident != name.split('/')[0]:
            raise SkillError('skill ID must match directory')
        description = metadata['description']
        if not isinstance(description, str) or not description.strip() or len(description) > 500:
            raise SkillError('invalid description')
        if not '\n'.join(lines[end + 1:]).strip():
            raise SkillError('empty procedure')
    for name, raw in files.items():
        if name.split('/')[0] not in ids:
            raise SkillError('file outside a registered skill')
        if not name.endswith('.md'):
            raise SkillError('only Markdown assets supported in format 1')
        text = raw.decode('utf-8')
        if any((ord(c) < 32 and c not in '\n\t') or unicodedata.category(c) == 'Cf'
               or c in '\u0085\u2028\u2029' for c in text):
            raise SkillError('control characters or non-LF endings')
        # Conservative lint, not proof against malicious natural language.
        if re.search(r'(?im)^\s*(?:requires|dependencies|allowed-tools)\s*:', text):
            raise SkillError('undeclared runtime requirements')
        if re.search(r'(?i)(--admin|--force|--no-verify|--no-gpg-sign|(?<!\w)-f(?!\w)|ignore\s+previous\s+instructions|disable\s+protections)', text):
            raise SkillError('unsafe requirement')
        # Keep this deliberately narrow: inline local links, no remote or
        # reference-style links, HTML or anchors requiring a Markdown parser.
        if re.search(r'(?m)^\s*\[[^\]]+\]:|<[^>]+>|\]\[[^\]]*\]', text):
            raise SkillError('unsupported link syntax')
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            if not re.fullmatch(r'[A-Za-z0-9_./-]+', target):
                raise SkillError('unsafe link target')
            resolved = (root / name).parent / target
            resolved = resolved.resolve()
            bundle = root / name.split('/')[0]
            if not resolved.is_relative_to(bundle) or not resolved.is_file():
                raise SkillError('broken or escaping link')
    return dict(sorted(files.items()))


def synchronize(repo, *, write=False):
    """Validate before writing; reject extra copies instead of deleting them.

    Returns drift paths. Write is idempotent but not a multi-file transaction;
    rerun after interrupted writes. Caller must ensure exclusive checkout access.
    """
    repo = Path(repo).absolute()
    expected = validate_bundle(repo / 'harness/skills')
    copies = []
    drift = []
    for provider in ('.agents', '.claude'):
        root = repo / provider / 'skills'
        actual = _safe_tree(root)
        if set(actual) - set(expected):
            raise SkillError('unexpected provider files; reconcile manually')
        copies.append((root, actual))
        drift.extend(f'{provider}/skills/{name}' for name in expected
                     if actual.get(name) != expected[name])
    if write:
        for root, actual in copies:
            for name, content in expected.items():
                if actual.get(name) != content:
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
    return drift


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--sync', action='store_true', help='write provider copies')
    args = parser.parse_args(argv)
    try:
        drift = synchronize(args.root, write=args.sync)
        print(json.dumps({'valid': args.sync or not drift, 'drift': drift,
                          'runtime_discovery': 'not_verified'}, sort_keys=True))
        return 0 if args.sync or not drift else 1
    except (SkillError, OSError, UnicodeError) as exc:
        print(f'skill validation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
