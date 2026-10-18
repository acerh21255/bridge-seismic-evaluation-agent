"""Evidence hashing. Inline evidence is hashed as canonical JSON (sorted keys, compact, UTF-8)."""
import hashlib
import json
from pathlib import Path


def content_hash(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sources(package, base_dir=None):
    """Return problems for inline and file evidence; external evidence is only declared."""
    problems = []
    for key, source in package.get('sources', {}).items():
        kind = source.get('kind', 'inline')
        if kind == 'inline':
            if content_hash(source.get('content')) != source.get('sha256'):
                problems.append(f'sources.{key}：证据内容与 SHA256 不一致')
        elif kind == 'file':
            path = Path(base_dir or '.') / source.get('path', '')
            if base_dir is None or not path.is_file():
                problems.append(f'sources.{key}：证据文件 {source.get("path")} 未随交接包提供')
            elif file_hash(path) != source.get('sha256'):
                problems.append(f'sources.{key}：证据文件与 SHA256 不一致')
    return problems
