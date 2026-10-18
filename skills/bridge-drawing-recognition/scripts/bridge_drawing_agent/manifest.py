"""Build deterministic page manifests for drawing files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageOps

from .pdfium import PdfDocument
from .utils import atomic_write_json, ensure_dir, sha256_bytes, sha256_file, stable_digest, utc_now_iso

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS


def discover_documents(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if root_path.is_file():
        return [root_path] if root_path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    if not root_path.exists():
        raise FileNotFoundError(root_path)
    return sorted(
        (path for path in root_path.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda item: str(item).lower(),
    )


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return path.name


def _save_image_thumbnail(image: Image.Image, output: Path, width: int, quality: int) -> tuple[Image.Image, bytes]:
    rendered = ImageOps.exif_transpose(image)
    rendered.thumbnail((width, 100000), Image.Resampling.LANCZOS)
    payload = output.parent
    ensure_dir(payload)
    import io

    stream = io.BytesIO()
    rendered.convert("L" if rendered.mode in {"1", "L"} else "RGB").save(
        stream, format="JPEG", quality=quality, optimize=True
    )
    data = stream.getvalue()
    output.write_bytes(data)
    return rendered, data


def build_document_manifest(
    path: str | Path,
    *,
    root: str | Path | None = None,
    asset_root: str | Path | None = None,
    render_thumbnails: bool = False,
    thumbnail_width: int = 320,
    thumbnail_quality: int = 82,
    hash_pages: bool = True,
    max_pages: int | None = None,
    pdfium_dll: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(path)
    source_root = Path(root) if root else source.parent
    assets = Path(asset_root) if asset_root else source_root
    file_hash = sha256_file(source)
    doc_id = f"doc-{stable_digest(file_hash, source.name)}"
    pages: list[dict[str, Any]] = []
    thumbnail_dir = assets / "thumbnails" / doc_id
    suffix = source.suffix.lower()

    if suffix in PDF_EXTENSIONS:
        with PdfDocument(source, library_path=pdfium_dll) as document:
            total_pages = document.page_count
            page_limit = total_pages if max_pages is None else min(total_pages, max_pages)
            for page_index in range(page_limit):
                info = document.page_info(page_index)
                page: dict[str, Any] = {
                    "page_index": page_index,
                    "page_number": page_index + 1,
                    "page_count": total_pages,
                    "width_points": info["width_points"],
                    "height_points": info["height_points"],
                    "rotation": info["rotation"],
                    "page_type": "unknown",
                    "render_status": "metadata_only",
                }
                if render_thumbnails or hash_pages:
                    image, payload = document.thumbnail(page_index, width=thumbnail_width, quality=thumbnail_quality)
                    page["pixel_width"] = image.width
                    page["pixel_height"] = image.height
                    page["thumbnail_sha256"] = sha256_bytes(payload)
                    page["render_status"] = "rendered"
                    if render_thumbnails:
                        output = thumbnail_dir / f"page-{page_index + 1:04d}.jpg"
                        ensure_dir(output.parent)
                        output.write_bytes(payload)
                        page["thumbnail_path"] = str(output)
                pages.append(page)
    elif suffix in IMAGE_EXTENSIONS:
        with Image.open(source) as image:
            width, height = image.size
            total_pages = 1
            page: dict[str, Any] = {
                "page_index": 0,
                "page_number": 1,
                "page_count": 1,
                "width_points": None,
                "height_points": None,
                "rotation": 0,
                "pixel_width": width,
                "pixel_height": height,
                "page_type": "unknown",
                "render_status": "metadata_only",
            }
            if render_thumbnails or hash_pages:
                if render_thumbnails:
                    output = thumbnail_dir / "page-0001.jpg"
                    rendered, payload = _save_image_thumbnail(
                        image, output, thumbnail_width, thumbnail_quality
                    )
                else:
                    import io

                    rendered = ImageOps.exif_transpose(image)
                    rendered.thumbnail((thumbnail_width, 100000), Image.Resampling.LANCZOS)
                    stream = io.BytesIO()
                    rendered.convert("L" if rendered.mode in {"1", "L"} else "RGB").save(
                        stream, format="JPEG", quality=thumbnail_quality, optimize=True
                    )
                    payload = stream.getvalue()
                page["thumbnail_sha256"] = sha256_bytes(payload)
                page["render_status"] = "rendered"
                if render_thumbnails:
                    page["thumbnail_path"] = str(thumbnail_dir / "page-0001.jpg")
            pages.append(page)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")

    return {
        "doc_id": doc_id,
        "path": str(source.resolve()),
        "relative_path": _relative_path(source, source_root),
        "file_name": source.name,
        "extension": suffix,
        "size_bytes": source.stat().st_size,
        "sha256": file_hash,
        "page_count": total_pages,
        "pages": pages,
    }


def build_manifest(
    input_path: str | Path,
    *,
    render_thumbnails: bool = False,
    thumbnail_width: int = 320,
    thumbnail_quality: int = 82,
    hash_pages: bool = True,
    max_pages: int | None = None,
    pdfium_dll: str | Path | None = None,
    asset_root: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(input_path)
    root = source if source.is_dir() else source.parent
    documents = [
        build_document_manifest(
            path,
            root=root,
            asset_root=asset_root or root,
            render_thumbnails=render_thumbnails,
            thumbnail_width=thumbnail_width,
            thumbnail_quality=thumbnail_quality,
            hash_pages=hash_pages,
            max_pages=max_pages,
            pdfium_dll=pdfium_dll,
        )
        for path in discover_documents(source)
    ]
    return {
        "schema_version": "0.1",
        "generated_at": utc_now_iso(),
        "source_root": str(root.resolve()),
        "render": {
            "thumbnail_width": thumbnail_width,
            "render_thumbnails": render_thumbnails,
            "hash_pages": hash_pages,
            "max_pages": max_pages,
        },
        "summary": {
            "document_count": len(documents),
            "page_count": sum(document["page_count"] for document in documents),
            "file_size_bytes": sum(document["size_bytes"] for document in documents),
        },
        "documents": documents,
    }


def write_manifest(manifest: dict[str, Any], output_dir: str | Path) -> Path:
    output = Path(output_dir)
    ensure_dir(output)
    output_path = output / "manifest.json"
    atomic_write_json(output_path, manifest)
    return output_path
