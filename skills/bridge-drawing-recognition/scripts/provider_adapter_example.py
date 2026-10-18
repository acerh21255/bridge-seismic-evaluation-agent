"""Example integration point for a host-owned vision API.

This file intentionally does not contain a provider SDK, endpoint, or secret.
An integrator replaces ``call_vision_api`` with their own API call and exposes
``factory`` to the bridge drawing agent.
"""

from __future__ import annotations

from typing import Any

from bridge_drawing_agent.vision import CallableVisionBackend


def call_vision_api(
    *,
    image: str | bytes,
    prompt: str,
    system_prompt: str | None,
    json_schema: dict[str, Any] | None,
    detail: str,
    image_mime_type: str | None,
) -> dict[str, Any]:
    """Replace this body with the host environment's model/API call.

    The return value must be parsed JSON, plain text, or ``VisionResponse``.
    """
    raise NotImplementedError("Host must implement call_vision_api")


def factory() -> CallableVisionBackend:
    return CallableVisionBackend(call_vision_api, model="host-configured-model")
