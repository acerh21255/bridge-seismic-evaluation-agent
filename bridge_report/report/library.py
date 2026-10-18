"""Generic figures and verbatim fragments extracted from the reference report (see tools/build_template.py)."""
import json
from functools import lru_cache

from ..paths import LIBRARY_DIR


@lru_cache(maxsize=1)
def manifest():
    return json.loads((LIBRARY_DIR / 'manifest.json').read_text(encoding='utf-8'))


def figure_path(name):
    entry = next((f for f in manifest()['figures'] if f['name'] == name), None)
    return LIBRARY_DIR / entry['file'] if entry else None


def fragment_names():
    return [f['name'] for f in manifest()['fragments']]
