"""Deterministic seismic verification workflow for handoff contract v2.

Demands and capacities come from verified upstream solvers. This module checks completeness and
consistency, then applies the project gate order (design spec section 6):
E1 → E2 pier yield → pile capacity protection → pier/pile shear → bearings, measures and pile caps
→ ductility of plastic piers; detailing is judged independently; an optional retrofit stage re-checks
listed items on a new model revision. Only E1, pile yield and shear failures stop later gates.
"""
import math

from ..contract.evidence import verify_sources
from ..contract.schema import schema_issues
from .rules import DUCTILITY_KINDS, KINDS_BY_COMPONENT, LEVELS_BY_KIND, RULES, UNITS
from .terms import COMPONENT_LABELS, DIRECTION_LABELS, KIND_LABELS, STATUS_LABELS, verdict

DIRECTIONS = ('longitudinal', 'transverse')
GATES = (('handoff', '交接校验'), ('e1', 'E1 验算'), ('e2_pier', 'E2 桥墩屈服'), ('e2_pile', '桩基能力保护'),
         ('shear', '墩桩抗剪'), ('bearing', '支座与专项'), ('pilecap', '承台验算'), ('detailing', '构造措施'),
         ('ductility', '延性验算'), ('retrofit', '加固复核'))
GATE_TITLES = dict(GATES)
BEARING_GATE_KINDS = ('bearing_displacement', 'bearing_sliding', 'measures', 'additional')


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _key(record):
    return record['component'], record['direction'], record['level'], record['kind']


def _ratio(demand, capacity):
    if demand is None or capacity is None or demand <= 0:
        return None
    return round(capacity / demand, RULES['ratio_decimals'])


def gate_for(kind, level, component_kind):
    if level == 'E1':
        return 'e1'
    if kind == 'e2_moment':
        return 'e2_pier' if component_kind == 'pier' else 'e2_pile'
    if kind == 'shear':
        return 'shear'
    if kind in DUCTILITY_KINDS:
        return 'ductility'
    return 'bearing'


# ---------------------------------------------------------------------------------------------
# Package-level validation: any problem here means the data cannot be judged at all.
# ---------------------------------------------------------------------------------------------
def validate(package, base_dir=None):
    if not isinstance(package, dict):
        return ['交接包顶层必须是 JSON 对象']
    issues = schema_issues(package)
    if issues:
        return issues
    sources = package['sources']
    if package['analysis']['converged'] is not True:
        issues.append('analysis.converged：第三步分析未确认完成，不能开展判定')
    scope = package['scope_review']
    if scope['approved'] is not True:
        issues.append('scope_review：验算构件范围未经确认')
    if scope['evidence'] not in sources:
        issues.append('scope_review.evidence：范围确认证据不存在')
    issues += verify_sources(package, base_dir)

    components = {}
    for component in package['components']:
        if component['id'] in components:
            issues.append(f"components：构件编号 {component['id']} 重复")
        components[component['id']] = component
        if component['kind'] in ('pier', 'pile', 'bearing', 'measure') and set(component['directions']) != set(DIRECTIONS):
            issues.append(f"components.{component['id']}：{COMPONENT_LABELS[component['kind']]}必须同时覆盖纵横桥向")
    for component in components.values():
        if component['kind'] == 'pile':
            parent = components.get(component.get('parent_pier'))
            if parent is None or parent['kind'] != 'pier':
                issues.append(f"components.{component['id']}：桩基缺少关联桥墩（parent_pier）")
    kinds = {c['kind'] for c in components.values()}
    for needed in ('pier', 'pile', 'bearing'):
        if needed not in kinds:
            issues.append(f'components：常规桥验算范围缺少{COMPONENT_LABELS[needed]}构件')

    actions = {}
    for action in package.get('actions', []):
        if action['id'] in actions:
            issues.append(f"actions：成组内力编号 {action['id']} 重复")
        actions[action['id']] = action
        if action['component'] not in components:
            issues.append(f"actions.{action['id']}：构件 {action['component']} 不存在")

    issues += _validate_checks(package['checks'], components, actions, sources, package['model_revision'], 'checks')

    record_keys = {_key(r) for r in package['checks']}
    declared = set()
    for i, declaration in enumerate(package.get('not_applicable', [])):
        key = _key(declaration)
        where = f'not_applicable[{i}]'
        if declaration['component'] not in components:
            issues.append(f"{where}：构件 {declaration['component']} 不存在")
        if declaration['evidence'] not in sources:
            issues.append(f'{where}：不适用声明缺少证据')
        if key in record_keys:
            issues.append(f'{where}：{_describe(key, components)} 同时存在验算记录与不适用声明')
        if key in declared:
            issues.append(f'{where}：不适用声明重复')
        declared.add(key)

    retrofit = package.get('retrofit')
    if retrofit:
        if retrofit['model_revision'] == package['model_revision']:
            issues.append('retrofit.model_revision：加固模型版本必须与原状模型版本不同')
        issues += _validate_checks(retrofit['checks'], components, actions, sources, retrofit['model_revision'],
                                   'retrofit.checks', retrofit=True)

    for i, cap in enumerate(package.get('pilecap', {}).get('checks', [])):
        for name in ('demand', 'capacity'):
            value = cap.get(name)
            if value is not None and (not _finite(value) or value < 0):
                issues.append(f'pilecap.checks[{i}]：{name} 数值无效（须为非负有限数）')
        if cap.get('evidence') and cap['evidence'] not in sources:
            issues.append(f"pilecap.checks[{i}]：证据 {cap['evidence']} 不存在")
    return issues


def _describe(key, components):
    component, direction, level, kind = key
    label = components.get(component, {}).get('label', component)
    return f'{label} {DIRECTION_LABELS.get(direction, direction)} {level} {KIND_LABELS.get(kind, kind)}'


def _validate_checks(records, components, actions, sources, revision, where, retrofit=False):
    issues = []
    seen = set()
    stage = '加固' if retrofit else '原状'
    for i, record in enumerate(records):
        loc = f'{where}[{i}]'
        key = _key(record)
        if key in seen:
            issues.append(f'{loc}：验算记录重复（{_describe(key, components)}）')
        seen.add(key)
        component = components.get(record['component'])
        if component is None:
            issues.append(f"{loc}：构件 {record['component']} 不存在")
            continue
        kind = record['kind']
        if kind not in KINDS_BY_COMPONENT[component['kind']]:
            issues.append(f"{loc}：{COMPONENT_LABELS[component['kind']]}不应包含{KIND_LABELS[kind]}验算")
        if record['level'] not in LEVELS_BY_KIND[kind]:
            issues.append(f"{loc}：{KIND_LABELS[kind]}不属于 {record['level']} 水准验算内容")
        if record['direction'] not in component['directions']:
            issues.append(f"{loc}：构件 {component['id']} 未声明{DIRECTION_LABELS[record['direction']]}")
        if record['unit'] not in UNITS[kind]:
            issues.append(f"{loc}：单位 {record['unit']} 与验算类型{KIND_LABELS[kind]}不符（应为 {'/'.join(UNITS[kind])}）")
        for name in ('demand', 'capacity'):
            value = record.get(name)
            if value is not None and (not _finite(value) or value < 0):
                issues.append(f'{loc}：{name} 数值无效（须为非负有限数）')
        if 'phi' in record and not _finite(record['phi']):
            issues.append(f'{loc}：强度折减系数 phi 数值无效')
        if record.get('capacity') == 0:
            issues.append(f'{loc}：capacity 数值无效（容量不能为 0）')
        if record['model_revision'] != revision:
            issues.append(f"{loc}：模型版本 {record['model_revision']} 与{stage}模型版本 {revision} 不一致（禁止混用模型或加固版本）")
        if record['evidence'] not in sources:
            issues.append(f"{loc}：证据 {record['evidence']} 不存在")
        if kind == 'e1_capacity':
            issues += _validate_e1(record, actions, loc, require_action=not retrofit)
        elif record.get('action_id'):
            issues += _validate_action_link(record, actions, loc)
        strength = record.get('overstrength')
        if strength is not None:
            if strength['evidence'] not in sources:
                issues.append(f'{loc}：超强弯矩复算证据不存在')
            if not _finite(strength['factor']) or not _finite(strength['demand']) or strength['demand'] < 0:
                issues.append(f'{loc}：超强弯矩复算数值无效')
    return issues


def _validate_action_link(record, actions, loc):
    action = actions.get(record['action_id'])
    if action is None:
        return [f"{loc}：关联成组内力 {record['action_id']} 不存在"]
    same = (action['component'], action['direction'], action['level']) == (record['component'], record['direction'], record['level'])
    if not same or action['combination'] != record.get('combination'):
        return [f'{loc}：验算记录与成组内力的构件、方向、水准或组合不一致']
    return []


def _validate_e1(record, actions, loc, require_action):
    issues = []
    if record.get('method') != 'constant_eccentricity':
        issues.append(f'{loc}：E1 截面承载力须采用等偏心距路径（constant_eccentricity），不能以纯轴压容量替代')
    pair = record.get('paired_N_M') or {}
    if not _finite(pair.get('N_kN')) or not _finite(pair.get('M_kNm')):
        issues.append(f'{loc}：E1 缺少同一工况的配对轴力与弯矩（paired_N_M）')
    else:
        if pair['N_kN'] <= 0:
            issues.append(f'{loc}：配对轴力为拉力或零，超出本流程适用范围，需受拉专用模块')
        if record.get('demand') is not None and pair['N_kN'] != record['demand']:
            issues.append(f'{loc}：E1 需求轴力与配对轴力不一致')
    if not record.get('action_id'):
        if require_action:
            issues.append(f'{loc}：E1 记录缺少关联成组内力 action_id')
        return issues
    issues += _validate_action_link(record, actions, loc)
    action = actions.get(record['action_id'])
    if action and pair and (action['N_kN'] != pair.get('N_kN') or action['M_kNm'] != pair.get('M_kNm')):
        issues.append(f'{loc}：E1 配对内力与上游成组内力记录不一致')
    return issues


# ---------------------------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------------------------
def _valid_overstrength(strength, sources):
    return (isinstance(strength, dict) and strength.get('basis') == 'system_equilibrium' and strength.get('reviewed') is True
            and strength.get('evidence') in sources and _finite(strength.get('factor'))
            and strength['factor'] >= RULES['overstrength_min_factor'] and _finite(strength.get('demand')) and strength['demand'] >= 0)


class _Stage:
    def __init__(self, engine, name, records):
        self.engine = engine
        self.name = name
        self.records = {_key(r): r for r in records}
        self.done = {}
        self.plastic = []

    # -- item construction ---------------------------------------------------------------------
    def emit(self, key, gate, status, reason, record=None, **extra):
        component, direction, level, kind = key
        comp = self.engine.components[component]
        record = record or {}
        pair = record.get('paired_N_M') or {}
        demand = extra.pop('demand', record.get('demand'))
        capacity = extra.pop('capacity', record.get('capacity'))
        item = {
            'id': f'{self.name}|{component}|{direction}|{level}|{kind}',
            'stage': self.name, 'gate': gate, 'final': True,
            'component': component, 'component_kind': comp['kind'], 'component_label': comp['label'],
            'section_label': record.get('section_label') or comp['label'],
            'direction': direction, 'direction_label': DIRECTION_LABELS[direction],
            'level': level, 'kind': kind, 'kind_label': KIND_LABELS[kind], 'title': record.get('title'),
            'demand': demand, 'capacity': capacity, 'unit': record.get('unit') or UNITS[kind][0],
            'moment_kNm': pair.get('M_kNm'), 'axial_kN': pair.get('N_kN') if kind == 'e1_capacity' else record.get('axial_kN'),
            'ratio': _ratio(demand, capacity) if status in ('PASS', 'FAIL', 'PLASTIC') else None,
            'status': status, 'status_label': STATUS_LABELS[status], 'verdict': verdict(kind, comp['kind'], status),
            'reason': reason, 'provisional': False, 'limit_basis': record.get('limit_basis'), 'phi': 1.0,
            'overstrength': None, 'direct_demand': None, 'before': None,
            'evidence': record.get('evidence'), 'locator': record.get('locator'),
            'combination': record.get('combination'), 'model_revision': record.get('model_revision'),
        }
        item.update(extra)
        self.done[key] = item
        self.engine.items.append(item)
        return item

    def not_applicable(self, key, gate):
        declaration = self.engine.na[key]
        return self.emit(key, gate, 'NA', declaration['reason'], {'evidence': declaration['evidence']})

    def skip(self, key, gate, reason):
        return self.emit(key, gate, 'SKIPPED', reason, self.records.get(key))

    # -- comparisons ----------------------------------------------------------------------------
    def compare(self, key, gate):
        if key in self.engine.na:
            return self.not_applicable(key, gate)
        record = self.records.get(key)
        if record is None:
            return self.emit(key, gate, 'BLOCKED', '缺少验算记录，需第三步补充')
        component_kind = self.engine.components[key[0]]['kind']
        kind = key[3]
        demand, capacity = record['demand'], record['capacity']
        extra = {}
        if kind == 'bearing_displacement' and capacity is None and record.get('limit_status') == 'not_provided':
            capacity = RULES['bearing_displacement_provisional_limit_m']
            extra = {'provisional': True, 'limit_basis': RULES['bearing_displacement_provisional_basis']}
        strength = record.get('overstrength')
        if kind == 'shear' and strength is not None:
            if not _valid_overstrength(strength, self.engine.sources):
                return self.emit(key, gate, 'BLOCKED', '超强弯矩体系传力复算资料不完整或未经复核', record)
            extra.update(direct_demand=demand, overstrength=strength)
            demand = strength['demand']
        if demand is None or capacity is None:
            return self.emit(key, gate, 'BLOCKED', '缺少需求或容量数值，需第三步补充', record, demand=demand, capacity=capacity)
        phi = record.get('phi', 1.0)
        effective = capacity * phi
        if phi != 1.0:
            extra.update(phi=phi, ratio=_ratio(demand, effective))
        if effective >= demand:
            status = 'PASS'
            reason = '弯矩未超过等效屈服弯矩，保持弹性' if kind == 'e2_moment' else '能力不小于需求'
        elif kind == 'e2_moment' and component_kind == 'pier':
            status, reason = 'PLASTIC', '弯矩大于等效屈服弯矩，进入塑性，需开展延性验算'
        else:
            status = 'FAIL'
            reason = {'e1_capacity': '截面承载力小于最不利轴力需求', 'shear': '抗剪能力小于剪力需求'}.get(kind, '能力小于需求')
        if extra.get('provisional'):
            reason += '（采用暂定限值）'
        return self.emit(key, gate, status, reason, record, demand=demand, capacity=capacity, **extra)

    def pile_moment(self, key, plastic):
        gate = 'e2_pile'
        if key in self.engine.na:
            return self.not_applicable(key, gate)
        record = self.records.get(key)
        if record is None:
            return self.emit(key, gate, 'BLOCKED', '缺少验算记录，需第三步补充')
        demand, capacity = record['demand'], record['capacity']
        if demand is None or capacity is None:
            return self.emit(key, gate, 'BLOCKED', '缺少需求或容量数值，需第三步补充', record)
        if demand <= capacity:
            return self.emit(key, gate, 'PASS', '桩基弯矩未超过等效屈服弯矩，满足能力保护要求', record)
        parent = self.engine.components[key[0]]['parent_pier']
        if (parent, key[1]) not in plastic:
            return self.emit(key, gate, 'FAIL', '关联桥墩未进入塑性，桩基弯矩超过等效屈服弯矩（进入屈服），不满足能力保护要求', record)
        strength = record.get('overstrength')
        if not _valid_overstrength(strength, self.engine.sources):
            return self.emit(key, gate, 'BLOCKED', '关联桥墩已进入塑性，桩基直接弯矩需求超过等效屈服弯矩；'
                                                   '需第三步按超强弯矩开展体系传力复算后重新交接', record)
        extra = {'direct_demand': demand, 'overstrength': strength, 'demand': strength['demand']}
        if strength['demand'] <= capacity:
            return self.emit(key, gate, 'PASS', '按超强弯矩体系传力复算后，桩基弯矩未超过等效屈服弯矩', record, **extra)
        return self.emit(key, gate, 'FAIL', '按超强弯矩体系传力复算后，桩基弯矩仍超过等效屈服弯矩（进入屈服），不满足能力保护要求',
                         record, **extra)

    def run(self, keys, gate):
        statuses = []
        for key in keys:
            if key in self.done:
                continue
            statuses.append(self.compare(key, gate)['status'])
        return _worst(statuses)

    def skip_remaining(self, reason):
        for key in self.engine.e2_keys() + [k for k in self.records if k[2] == 'E2']:
            if key not in self.done:
                comp_kind = self.engine.components[key[0]]['kind']
                self.skip(key, gate_for(key[3], key[2], comp_kind), reason)


def _worst(statuses):
    for status in ('FAIL', 'BLOCKED', 'PLASTIC'):
        if status in statuses:
            return status
    return 'PASS'


class _Engine:
    def __init__(self, package):
        self.p = package
        self.components = {c['id']: c for c in package['components']}
        self.sources = package['sources']
        self.na = {_key(n): n for n in package.get('not_applicable', [])}
        self.items = []
        self.stops = []

    def members(self, *kinds):
        return [c for c in self.components.values() if c['kind'] in kinds]

    def keys(self, kinds_of_component, level, kinds):
        return [(c['id'], d, level, k) for c in self.members(*kinds_of_component) for d in c['directions'] for k in kinds]

    def e2_keys(self):
        return (self.keys(('pier',), 'E2', ('e2_moment',)) + self.keys(('pile',), 'E2', ('e2_moment',))
                + self.keys(('pier', 'pile'), 'E2', ('shear',)) + self.keys(('bearing',), 'E2', ('bearing_displacement', 'bearing_sliding'))
                + self.keys(('measure',), 'E2', ('measures',)) + self.keys(('capbeam', 'tiebeam'), 'E2', ('additional',)))

    def stop(self, stage, gate, reason):
        self.stops.append({'stage': stage.name, 'gate': gate, 'reason': reason})
        stage.skip_remaining(reason + '，本项未开展')
        for check in self.p.get('pilecap', {}).get('checks', []):
            self.pilecap_item(stage.name, check, 'SKIPPED', reason + '，本项未开展')

    # -- original stage ---------------------------------------------------------------------------
    def run_original(self):
        stage = _Stage(self, 'original', self.p['checks'])
        e1_keys = (self.keys(('pier', 'pile'), 'E1', ('e1_capacity',))
                   + self.keys(('bearing',), 'E1', ('bearing_displacement', 'bearing_sliding'))
                   + [k for k in stage.records if k[2] == 'E1'])
        if stage.run(e1_keys, 'e1') != 'PASS':
            failed = [i for i in self.items if i['gate'] == 'e1' and i['status'] in ('FAIL', 'BLOCKED')]
            self.stop(stage, 'e1', 'E1 验算存在' + ('不满足项' if any(i['status'] == 'FAIL' for i in failed) else '待补正项')
                      + '（' + '、'.join(_short(i) for i in failed[:4]) + '），E2 地震作用下的验算未开展')
            return stage
        stage.run(self.keys(('pier',), 'E2', ('e2_moment',)), 'e2_pier')
        plastic = {(k[0], k[1]) for k, i in stage.done.items() if k[3] == 'e2_moment' and i['status'] == 'PLASTIC'}
        stage.plastic = sorted(plastic)
        pile_statuses = [stage.pile_moment(key, plastic)['status'] for key in self.keys(('pile',), 'E2', ('e2_moment',))]
        if 'FAIL' in pile_statuses:
            failed = [i for i in self.items if i['gate'] == 'e2_pile' and i['status'] == 'FAIL']
            self.stop(stage, 'e2_pile', '桩基进入屈服，不满足能力保护要求（' + '、'.join(_short(i) for i in failed) + '），后续验算未开展')
            return stage
        if stage.run(self.keys(('pier', 'pile'), 'E2', ('shear',)), 'shear') == 'FAIL':
            failed = [i for i in self.items if i['gate'] == 'shear' and i['status'] == 'FAIL']
            self.stop(stage, 'shear', '墩桩抗剪不满足（' + '、'.join(_short(i) for i in failed) + '），后续验算未开展')
            return stage
        bearing_keys = (self.keys(('bearing',), 'E2', ('bearing_displacement', 'bearing_sliding'))
                        + self.keys(('measure',), 'E2', ('measures',)) + self.keys(('capbeam', 'tiebeam'), 'E2', ('additional',))
                        + [k for k in stage.records if k[2] == 'E2' and k[3] in BEARING_GATE_KINDS])
        stage.run(bearing_keys, 'bearing')
        for check in self.p.get('pilecap', {}).get('checks', []):
            self.pilecap_item(stage.name, check)
        self.ductility(stage, plastic)
        for key, record in stage.records.items():
            if key not in stage.done and key[3] in DUCTILITY_KINDS:
                stage.emit(key, 'ductility', 'NA', '该桥墩在此方向未进入塑性，无需开展延性验算', record)
        return stage

    def ductility(self, stage, plastic):
        for pier, direction in sorted(plastic):
            hinge = stage.compare((pier, direction, 'E2', 'hinge_shear'), 'ductility')
            for kind in ('ductility_displacement', 'ductility_reinforcement'):
                key = (pier, direction, 'E2', kind)
                if hinge['status'] == 'FAIL' and key not in stage.records and key not in self.na:
                    stage.emit(key, 'ductility', 'SKIPPED', '塑性铰区抗剪不满足，该项延性验算未开展')
                else:
                    stage.compare(key, 'ductility')

    def pilecap_item(self, stage_name, check, status=None, reason=None):
        demand, capacity = check.get('demand'), check.get('capacity')
        if status is None:
            if demand is None or capacity is None:
                status, reason = 'BLOCKED', '缺少需求或容量数值，需第三步补充'
            elif capacity >= demand:
                status, reason = 'PASS', '承载力不小于需求'
            else:
                status, reason = 'FAIL', '承载力小于需求'
        item = {
            'id': f"{stage_name}|pilecap|{check['id']}", 'stage': stage_name, 'gate': 'pilecap', 'final': True,
            'component': None, 'component_kind': 'pilecap', 'component_label': '承台', 'section_label': check['title'],
            'direction': check['direction'], 'direction_label': DIRECTION_LABELS[check['direction']], 'level': 'E2',
            'kind': 'pilecap', 'kind_label': check['title'], 'title': check['title'], 'pilecap_id': check['id'],
            'demand': demand, 'capacity': capacity, 'unit': 'kN',
            'ratio': _ratio(demand, capacity) if status in ('PASS', 'FAIL') else None,
            'status': status, 'status_label': STATUS_LABELS[status], 'verdict': verdict('pilecap', 'pilecap', status),
            'reason': reason, 'provisional': False, 'evidence': check.get('evidence'), 'before': None,
        }
        self.items.append(item)
        return item

    # -- detailing (independent of the analysis gates) ---------------------------------------------
    def detailing(self):
        data = self.p.get('detailing') or {}
        rows1 = (data.get('level1') or {}).get('rows') or []
        if not (rows1 or data.get('level2') or data.get('level3')):
            self.items.append(self._detail_item('detailing', 'missing', '构造措施', None, 'BLOCKED', '缺少构造措施验算资料，需补充'))
            return
        for n, row in enumerate(rows1):
            ok = row['design_cm'] >= row['required_cm']
            self.items.append(self._detail_item('edge_distance', f'level1-{n}', row['location'], 'level1', 'PASS' if ok else 'FAIL',
                                                '设计边距不小于规范要求' if ok else '设计边距小于规范要求',
                                                demand=row['required_cm'], capacity=row['design_cm'], unit='cm', row=row))
        for group in ('level2', 'level3'):
            for n, row in enumerate(data.get(group) or []):
                status = {True: 'PASS', False: 'FAIL', None: 'BLOCKED'}[row['satisfied']]
                reason = {'PASS': '满足规范要求', 'FAIL': '不满足规范要求', 'BLOCKED': '满足情况待确认'}[status]
                self.items.append(self._detail_item('detailing', f'{group}-{n}', row.get('topic') or f"第{row['clause']}条", group,
                                                    status, reason, row=row))

    def _detail_item(self, kind, ident, label, group, status, reason, demand=None, capacity=None, unit=None, row=None):
        return {
            'id': f'original|detailing|{ident}', 'stage': 'original', 'gate': 'detailing', 'final': True,
            'component': None, 'component_kind': 'detailing', 'component_label': label, 'section_label': label,
            'direction': None, 'direction_label': None, 'level': None, 'kind': kind, 'kind_label': KIND_LABELS[kind],
            'group': group, 'title': label, 'demand': demand, 'capacity': capacity, 'unit': unit,
            'ratio': None, 'status': status, 'status_label': STATUS_LABELS[status],
            'verdict': verdict(kind, 'detailing', status), 'reason': reason, 'provisional': False, 'row': row, 'before': None,
        }

    # -- retrofit stage ---------------------------------------------------------------------------
    def run_retrofit(self, original):
        retrofit = self.p.get('retrofit')
        if not retrofit:
            return None
        stage = _Stage(self, 'retrofit', retrofit['checks'])
        plastic = set(original.plastic)
        order = {'e1_capacity': 0, 'bearing_displacement': 0, 'bearing_sliding': 0, 'e2_moment': 1, 'shear': 3,
                 'measures': 4, 'additional': 4, 'hinge_shear': 5, 'ductility_displacement': 6, 'ductility_reinforcement': 6}
        keys = sorted(stage.records, key=lambda k: (0 if k[2] == 'E1' else 1, order[k[3]],
                                                    self.components[k[0]]['kind'] != 'pier', k))
        for key in keys:
            component_kind = self.components[key[0]]['kind']
            if key[3] == 'e2_moment' and component_kind == 'pile':
                item = stage.pile_moment(key, plastic)
            elif key[3] in DUCTILITY_KINDS and (key[0], key[1]) not in plastic:
                item = stage.emit(key, 'retrofit', 'NA', '加固后该桥墩在此方向保持弹性，无需开展延性验算', stage.records[key])
            else:
                item = stage.compare(key, 'retrofit')
            item['origin_gate'] = gate_for(key[3], key[2], component_kind)
            item['gate'] = 'retrofit'
            if key[3] == 'e2_moment' and component_kind == 'pier':
                (plastic.add if item['status'] == 'PLASTIC' else plastic.discard)((key[0], key[1]))
            previous = original.done.get(key)
            if previous is not None:
                previous['final'] = False
                item['before'] = {k: previous[k] for k in ('demand', 'capacity', 'ratio', 'status', 'verdict')}
        stage.plastic = sorted(plastic)
        for pier, direction in stage.plastic:
            for kind in DUCTILITY_KINDS:
                key = (pier, direction, 'E2', kind)
                if key not in stage.done and key not in original.done:
                    stage.emit(key, 'retrofit', 'BLOCKED', '加固后桥墩进入塑性，缺少该项延性验算记录', origin_gate='ductility')
        for pier, direction in set(original.plastic) - plastic:
            for kind in DUCTILITY_KINDS:
                previous = original.done.get((pier, direction, 'E2', kind))
                if previous is not None and previous['final']:
                    previous['final'] = False
                    previous['superseded'] = '加固后该桥墩在此方向保持弹性'
        return stage

    # -- summary ------------------------------------------------------------------------------------
    def result(self, original, retrofit):
        final = [i for i in self.items if i['final']]
        statuses = [i['status'] for i in final]
        if 'FAIL' in statuses:
            status = 'FAIL'
        elif 'BLOCKED' in statuses or 'SKIPPED' in statuses:
            status = 'BLOCKED'
        else:
            status = 'PASS'
        provisional = [i['id'] for i in final if i.get('provisional')]
        plastic = [self._plastic_entry(original, p) for p in original.plastic]
        result = {
            'status': status, 'status_label': STATUS_LABELS[status], 'evaluated': True, 'engineering_release': False,
            'reason': self.reason(status, final, provisional), 'issues': [], 'items': self.items,
            'gates': self.gates(retrofit is not None), 'plastic': plastic, 'stops': self.stops, 'provisional': provisional,
            'has_retrofit': retrofit is not None,
            'counts': {s: statuses.count(s) for s in STATUS_LABELS},
        }
        if retrofit is not None:
            result['plastic_after'] = [self._plastic_entry(retrofit, p, fallback=original) for p in retrofit.plastic]
        return result

    @staticmethod
    def _plastic_entry(stage, pair, fallback=None):
        key = (pair[0], pair[1], 'E2', 'e2_moment')
        item = stage.done.get(key) or (fallback.done.get(key) if fallback else None)
        return {'component': pair[0], 'direction': pair[1], 'section_label': item['section_label'] if item else pair[0]}

    def reason(self, status, final, provisional):
        if status == 'PASS':
            note = f'（其中 {len(provisional)} 项支座位移采用暂定限值）' if provisional else ''
            return '声明范围内各项验算满足本流程要求' + note + '；工程签发仍需计算复核与人工审定'
        if self.stops and not self.p.get('retrofit'):
            return self.stops[0]['reason']
        wanted = 'FAIL' if status == 'FAIL' else None
        picked = [i for i in final if (i['status'] == wanted if wanted else i['status'] in ('BLOCKED', 'SKIPPED'))]
        head = '存在不满足项' if status == 'FAIL' else '资料待补正'
        more = f' 等 {len(picked)} 项' if len(picked) > 3 else ''
        return f"{head}：{'；'.join(_short(i) for i in picked[:3])}{more}"

    def gates(self, has_retrofit):
        summaries = [{'id': 'handoff', 'title': GATE_TITLES['handoff'], 'status': 'PASS', 'summary': '合同、证据与版本检查通过',
                      'counts': {}}]
        for gate_id, title in GATES[1:]:
            if gate_id == 'retrofit' and not has_retrofit:
                continue
            members = [i for i in self.items if i['gate'] == gate_id]
            summaries.append({'id': gate_id, 'title': title, 'status': _gate_status(gate_id, members),
                              'summary': _gate_summary(gate_id, members),
                              'counts': {s: sum(1 for i in members if i['status'] == s) for s in STATUS_LABELS if any(i['status'] == s for i in members)}})
        return summaries


GROUP_LABELS = {'level1': '一级抗震措施', 'level2': '二级抗震措施', 'level3': '三级抗震措施'}


def _short(item):
    if item['kind'] in ('detailing', 'edge_distance'):
        return f"{GROUP_LABELS.get(item.get('group'), '构造措施')}：{item['section_label']}{item['verdict']}"
    direction = f"（{item['direction_label']}）" if item.get('direction_label') else ''
    if item['kind'] == 'pilecap':
        return f"{item['title']}{direction}{item['verdict']}"
    return f"{item['section_label']}{direction}{item['kind_label']}{item['verdict']}"


def _gate_status(gate_id, members):
    statuses = [i['status'] for i in members]
    if not statuses or all(s == 'NA' for s in statuses):
        return 'NA'
    if all(s == 'SKIPPED' for s in statuses):
        return 'SKIPPED'
    if 'FAIL' in statuses:
        return 'FAIL'
    if 'BLOCKED' in statuses:
        return 'BLOCKED'
    if 'PLASTIC' in statuses and gate_id == 'e2_pier':
        return 'PLASTIC'
    if 'SKIPPED' in statuses:
        return 'BLOCKED'
    return 'PASS'


def _gate_summary(gate_id, members):
    if not members:
        return {'ductility': '无桥墩进入塑性，不需开展', 'pilecap': '未提供承台验算资料', 'retrofit': '无加固复核'}.get(gate_id, '无验算项')
    counts = {s: sum(1 for i in members if i['status'] == s) for s in STATUS_LABELS}
    judged = len(members) - counts['NA'] - counts['SKIPPED']
    if counts['SKIPPED'] == len(members):
        return '前置门禁未通过，未开展'
    parts = [f"满足 {counts['PASS']}/{judged}"] if judged else []
    for status in ('PLASTIC', 'FAIL', 'BLOCKED', 'SKIPPED', 'NA'):
        if counts[status]:
            parts.append(f'{STATUS_LABELS[status]} {counts[status]}')
    text = '，'.join(parts)
    if gate_id != 'retrofit' and any(not i['final'] and i['status'] in ('FAIL', 'SKIPPED', 'BLOCKED') for i in members):
        text += '（已由加固复核替代）'
    return text


def blocked(issues, reason='第三步交接包未通过数据与证据检查，未开展判定'):
    return {'status': 'BLOCKED', 'status_label': STATUS_LABELS['BLOCKED'], 'evaluated': False, 'engineering_release': False,
            'reason': reason, 'issues': issues, 'items': [], 'plastic': [], 'stops': [], 'provisional': [], 'has_retrofit': False,
            'gates': [{'id': 'handoff', 'title': GATE_TITLES['handoff'], 'status': 'BLOCKED', 'summary': f'问题 {len(issues)} 项',
                       'counts': {}}],
            'counts': {s: 0 for s in STATUS_LABELS}}


def evaluate(package, base_dir=None):
    """Judge a handoff package. Never raises for bad input; returns BLOCKED with issues instead."""
    try:
        issues = validate(package, base_dir)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return blocked([f'交接包结构无效（{type(exc).__name__}），请按模板补正'])
    if issues:
        return blocked(issues)
    engine = _Engine(package)
    original = engine.run_original()
    engine.detailing()
    retrofit = engine.run_retrofit(original)
    return engine.result(original, retrofit)
