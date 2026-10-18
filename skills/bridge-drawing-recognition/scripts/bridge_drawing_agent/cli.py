"""Command line interface for the provider-neutral bridge drawing agent."""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .exporter import export_normalized_workbook
from .extraction import (
    ALL_FIELD_CODES,
    CLASSIFY_PAGE_PROMPT,
    bridge_extraction_prompt,
    classify_page,
    extract_page_fields,
)
from .manifest import build_manifest, write_manifest
from .pdfium import pdfium_available
from .pipeline import classify_manifest_file, extract_manifest_file
from .utils import atomic_write_json
from .vision import backend_model_name, load_vision_backend
from .workbook import inspect_workbook, normalize_workbook


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _backend(args: argparse.Namespace):
    return load_vision_backend(getattr(args, "backend", None))


def command_inspect_workbook(args: argparse.Namespace) -> int:
    result = inspect_workbook(Path(args.workbook), args.sheet)
    if args.output:
        atomic_write_json(Path(args.output), result)
    _print_json(result)
    return 0


def command_normalize_workbook(args: argparse.Namespace) -> int:
    result = normalize_workbook(Path(args.workbook), args.sheet)
    if args.output:
        atomic_write_json(Path(args.output), result)
    _print_json({
        "source_file": result["source_file"],
        "record_count": result["summary"]["record_count"],
        "max_column": result["summary"]["max_column"],
        "issue_count": len(result["issues"]),
        "output": str(Path(args.output).resolve()) if args.output else None,
    })
    return 0


def command_export_normalized(args: argparse.Namespace) -> int:
    output = export_normalized_workbook(Path(args.input), Path(args.output))
    _print_json({"output": str(output.resolve())})
    return 0


def command_manifest(args: argparse.Namespace) -> int:
    manifest = build_manifest(
        Path(args.input),
        render_thumbnails=args.render_thumbnails,
        thumbnail_width=args.thumbnail_width,
        thumbnail_quality=args.thumbnail_quality,
        hash_pages=not args.no_hash_pages,
        max_pages=args.max_pages,
        pdfium_dll=args.pdfium_dll,
        asset_root=Path(args.output),
    )
    output_path = write_manifest(manifest, Path(args.output))
    _print_json({"output": str(output_path.resolve()), **manifest["summary"]})
    return 0

def command_classify_page(args: argparse.Namespace) -> int:
    if args.dry_run:
        _print_json({
            "backend": args.backend or "",
            "prompt": CLASSIFY_PAGE_PROMPT,
            "image": args.image,
            "will_call_backend": False,
        })
        return 0
    backend = _backend(args)
    result = classify_page(backend, Path(args.image), context=args.context or "")
    _print_json(result)
    return 0


def command_extract_page(args: argparse.Namespace) -> int:
    codes = [code.strip().upper() for code in args.fields.split(",") if code.strip()]
    if not codes:
        codes = list(ALL_FIELD_CODES)
    if args.dry_run:
        _print_json({
            "backend": args.backend or "",
            "prompt": bridge_extraction_prompt(
                bridge_hint=args.bridge_hint or "",
                page_type=args.page_type,
                field_codes=codes,
            ),
            "image": args.image,
            "will_call_backend": False,
        })
        return 0
    backend = _backend(args)
    fields = extract_page_fields(
        backend,
        Path(args.image),
        bridge_hint=args.bridge_hint or "",
        page_type=args.page_type,
        field_codes=codes,
    )
    _print_json({"model": backend_model_name(backend), "fields": [item.to_dict() for item in fields]})
    return 0


def command_classify_manifest(args: argparse.Namespace) -> int:
    backend = _backend(args)
    result = classify_manifest_file(
        Path(args.manifest),
        backend,
        Path(args.output),
        limit=args.limit,
        force=args.force,
    )
    _print_json({
        "output": str(Path(args.output).resolve()),
        "model": backend_model_name(backend),
        **result.get("classification", {}),
    })
    return 0


def command_extract_manifest(args: argparse.Namespace) -> int:
    backend = _backend(args)
    result = extract_manifest_file(
        Path(args.manifest),
        backend,
        Path(args.output),
        doc_id=args.doc_id,
        limit=args.limit,
    )
    _print_json({
        "output": str(Path(args.output).resolve()),
        "model": backend_model_name(backend),
        "document_count": len(result.get("documents", [])),
        "processed_pages": sum(
            document.get("processed_pages", 0) for document in result.get("documents", [])
        ),
    })
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    result = {
        "version": __version__,
        "pdfium_available": pdfium_available(args.pdfium_dll),
        "vision_backend_spec": args.backend or "",
        "vision_backend_loaded": False,
        "vision_backend_model": "",
        "vision_backend_error": "",
        "network_access_owned_by_agent": False,
    }
    if args.backend:
        try:
            backend = _backend(args)
            result["vision_backend_loaded"] = True
            result["vision_backend_model"] = backend_model_name(backend)
        except Exception as error:
            result["vision_backend_error"] = str(error)
    _print_json(result)
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridge-agent",
        description="既有桥梁图纸智能识别 Subagent（无供应商耦合）",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--backend",
        help="视觉后端工厂，格式为 module:factory；也可设置 BRIDGE_VISION_BACKEND",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-workbook", help="检查 Excel 表头和字段覆盖")
    inspect_parser.add_argument("workbook")
    inspect_parser.add_argument("--sheet")
    inspect_parser.add_argument("--output")
    inspect_parser.set_defaults(func=command_inspect_workbook)

    normalize_parser = subparsers.add_parser("normalize-workbook", help="规范化桥体记录")
    normalize_parser.add_argument("workbook")
    normalize_parser.add_argument("--sheet")
    normalize_parser.add_argument("--output", required=True)
    normalize_parser.set_defaults(func=command_normalize_workbook)

    export_parser = subparsers.add_parser("export-normalized", help="从规范化 JSON 导出 Excel")
    export_parser.add_argument("input")
    export_parser.add_argument("--output", required=True)
    export_parser.set_defaults(func=command_export_normalized)

    manifest_parser = subparsers.add_parser("manifest", help="生成 PDF/图片页级清单")
    manifest_parser.add_argument("input")
    manifest_parser.add_argument("--output", required=True)
    manifest_parser.add_argument("--render-thumbnails", action="store_true")
    manifest_parser.add_argument("--thumbnail-width", type=int, default=320)
    manifest_parser.add_argument("--thumbnail-quality", type=int, default=82)
    manifest_parser.add_argument("--no-hash-pages", action="store_true")
    manifest_parser.add_argument("--max-pages", type=int)
    manifest_parser.add_argument("--pdfium-dll")
    manifest_parser.set_defaults(func=command_manifest)

    classify_parser = subparsers.add_parser("classify-page", help="使用注入后端分类单页")
    classify_parser.add_argument("image")
    classify_parser.add_argument("--context")
    classify_parser.add_argument("--dry-run", action="store_true")
    classify_parser.set_defaults(func=command_classify_page)

    extract_parser = subparsers.add_parser("extract-page", help="使用注入后端抽取单页字段")
    extract_parser.add_argument("image")
    extract_parser.add_argument("--bridge-hint")
    extract_parser.add_argument("--page-type", default="unknown")
    extract_parser.add_argument("--fields", default="")
    extract_parser.add_argument("--dry-run", action="store_true")
    extract_parser.set_defaults(func=command_extract_page)

    classify_manifest_parser = subparsers.add_parser(
        "classify-manifest", help="批量分类页面清单中的未知页"
    )
    classify_manifest_parser.add_argument("manifest")
    classify_manifest_parser.add_argument("--output", required=True)
    classify_manifest_parser.add_argument("--limit", type=int)
    classify_manifest_parser.add_argument("--force", action="store_true")
    classify_manifest_parser.set_defaults(func=command_classify_manifest)

    extract_manifest_parser = subparsers.add_parser(
        "extract-manifest", help="按页面分类批量抽取并融合字段"
    )
    extract_manifest_parser.add_argument("manifest")
    extract_manifest_parser.add_argument("--output", required=True)
    extract_manifest_parser.add_argument("--doc-id")
    extract_manifest_parser.add_argument("--limit", type=int)
    extract_manifest_parser.set_defaults(func=command_extract_manifest)

    doctor_parser = subparsers.add_parser("doctor", help="检查核心环境与后端契约")
    doctor_parser.add_argument("--pdfium-dll")
    doctor_parser.set_defaults(func=command_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        if getattr(args, "debug", False):
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
