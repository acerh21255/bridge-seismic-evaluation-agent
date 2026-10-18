"""Fail when source files contain U+FFFD replacement characters (corrupted text)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {'.py', '.md', '.json', '.html', '.css', '.js', '.ps1', '.cmd', '.txt'}
SKIP = {'.venv', 'build', 'vendor', '__pycache__', '_legacy', 'research'}


def main():
    bad = []
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in SUFFIXES and not SKIP.intersection(path.relative_to(ROOT).parts):
            text = path.read_text(encoding='utf-8', errors='replace')
            for n, line in enumerate(text.splitlines(), start=1):
                if '\ufffd' in line:
                    bad.append(f'{path.relative_to(ROOT)}:{n}: {line.strip()[:80]}')
    print('\n'.join(bad) or '未发现乱码字符')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
