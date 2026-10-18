---
name: bridge-drawing-recognition
description: Process scanned Chinese bridge construction-drawing PDFs/images into evidence-backed bridge records and Excel review workbooks. Use for drawing ingestion, page classification, OCR/LMM adapter boundaries, bridge-field extraction, and reconciliation; do not invent missing values or act as a structural-design authority.
---

# Bridge Drawing Recognition

## Ownership boundary

This skill owns deterministic drawing processing, prompts, JSON schemas, page
classification contracts, field extraction contracts, reconciliation, and Excel
output. It must not contain provider SDKs, API keys, endpoints, or network
calls.

The host environment owns the vision capability. Require a backend implementing
`analyze_image(...)`, injected through:

```powershell
python -m bridge_drawing_agent.cli --backend your_module:factory ...
```

or `BRIDGE_VISION_BACKEND=your_module:factory`.

When no backend is available, run only ingestion, normalization, manifest,
schema inspection, and dry-run commands. Do not fabricate extraction results.

## Workflow

1. Inventory the workbook and drawing folder.
2. Normalize workbook records while ignoring column A.
3. Build a page manifest with hashes, page sizes, and thumbnails.
4. Classify pages through the injected backend.
5. Extract only relevant fields from relevant page types.
6. Merge candidates by evidence and confidence; preserve conflicts.
7. Export `筛选结果`, `字段证据`, `可选墩高`, `问题`, and `元数据` sheets.
8. Mark unverified values for review; never silently backfill them.

## Commands

```powershell
# Run from the unified repository root.
$env:PYTHONPATH = Join-Path $PWD 'skills\bridge-drawing-recognition\scripts'
python -m bridge_drawing_agent.cli doctor
python -m bridge_drawing_agent.cli normalize-workbook "<workbook.xlsx>" --output "artifacts/g8511_records.json"
python -m bridge_drawing_agent.cli manifest "<drawing-folder>" --output "artifacts/page_manifest" --render-thumbnails
python -m bridge_drawing_agent.cli export-normalized "artifacts/g8511_records.json" --output "artifacts/g8511_normalized.xlsx"
python -m bridge_drawing_agent.cli --backend your_module:factory classify-manifest "artifacts/page_manifest/manifest.json" --output "artifacts/manifest_classified.json" --limit 10
python -m bridge_drawing_agent.cli --backend your_module:factory extract-manifest "artifacts/manifest_classified.json" --output "artifacts/bridge_fields.json" --limit 5
```

Use `--dry-run` before the first real backend call.

## Reading order

- Read `references/vision-backend-contract.md` before implementing an adapter.
- Read `references/workflow.md` for page taxonomy, extraction, and validation rules.
- Read `references/field-contract.md` for the downstream workbook dictionary.
- Use `scripts/run_bridge_agent.py` or the module commands above. The packaged skill contains its own `bridge_drawing_agent` implementation and only requires its Python dependencies.


## Runtime dependencies

Install scripts/requirements.txt before rendering PDFs. Pillow is required; pypdfium2 is the portable PDFium source. The agent also discovers a host-provided PDFium DLL automatically.
