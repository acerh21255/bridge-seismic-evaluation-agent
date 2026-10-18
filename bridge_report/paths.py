"""Filesystem locations shared by the report agent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / 'bridge_report'
REPORT_DIR = PACKAGE_DIR / 'report'
TEMPLATE_DIR = REPORT_DIR / 'template'
LIBRARY_DIR = REPORT_DIR / 'library'
TEMPLATE_DOCX = TEMPLATE_DIR / 'lab_template.docx'
FORMAT_SPEC = TEMPLATE_DIR / 'format_spec.json'

CONTRACTS_DIR = ROOT / 'contracts'
EXAMPLES_DIR = ROOT / 'examples'
GOLDEN_DIR = EXAMPLES_DIR / 'golden' / '76K278+308'
SCENARIOS_DIR = EXAMPLES_DIR / 'scenarios'
REFERENCE_DIR = ROOT / 'templates' / 'reference'
REFERENCE_76K = REFERENCE_DIR / 'G8511 76K278+308 (20m+33m+20m)抗震设计验算报告.docx'
RULES_DOC = ROOT / 'docs' / '报告撰写规范.md'
STATIC_DIR = ROOT / 'static'
BUILD_DIR = ROOT / 'build'
