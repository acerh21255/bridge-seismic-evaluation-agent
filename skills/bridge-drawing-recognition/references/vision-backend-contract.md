# Vision Backend Contract

The core agent does not call an API. Integration is a Python factory returning
an object with:

```python
def analyze_image(
    image: str | bytes,
    prompt: str,
    *,
    system_prompt: str | None = None,
    json_schema: dict | None = None,
    detail: str = "high",
    image_mime_type: str | None = None,
) -> dict | list | str | VisionResponse:
    ...
```

Register the factory as `module:factory` through `--backend` or
`BRIDGE_VISION_BACKEND`.

Implementation requirements:

- Accept either an image path or encoded image bytes.
- Forward the supplied prompt and JSON schema.
- Return parsed JSON when possible.
- Return `VisionResponse` when raw text, model name, or usage data must be
  preserved.
- Raise a clear exception on provider failures.
- Do not place credentials or provider-specific code in this repository.

Use `scripts/provider_adapter_example.py` and `bridge_drawing_agent.vision.CallableVisionBackend`
as the reference integration shape.
