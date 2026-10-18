"""Structured page classification and bridge-field extraction contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .normalization import normalize_field_value
from .utils import normalize_text
from .vision import VisionBackend, backend_model_name

PAGE_TYPES = (
    "cover", "toc", "design_notes", "quantity_table", "general_arrangement",
    "plan_elevation", "girder_section", "abutment", "pier",
    "cap_beam_reinforcement", "pile", "bearing", "appurtenance",
    "backcover", "unknown",
)
REQUIRED_FIELD_CODES = ("B", "D", "E", "F", "G", "H", "I", "J")
OPTIONAL_FIELD_CODES = (
    "C", "K", "L", "M", "N", "O", "P", "Q", "R", "S",
    "T", "U", "V", "W", "X", "Y", "Z", "AA",
)
ALL_FIELD_CODES = REQUIRED_FIELD_CODES + OPTIONAL_FIELD_CODES


def page_classification_schema() -> dict[str, Any]:
    return {
        "name": "page_classification",
        "schema": {
            "type": "object",
            "properties": {
                "page_type": {"type": "string", "enum": list(PAGE_TYPES)},
                "title": {"type": "string"},
                "bridge_hint": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence_text": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": [
                "page_type", "title", "bridge_hint", "confidence",
                "evidence_text", "reason",
            ],
            "additionalProperties": False,
        },
    }


def bridge_field_schema(field_codes: Iterable[str] = ALL_FIELD_CODES) -> dict[str, Any]:
    codes = [code for code in field_codes if code in ALL_FIELD_CODES]
    field_schema = {
        "type": "object",
        "properties": {
            "field_code": {"type": "string", "enum": codes},
            "value": {"type": ["string", "number", "boolean", "null"]},
            "normalized_value": {"type": ["string", "number", "boolean", "null"]},
            "unit": {"type": ["string", "null"]},
            "state": {
                "type": "string",
                "enum": ["extracted", "derived", "missing", "not_applicable", "unknown"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_text": {"type": "string"},
            "bbox": {
                "type": ["object", "null"],
                "properties": {
                    "x": {"type": "number"}, "y": {"type": "number"},
                    "width": {"type": "number"}, "height": {"type": "number"},
                },
                "required": ["x", "y", "width", "height"],
                "additionalProperties": False,
            },
            "reason": {"type": "string"},
        },
        "required": [
            "field_code", "value", "normalized_value", "unit", "state",
            "confidence", "evidence_text", "bbox", "reason",
        ],
        "additionalProperties": False,
    }
    return {
        "name": "bridge_page_fields",
        "schema": {
            "type": "object",
            "properties": {"fields": {"type": "array", "items": field_schema}},
            "required": ["fields"],
            "additionalProperties": False,
        },
    }

CLASSIFY_PAGE_PROMPT = f"""
请根据图像中的标题栏、图名、目录、数量表和图形内容判断页面类型。
只能依据图像证据回答，不要猜测。
page_type 必须从以下枚举中选择：{', '.join(PAGE_TYPES)}。
只输出一个 json 对象，不要添加额外字段，固定格式为：
{{"page_type":"general_arrangement","title":"图名","bridge_hint":"桥名或桩号","confidence":0.98,"evidence_text":"图像中出现的证据","reason":"判断依据"}}
路径文件位置信息仅用于辅助，不得替代图像证据。
""".strip()


def bridge_extraction_prompt(
    *,
    bridge_hint: str = "",
    page_type: str = "unknown",
    field_codes: Iterable[str] = ALL_FIELD_CODES,
) -> str:
    codes = ", ".join(field_codes)
    return f"""
你是桥梁竣工图结构化工程师。只读取当前页面，禁止根据常识补值。
桥梁提示：{bridge_hint or "未提供"}
页面类型：{page_type}
需要检查的字段代码：{codes}

字段含义：
B=序号或记录键；C=桩号/桥名；D=设计桩号；E=左幅/右幅；F=跨径；
G=桥跨组合；H=一联总长；I=主梁形式；J=结构形式；K=支座形式；
L=桥台形式；M=桥墩形式；N=桥墩尺寸；O=纵向墩高差；P=横向墩高差；
Q=桩基形式；R=桩基直径；S=盖梁顺桥向宽度；
T=盖梁配筋图是/否；U=盖梁配筋率；V=桥墩配筋图是/否；W=桥墩配筋率；
X=系梁配筋图是/否；Y=系梁配筋率；Z=桩配筋图是/否；AA=桩配筋率。

规则：
1. 每个字段必须保留图面原始值 value 和规范化值 normalized_value。
2. 页面没有明确证据时，state=unknown 或 missing，value=null。
3. 不要从其他桥、其他分幅或其他图纸类型推断。
4. 数字不得猜测；单位必须按图面或字段定义记录。
5. evidence_text 必须是图像上实际出现的文字或尺寸。
6. bbox 使用相对页面的 0~1 坐标；无法定位时为 null。
7. 固定 json 格式为：
{{"fields":[{{"field_code":"D","value":"K257+528","normalized_value":257528,"unit":"m","state":"extracted","confidence":0.95,"evidence_text":"K257+528","bbox":null,"reason":"标题栏"}}]}}
8. state 只能为 extracted、derived、missing、not_applicable、unknown。
9. 不得增加 fields 之外的顶层字段。
""".strip()

@dataclass
class FieldCandidate:
    field_code: str
    value: Any
    normalized_value: Any
    unit: str | None
    state: str
    confidence: float
    evidence_text: str = ""
    bbox: dict[str, float] | None = None
    reason: str = ""
    page_number: int | None = None
    doc_id: str = ""
    model: str = ""
    conflicts: list["FieldCandidate"] = field(default_factory=list)

    @classmethod
    def from_mapping(
        cls,
        payload: dict[str, Any],
        *,
        page_number: int | None = None,
        doc_id: str = "",
        model: str = "",
    ) -> "FieldCandidate":
        try:
            confidence = float(payload.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        state = normalize_text(payload.get("state")) or "unknown"
        if state not in {"extracted", "derived", "missing", "not_applicable", "unknown", "conflict"}:
            state = "unknown"
        bbox = payload.get("bbox") if isinstance(payload.get("bbox"), dict) else None
        field_code = normalize_text(payload.get("field_code"))
        value = payload.get("value")
        normalized_value, unit = normalize_field_value(
            field_code,
            value,
            payload.get("normalized_value"),
            normalize_text(payload.get("unit")) or None,
        )
        return cls(
            field_code=field_code,
            value=value,
            normalized_value=normalized_value,
            unit=unit,
            state=state,
            confidence=max(0.0, min(1.0, confidence)),
            evidence_text=normalize_text(payload.get("evidence_text")),
            bbox=bbox,
            reason=normalize_text(payload.get("reason")),
            page_number=page_number,
            doc_id=doc_id,
            model=model,
        )

    def score(self) -> tuple[float, int, int]:
        state_score = 2 if self.state == "extracted" else 1 if self.state == "derived" else 0
        evidence_score = 1 if self.evidence_text else 0
        return (self.confidence, state_score, evidence_score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_code": self.field_code,
            "value": self.value,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
            "state": self.state,
            "confidence": self.confidence,
            "evidence_text": self.evidence_text,
            "bbox": self.bbox,
            "reason": self.reason,
            "page_number": self.page_number,
            "doc_id": self.doc_id,
            "model": self.model,
            "conflicts": [candidate.to_dict() for candidate in self.conflicts],
        }

PAGE_TYPE_ALIASES = {
    "封面": "cover",
    "目录": "toc",
    "设计说明": "design_notes",
    "数量表": "quantity_table",
    "工程数量表": "quantity_table",
    "数量汇总表": "quantity_table",
    "桥型总体布置图": "general_arrangement",
    "总体布置图": "general_arrangement",
    "平面图": "plan_elevation",
    "立面图": "plan_elevation",
    "主梁横断面": "girder_section",
    "横断面": "girder_section",
    "桥台": "abutment",
    "桥墩": "pier",
    "盖梁配筋": "cap_beam_reinforcement",
    "桩基": "pile",
    "支座": "bearing",
    "附属构造": "appurtenance",
    "封底": "backcover",
}


def normalize_page_classification(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "page_type": "unknown",
            "title": "",
            "bridge_hint": "",
            "confidence": 0.0,
            "evidence_text": "",
            "reason": "视觉后端未返回 JSON 对象",
            "raw_page_type": "",
        }
    raw_type = normalize_text(payload.get("page_type"))
    page_type = raw_type if raw_type in PAGE_TYPES else PAGE_TYPE_ALIASES.get(raw_type, "unknown")
    if page_type == "unknown" and raw_type:
        for alias, canonical in PAGE_TYPE_ALIASES.items():
            if alias in raw_type:
                page_type = canonical
                break
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "page_type": page_type,
        "title": normalize_text(payload.get("title")),
        "bridge_hint": normalize_text(payload.get("bridge_hint")),
        "confidence": max(0.0, min(1.0, confidence)),
        "evidence_text": normalize_text(payload.get("evidence_text")),
        "reason": normalize_text(payload.get("reason")),
        "raw_page_type": raw_type,
    }


def classify_page(
    client: VisionBackend,
    image: str | bytes,
    *,
    context: str = "",
) -> dict[str, Any]:
    prompt = CLASSIFY_PAGE_PROMPT
    if context:
        prompt = f"{prompt}\n页面上下文：{context}"
    payload = client.analyze_image(
        image,
        prompt,
        json_schema=page_classification_schema(),
    )
    return normalize_page_classification(payload)


def extract_page_fields(
    client: VisionBackend,
    image: str | bytes,
    *,
    bridge_hint: str = "",
    page_type: str = "unknown",
    field_codes: Iterable[str] = ALL_FIELD_CODES,
) -> list[FieldCandidate]:
    payload = client.analyze_image(
        image,
        bridge_extraction_prompt(
            bridge_hint=bridge_hint,
            page_type=page_type,
            field_codes=field_codes,
        ),
        json_schema=bridge_field_schema(field_codes),
    )
    fields = payload.get("fields", []) if isinstance(payload, dict) else []
    allowed = {code for code in field_codes if code in ALL_FIELD_CODES}
    candidates = []
    for item in fields:
        if not isinstance(item, dict) or normalize_text(item.get("field_code")) not in allowed:
            continue
        candidates.append(FieldCandidate.from_mapping(item, model=backend_model_name(client)))
    return candidates


def _values_equal(left: Any, right: Any, numeric_tolerance: float = 1e-6) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    try:
        left_number = float(left)
        right_number = float(right)
    except (TypeError, ValueError):
        return normalize_text(left) == normalize_text(right)
    return abs(left_number - right_number) <= numeric_tolerance


def merge_field_candidates(
    candidates: Iterable[FieldCandidate],
    *,
    minimum_confidence: float = 0.65,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[FieldCandidate]] = {}
    for candidate in candidates:
        if candidate.field_code:
            grouped.setdefault(candidate.field_code, []).append(candidate)

    merged: dict[str, dict[str, Any]] = {}
    for field_code, items in grouped.items():
        ordered = sorted(items, key=lambda item: item.score(), reverse=True)
        best = ordered[0]
        conflicts = [
            item for item in ordered[1:]
            if not _values_equal(best.normalized_value, item.normalized_value)
        ]
        best.conflicts = conflicts
        review_required = (
            best.state in {"unknown", "missing", "conflict"}
            or best.confidence < minimum_confidence
            or bool(conflicts)
        )
        result = best.to_dict()
        result["review_required"] = review_required
        merged[field_code] = result
    return merged


def candidate_payloads_to_objects(
    payloads: Iterable[dict[str, Any]],
    *,
    doc_id: str = "",
    page_number: int | None = None,
    model: str = "",
) -> list[FieldCandidate]:
    return [
        FieldCandidate.from_mapping(
            payload,
            doc_id=doc_id,
            page_number=page_number,
            model=model,
        )
        for payload in payloads
    ]
