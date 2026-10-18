"""Derive demonstration variants from the 76K golden package (spec section 7).

Base B = golden + third-level detailing “限位装置” set as provided, so each variant isolates one branch:
retrofit_pass, elastic, e1_fail, missing, overstrength. Modified records cite the inline evidence
`variant-note`; assets are shared with the golden package.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge_report.contract.evidence import content_hash  # noqa: E402
from bridge_report.contract.package import load_file  # noqa: E402
from bridge_report.engine.gates import evaluate  # noqa: E402
from bridge_report.paths import EXAMPLES_DIR, GOLDEN_DIR, SCENARIOS_DIR  # noqa: E402

GOLDEN_REL = '../golden/76K278+308/'


def find(package, component, direction, level, kind, where='checks'):
    records = package['retrofit']['checks'] if where == 'retrofit' else package['checks']
    return next(r for r in records if (r['component'], r['direction'], r['level'], r['kind']) == (component, direction, level, kind))


def base(golden):
    b = copy.deepcopy(golden)
    limiter = next(i for i in b['detailing']['level3'] if i['clause'] == '11.4.3')
    limiter.update(design='桥台、桥墩设置限位装置', satisfied=True)
    return b


def finish(package, variant_id, title, description, changes, expected):
    package['data_kind'] = 'synthetic_variant'
    package['bridge_id'] = f'G8511-K278+308-{variant_id}'
    package['variant'] = {'id': variant_id, 'title': title, 'base': '76K278+308 金标准（原报告复现）', 'changes': changes}
    revision = f"76K278+308-{variant_id}-demo"
    package['model_revision'] = revision
    for record in package['checks']:
        record['model_revision'] = revision
    if package.get('retrofit'):
        package['retrofit']['model_revision'] = f'{revision}-retrofit'
        for record in package['retrofit']['checks']:
            record['model_revision'] = package['retrofit']['model_revision']
    note = {'variant': variant_id, 'changes': changes, 'statement': '演示变体：数据经人为修改，不代表实桥结论'}
    package['sources']['variant-note'] = {'kind': 'inline', 'title': f'演示变体说明：{title}', 'content': note, 'sha256': content_hash(note)}
    for asset in package['assets']:
        asset['path'] = GOLDEN_REL + asset['path']
    return {'id': variant_id, 'title': title, 'description': description, 'expected_status': expected, 'group': 'variant',
            'file': f'scenarios/{variant_id}.json'}


def mark(record):
    record['evidence'] = 'variant-note'
    record['locator'] = '演示变体修改'
    return record


def build():
    golden = json.loads((GOLDEN_DIR / 'handoff.json').read_text(encoding='utf-8'))
    variants = []

    v = base(golden)
    variants.append((v, finish(v, 'retrofit_pass', '加固后满足', '1#墩底进入塑性，经韧性提升后延性三项满足，限位装置按已设置处理。',
                               ['三级抗震措施“限位装置”改为已设置'], 'PASS')))

    v = base(golden)
    mark(find(v, 'P1', 'longitudinal', 'E2', 'e2_moment'))['demand'] = 5500.0
    v['checks'] = [r for r in v['checks'] if r['kind'] != 'hinge_shear']
    v.pop('retrofit')
    variants.append((v, finish(v, 'elastic', '弹性通过', 'E2 桥墩弯矩均低于等效屈服弯矩，全桥保持弹性，无需延性验算。',
                               ['三级抗震措施“限位装置”改为已设置', '1#墩底 E2 纵桥向弯矩改为 5500 kN·m（低于 5902 kN·m）',
                                '删除延性验算与韧性提升方案'], 'PASS')))

    v = base(golden)
    mark(find(v, 'P1', 'longitudinal', 'E1', 'e1_capacity'))['capacity'] = 4200.0
    v.pop('retrofit')
    variants.append((v, finish(v, 'e1_fail', 'E1强度破坏', '1#墩底 E1 截面承载力低于最不利轴力需求，E2 验算按流程停止。',
                               ['三级抗震措施“限位装置”改为已设置', '1#墩底 E1 纵桥向截面承载力改为 4200 kN（低于需求 4708.7 kN）',
                                '删除韧性提升方案'], 'FAIL')))

    v = base(golden)
    mark(find(v, 'F2', 'transverse', 'E2', 'e2_moment'))['capacity'] = None
    variants.append((v, finish(v, 'missing', '资料缺失', '第三步漏交 2#桩顶横桥向等效屈服弯矩，Agent 列出待补正项。',
                               ['三级抗震措施“限位装置”改为已设置', '删除 2#桩顶 E2 横桥向等效屈服弯矩'], 'BLOCKED')))

    v = base(golden)
    mark(find(v, 'F1', 'longitudinal', 'E2', 'e2_moment'))['demand'] = 4500.0
    variants.append((v, finish(v, 'overstrength', '待超强复算', '1#墩底已进入塑性，1#桩顶弯矩超过等效屈服弯矩，需第三步提交超强弯矩体系传力复算。',
                               ['三级抗震措施“限位装置”改为已设置', '1#桩顶 E2 纵桥向弯矩改为 4500 kN·m（高于 4219 kN·m）'], 'BLOCKED')))

    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    index = [{'id': 'golden-76K', 'title': '76K278+308 原报告复现', 'group': 'golden', 'expected_status': 'FAIL',
              'description': '按原报告数据复现：1#墩底进入塑性并经加固满足延性要求，三级抗震措施中限位装置不满足。',
              'file': 'golden/76K278+308/handoff.json'}]
    for package, entry in variants:
        path = SCENARIOS_DIR / f"{entry['id']}.json"
        path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding='utf-8')
        index.append(entry)
    for entry in index:
        loaded = load_file(EXAMPLES_DIR / entry['file'], root_limit=EXAMPLES_DIR)
        status = evaluate(loaded.data, loaded.base_dir)['status']
        entry['bridge_name'] = f"{loaded.data['project']['route']} {loaded.data['project']['stake']}"
        entry['checks_count'] = len(loaded.data['checks']) + len((loaded.data.get('retrofit') or {}).get('checks', []))
        mark_ok = '✓' if status == entry['expected_status'] else '✗'
        print(f"{mark_ok} {entry['id']:14s} 预期 {entry['expected_status']:7s} 实际 {status}")
        if status != entry['expected_status']:
            raise SystemExit(f"变体 {entry['id']} 判定结果与预期不符")
    (SCENARIOS_DIR / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    build()
