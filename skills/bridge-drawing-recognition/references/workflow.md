# Recognition Workflow

## 1. Inputs

- Structured screening workbook.
- Scanned PDF/PNG/JPG drawing volumes.
- Optional integrator-owned vision backend.

## 2. Page taxonomy

Use: `cover`, `toc`, `design_notes`, `quantity_table`,
`general_arrangement`, `plan_elevation`, `girder_section`, `abutment`,
`pier`, `cap_beam_reinforcement`, `pile`, `bearing`, `appurtenance`,
`backcover`, `unknown`.

Page retrieval should favor recall for critical-field pages over perfect page
classification. Use Top-K candidate retrieval before model calls.

## 3. Field groups

- Metadata/table fields: B, C, D, E, F, G, H, I, J.
- Structural fields: K, L, M, N, Q, R, S.
- Drawing-existence flags: T, V, X, Z.
- Reinforcement ratios: U, W, Y, AA, only when explicitly written.
- Pier heights: AB and later columns, optional enhancement and not a v1 gate.

Column A has no business meaning and must be ignored.

## 4. Evidence contract

Each extracted field carries value, normalized value, unit, state, confidence,
evidence text, page number, bounding box, model name, and reason.

Allowed states: `extracted`, `derived`, `missing`, `not_applicable`, `unknown`.
Never replace `unknown` with a prior or common engineering value.

## 5. Reconciliation

- Group candidates by field code.
- Rank by confidence, state, and evidence presence.
- Preserve conflicting candidates.
- Mark low-confidence or conflicting fields for review.
- Compute dimensions with deterministic Python code, not model arithmetic.

## 6. Workbook output

Produce a new workbook with:

- `筛选结果`: one normalized row per bridge/substructure record.
- `字段证据`: all candidate provenance.
- `可选墩高`: optional AB+ values.
- `问题`: ingestion and extraction issues.
- `元数据`: source hashes, model identity, and run metadata.

Never overwrite the source workbook.
