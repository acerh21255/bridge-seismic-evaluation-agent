"""Synthetic minimal v2 packages for engine and report tests (not bridge data)."""
import copy

from bridge_report.contract.evidence import content_hash

REVISION = 'synthetic-v1'
SOURCE = {'note': '合成测试数据，不代表任何桥梁'}


def base_package():
    package = {
        'contract_version': '2.0',
        'data_kind': 'synthetic_variant',
        'variant': {'id': 'test', 'title': '测试', 'base': 'none', 'changes': ['合成数据']},
        'bridge_id': 'TEST-01',
        'model_revision': REVISION,
        'scenario': 'original',
        'project': {'route': '测试高速', 'stake': 'K1+000', 'stake_line': '设计桩号 K1+000', 'short_name': 'K1+000',
                    'span_text': '30 m 跨径', 'spans_m': [30], 'bridge_type': '连续梁桥', 'report_title': '抗震验算分析报告',
                    'organization': '测试实验室', 'date': '2026.09', 'header_text': '测试高速 K1+000'},
        'analysis': {'software': 'TEST', 'converged': True, 'axial_sign': 'compression_positive',
                     'methods': {'E1': 'response_spectrum', 'E2': 'nonlinear_time_history'}},
        'scope_review': {'approved': True, 'evidence': 'calc'},
        'components': [
            {'id': 'P1', 'kind': 'pier', 'label': '1#墩', 'directions': ['longitudinal', 'transverse']},
            {'id': 'F1', 'kind': 'pile', 'label': '1#桩', 'parent_pier': 'P1', 'directions': ['longitudinal', 'transverse']},
            {'id': 'B0', 'kind': 'bearing', 'label': '0#桥台', 'directions': ['longitudinal', 'transverse']},
        ],
        'actions': [],
        'checks': [],
        'not_applicable': [],
        'detailing': {'level1': {'rows': [{'location': '0#桥台', 'design_cm': 110, 'required_cm': 70}]},
                      'level2': [{'clause': '11.3.7', 'requirement': '设置挡块', 'design': '已设置', 'satisfied': True, 'topic': '挡块'}],
                      'level3': [{'clause': '11.4.3', 'requirement': '设置限位装置', 'design': '已设置', 'satisfied': True, 'topic': '限位装置'}]},
        'sources': {'calc': {'kind': 'inline', 'title': '合成计算记录', 'content': SOURCE, 'sha256': content_hash(SOURCE)}},
    }
    for member, section in (('P1', '1#墩底'), ('F1', '1#桩顶')):
        for direction in ('longitudinal', 'transverse'):
            action_id = f'A-{member}-{direction}'
            package['actions'].append({'id': action_id, 'component': member, 'direction': direction, 'level': 'E1',
                                       'combination': 'G+E1', 'N_kN': 1000.0, 'M_kNm': 500.0})
            package['checks'] += [
                check(member, direction, 'E1', 'e1_capacity', 1000.0, 2000.0, 'kN', section, action_id=action_id,
                      paired_N_M={'N_kN': 1000.0, 'M_kNm': 500.0}, method='constant_eccentricity', combination='G+E1'),
                check(member, direction, 'E2', 'e2_moment', 1000.0, 2000.0, 'kN*m', section, axial_kN=1000.0),
                check(member, direction, 'E2', 'shear', 100.0, 200.0, 'kN', section, axial_kN=1000.0),
            ]
    for level in ('E1', 'E2'):
        for direction in ('longitudinal', 'transverse'):
            package['checks'] += [check('B0', direction, level, 'bearing_displacement', 0.01, 0.0375, 'm', '0#桥台'),
                                  check('B0', direction, level, 'bearing_sliding', 10.0, 20.0, 'kN', '0#桥台')]
    return package


def check(component, direction, level, kind, demand, capacity, unit, section_label=None, **extra):
    record = {'component': component, 'direction': direction, 'level': level, 'kind': kind, 'demand': demand,
              'capacity': capacity, 'unit': unit, 'model_revision': REVISION, 'evidence': 'calc',
              'combination': extra.pop('combination', f'G+{level}')}
    if section_label:
        record['section_label'] = section_label
    record.update(extra)
    return record


def record(package, component, direction, level, kind, checks_key='checks'):
    items = package['retrofit']['checks'] if checks_key == 'retrofit' else package['checks']
    return next(r for r in items if (r['component'], r['direction'], r['level'], r['kind']) == (component, direction, level, kind))


def make_pier_plastic(package, direction='longitudinal', ductility=True):
    record(package, 'P1', direction, 'E2', 'e2_moment')['demand'] = 3000.0
    if ductility:
        add_ductility(package, direction)


def add_ductility(package, direction='longitudinal', hinge=(100.0, 300.0), displacement=(0.02, 0.10), reinforcement=(0.004, 0.005),
                  checks_key='checks', revision=REVISION):
    target = package['retrofit']['checks'] if checks_key == 'retrofit' else package['checks']
    for kind, values, unit in (('hinge_shear', hinge, 'kN'), ('ductility_displacement', displacement, 'm'),
                               ('ductility_reinforcement', reinforcement, 'ratio')):
        if values is None:
            continue
        item = check('P1', direction, 'E2', kind, values[0], values[1], unit, '1#墩底')
        item['model_revision'] = revision
        target.append(item)


def overstrength(demand, factor=1.2):
    return {'basis': 'system_equilibrium', 'reviewed': True, 'evidence': 'calc', 'factor': factor, 'demand': demand}


def with_retrofit(package, revision='synthetic-retrofit'):
    package = copy.deepcopy(package)
    package['retrofit'] = {'model_revision': revision, 'description': '外包混凝土加固', 'checks': []}
    return package
