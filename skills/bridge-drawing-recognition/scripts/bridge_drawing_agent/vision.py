"""Provider-neutral vision backend contract.

The bridge drawing agent owns prompts, schemas, orchestration, validation and
output contracts. It deliberately does not call a model provider directly.
Integrators inject a backend that implements ``analyze_image``.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable


class VisionBackendError(RuntimeError):
    pass


class VisionBackendUnavailable(VisionBackendError):
    pass


@runtime_checkable
class VisionBackend(Protocol):
    model: str

    def analyze_image(
        self,
        image: str | Path | bytes,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_schema: dict[str, Any] | None = None,
        detail: str = "high",
        image_mime_type: str | None = None,
    ) -> Any:
        """Return parsed JSON, plain text, or a VisionResponse-like object."""


@dataclass
class VisionResponse:
    content: Any
    raw_text: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    def parsed(self) -> Any:
        if isinstance(self.content, (dict, list)):
            return self.content
        return parse_json_response(self.raw_text or str(self.content))


def parse_json_response(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    starts = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
    if not starts:
        raise VisionBackendError("视觉后端响应中没有可解析的 JSON")
    start = min(starts)
    for end in range(len(cleaned), start, -1):
        candidate = cleaned[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise VisionBackendError("视觉后端响应 JSON 无法解析")

class CallableVisionBackend:
    """Adapt an arbitrary callable into the provider-neutral backend contract."""

    def __init__(self, function: Callable[..., Any], *, model: str = "external-backend"):
        if not callable(function):
            raise TypeError("function must be callable")
        self.function = function
        self.model = model

    def analyze_image(
        self,
        image: str | Path | bytes,
        prompt: str,
        *,
        system_prompt: str | None = None,
        json_schema: dict[str, Any] | None = None,
        detail: str = "high",
        image_mime_type: str | None = None,
    ) -> Any:
        result = self.function(
            image=image,
            prompt=prompt,
            system_prompt=system_prompt,
            json_schema=json_schema,
            detail=detail,
            image_mime_type=image_mime_type,
        )
        if isinstance(result, VisionResponse):
            return result.parsed()
        return result


class NullVisionBackend:
    """Default backend that fails only when a vision call is actually needed."""

    model = "unconfigured"

    def analyze_image(self, *args: Any, **kwargs: Any) -> Any:
        raise VisionBackendUnavailable(
            "未注入视觉后端。核心算法不会直接调用模型 API；"
            "请提供实现 analyze_image(...) 的后端，并通过 --backend 或 "
            "BRIDGE_VISION_BACKEND 注册。"
        )


def load_vision_backend(spec: str | None = None) -> VisionBackend:
    """Load ``module:factory`` from an integrator-owned Python module."""
    import os

    value = spec or os.environ.get("BRIDGE_VISION_BACKEND", "")
    if not value:
        return NullVisionBackend()
    if ":" not in value:
        raise VisionBackendError("视觉后端格式应为 module:factory")
    module_name, factory_name = value.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise VisionBackendError(f"无法导入视觉后端模块: {module_name}") from error
    factory = getattr(module, factory_name, None)
    if not callable(factory):
        raise VisionBackendError(f"视觉后端工厂不可调用: {value}")
    backend = factory()
    if not hasattr(backend, "analyze_image"):
        raise VisionBackendError("视觉后端必须实现 analyze_image(...)")
    return backend


def backend_model_name(backend: Any) -> str:
    return str(
        getattr(backend, "model", "")
        or getattr(getattr(backend, "config", None), "model", "")
    )
