"""JSON Schema validation for handoff contract v2."""
import json
from functools import lru_cache

from jsonschema import Draft202012Validator

from ..paths import CONTRACTS_DIR

SCHEMA_PATH = CONTRACTS_DIR / 'handoff.schema.json'


@lru_cache(maxsize=1)
def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def schema_issues(package, limit=30):
    issues = []
    for error in sorted(validator().iter_errors(package), key=lambda e: list(e.absolute_path)):
        location = '.'.join(map(str, error.absolute_path)) or '根对象'
        issues.append(f'{location}：{error.message}')
        if len(issues) >= limit:
            break
    return issues
