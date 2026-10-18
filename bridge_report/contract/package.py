"""Load handoff packages from JSON files, dictionaries or zip archives (handoff.json + assets/)."""
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_ZIP_ENTRIES = 2000
HANDOFF_NAME = 'handoff.json'


class PackageError(ValueError):
    """Raised when a package file or archive is unusable."""


def _reject_constant(value):
    raise PackageError('JSON 不允许 NaN 或 Infinity')


def parse_json(text):
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise PackageError(f'交接包不是合法 JSON：第 {exc.lineno} 行第 {exc.colno} 列') from exc


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


@dataclass
class Package:
    data: dict
    base_dir: Path | None = None
    root_limit: Path | None = None

    def resolve(self, relative):
        """Resolve a package-relative file path; None when unavailable or outside the allowed root."""
        if not relative or self.base_dir is None:
            return None
        candidate = (Path(self.base_dir) / relative).resolve()
        limit = self.root_limit or self.base_dir
        if not inside(candidate, limit) or not candidate.is_file():
            return None
        return candidate

    def assets(self):
        return {a['id']: a for a in self.data.get('assets', []) if isinstance(a, dict) and a.get('id')}

    def asset_path(self, asset_id):
        asset = self.assets().get(asset_id)
        return self.resolve(asset.get('path')) if asset else None


def load_file(path, root_limit=None):
    path = Path(path)
    data = parse_json(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise PackageError('交接包顶层必须是 JSON 对象')
    return Package(data, path.parent, Path(root_limit) if root_limit else path.parent)


def load_zip(raw, destination):
    """Extract an uploaded archive into `destination` after validating every entry path."""
    if len(raw) > MAX_ZIP_BYTES:
        raise PackageError('交接压缩包不能超过 50 MB')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise PackageError('上传文件不是有效的 zip 压缩包') from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            raise PackageError('压缩包文件数量过多')
        if sum(e.file_size for e in entries) > 4 * MAX_ZIP_BYTES:
            raise PackageError('压缩包解压后体积过大')
        for entry in entries:
            name = PurePosixPath(entry.filename.replace('\\', '/'))
            if name.is_absolute() or '..' in name.parts or ':' in entry.filename:
                raise PackageError(f'压缩包包含不安全路径：{entry.filename}')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise PackageError(f'压缩包不允许符号链接：{entry.filename}')
        names = [PurePosixPath(e.filename) for e in entries if not e.is_dir()]
        if PurePosixPath(HANDOFF_NAME) not in names:
            raise PackageError('压缩包根目录缺少 handoff.json')
        for entry in entries:
            target = destination.joinpath(*PurePosixPath(entry.filename.replace('\\', '/')).parts)
            if not inside(target, destination):
                raise PackageError(f'压缩包包含不安全路径：{entry.filename}')
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, open(target, 'wb') as sink:
                sink.write(source.read())
    return load_file(destination / HANDOFF_NAME, root_limit=destination)
