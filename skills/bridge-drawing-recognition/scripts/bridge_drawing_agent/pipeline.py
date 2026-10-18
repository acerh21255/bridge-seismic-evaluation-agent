"""Manifest-level classification and field-extraction orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .extraction import (
    ALL_FIELD_CODES,
    FieldCandidate,
    classify_page,
    extract_page_fields,
    merge_field_candidates,
)
from .utils import atomic_write_json, read_json, utc_now_iso
from .vision import backend_model_name

DRAWING_PAGE_TYPES = {
    "quantity_table", "general_arrangement", "plan_elevation",
    "girder_section", "abutment", "pier", "cap_beam_reinforcement",
    "pile", "bearing", "design_notes", "toc",
}


def _image_path_for_page(page: dict[str, Any]) -> Path | None:
    value = page.get("thumbnail_path")
    if not value:
        return None
    path = Path(value)
    return path if path.is_file() else None

def classify_manifest_pages(
    manifest: dict[str, Any],
    client: Any,
    *,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    processed = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    for document in manifest.get("documents", []):
        for page in document.get("pages", []):
            if limit is not None and processed >= limit:
                break
            if page.get("page_type") not in {None, "", "unknown"} and not force:
                skipped += 1
                continue
            image_path = _image_path_for_page(page)
            if image_path is None:
                errors.append({
                    "doc_id": document.get("doc_id"),
                    "page_number": page.get("page_number"),
                    "error": "缺少页面缩略图",
                })
                continue
            context = (
                f"文件={document.get('file_name')}；"
                f"页码={page.get('page_number')}/{page.get('page_count')}"
            )
            try:
                result = classify_page(client, image_path, context=context)
            except Exception as error:
                errors.append({
                    "doc_id": document.get("doc_id"),
                    "page_number": page.get("page_number"),
                    "error": str(error),
                })
                continue
            page.update({
                "page_type": result.get("page_type", "unknown"),
                "page_title": result.get("title", ""),
                "bridge_hint": result.get("bridge_hint", ""),
                "classification_confidence": result.get("confidence", 0.0),
                "classification_evidence": result.get("evidence_text", ""),
                "classification_reason": result.get("reason", ""),
                "classification_model": backend_model_name(client),
            })
            processed += 1
        if limit is not None and processed >= limit:
            break
    manifest["classification"] = {
        "processed": processed,
        "skipped": skipped,
        "error_count": len(errors),
        "errors": errors,
        "generated_at": utc_now_iso(),
    }
    return manifest

def extract_manifest_fields(
    manifest: dict[str, Any],
    client: Any,
    *,
    doc_id: str | None = None,
    limit: int | None = None,
    page_types: Iterable[str] = DRAWING_PAGE_TYPES,
    field_codes: Iterable[str] = ALL_FIELD_CODES,
) -> dict[str, Any]:
    allowed_types = set(page_types)
    results: list[dict[str, Any]] = []
    for document in manifest.get("documents", []):
        if doc_id and document.get("doc_id") != doc_id:
            continue
        candidates: list[FieldCandidate] = []
        processed_pages = 0
        errors: list[dict[str, Any]] = []
        for page in document.get("pages", []):
            if page.get("page_type") not in allowed_types:
                continue
            if limit is not None and processed_pages >= limit:
                break
            image_path = _image_path_for_page(page)
            if image_path is None:
                continue
            try:
                page_candidates = extract_page_fields(
                    client,
                    image_path,
                    bridge_hint=page.get("bridge_hint") or document.get("file_name", ""),
                    page_type=page.get("page_type", "unknown"),
                    field_codes=field_codes,
                )
            except Exception as error:
                errors.append({
                    "page_number": page.get("page_number"),
                    "error": str(error),
                })
                continue
            for candidate in page_candidates:
                candidate.doc_id = document.get("doc_id", "")
                candidate.page_number = page.get("page_number")
                candidate.model = backend_model_name(client)
            candidates.extend(page_candidates)
            processed_pages += 1
        if candidates or doc_id:
            results.append({
                "doc_id": document.get("doc_id", ""),
                "file_name": document.get("file_name", ""),
                "processed_pages": processed_pages,
                "fields": merge_field_candidates(candidates),
                "errors": errors,
            })
    return {
        "schema_version": "0.1",
        "generated_at": utc_now_iso(),
        "documents": results,
    }

def classify_manifest_file(
    manifest_path: str | Path,
    client: Any,
    output_path: str | Path,
    *,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    manifest = read_json(Path(manifest_path))
    result = classify_manifest_pages(manifest, client, limit=limit, force=force)
    atomic_write_json(Path(output_path), result)
    return result

def extract_manifest_file(
    manifest_path: str | Path,
    client: Any,
    output_path: str | Path,
    *,
    doc_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    manifest = read_json(Path(manifest_path))
    result = extract_manifest_fields(manifest, client, doc_id=doc_id, limit=limit)
    atomic_write_json(Path(output_path), result)
    return result

