import copy
import json
import unittest

from bridge_report.engine.gates import evaluate
from bridge_report.paths import CONTRACTS_DIR
from tests.fixtures import (REVISION, add_ductility, base_package, check, make_pier_plastic, overstrength, record,
                            with_retrofit)


def items_by(result, **filters):
    return [i for i in result['items'] if all(i.get(k) == v for k, v in filters.items())]


def item(result, component, direction, level, kind, stage=None):
    found = [i for i in result['items'] if (i['component'], i['direction'], i['level'], i['kind']) == (component, direction, level, kind)
             and (stage is None or i['stage'] == stage)]
    assert len(found) == 1, found
    return found[0]


def gate(result, gate_id):
    return next(g for g in result['gates'] if g['id'] == gate_id)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.p = base_package()

    def test_all_satisfied_passes(self):
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'PASS', r['reason'])
        self.assertFalse(r['engineering_release'])
        self.assertTrue(all(i['status'] in ('PASS', 'NA') for i in r['items']))

    def test_e1_strength_failure_stops_e2(self):
        record(self.p, 'P1', 'longitudinal', 'E1', 'e1_capacity')['capacity'] = 500.0
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E1', 'e1_capacity')['verdict'], '强度破坏')
        e2 = [i for i in r['items'] if i['level'] == 'E2']
        self.assertTrue(e2 and all(i['status'] == 'SKIPPED' for i in e2))
        self.assertEqual(gate(r, 'e1')['status'], 'FAIL')
        self.assertEqual(gate(r, 'e2_pier')['status'], 'SKIPPED')

    def test_e1_missing_value_blocks_and_skips_e2(self):
        record(self.p, 'F1', 'transverse', 'E1', 'e1_capacity')['capacity'] = None
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(item(r, 'F1', 'transverse', 'E1', 'e1_capacity')['status'], 'BLOCKED')
        self.assertTrue(all(i['status'] == 'SKIPPED' for i in r['items'] if i['level'] == 'E2'))

    def test_missing_record_blocks(self):
        self.p['checks'].remove(record(self.p, 'B0', 'longitudinal', 'E1', 'bearing_sliding'))
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertIn('缺少验算记录', item(r, 'B0', 'longitudinal', 'E1', 'bearing_sliding')['reason'])

    def test_pier_plastic_without_ductility_records_is_blocked(self):
        make_pier_plastic(self.p, ductility=False)
        r = evaluate(self.p)
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'e2_moment')['status'], 'PLASTIC')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'e2_moment')['verdict'], '进入塑性')
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(r['plastic'], [{'component': 'P1', 'direction': 'longitudinal', 'section_label': '1#墩底'}])

    def test_pier_plastic_with_ductility_passes(self):
        make_pier_plastic(self.p)
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'PASS', r['reason'])
        self.assertEqual(gate(r, 'e2_pier')['status'], 'PLASTIC')
        self.assertEqual(gate(r, 'ductility')['status'], 'PASS')

    def test_pile_direct_demand_satisfied_needs_no_recompute(self):
        # D6 replaces the v1 rule “桥墩塑性即要求超强复算”: a pile within its yield moment passes directly.
        make_pier_plastic(self.p)
        r = evaluate(self.p)
        self.assertEqual(item(r, 'F1', 'longitudinal', 'E2', 'e2_moment')['status'], 'PASS')
        self.assertIsNone(item(r, 'F1', 'longitudinal', 'E2', 'e2_moment')['overstrength'])

    def test_pile_exceeds_with_plastic_pier_awaits_recompute(self):
        make_pier_plastic(self.p)
        record(self.p, 'F1', 'longitudinal', 'E2', 'e2_moment')['demand'] = 2500.0
        r = evaluate(self.p)
        pile = item(r, 'F1', 'longitudinal', 'E2', 'e2_moment')
        self.assertEqual(pile['status'], 'BLOCKED')
        self.assertIn('超强弯矩', pile['reason'])
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'shear')['status'], 'PASS')

    def test_pile_recompute_within_capacity_passes(self):
        make_pier_plastic(self.p)
        pile = record(self.p, 'F1', 'longitudinal', 'E2', 'e2_moment')
        pile['demand'] = 2500.0
        pile['overstrength'] = overstrength(1800.0)
        r = evaluate(self.p)
        result = item(r, 'F1', 'longitudinal', 'E2', 'e2_moment')
        self.assertEqual((result['status'], result['demand']), ('PASS', 1800.0))
        self.assertEqual(result['direct_demand'], 2500.0)
        self.assertEqual(r['status'], 'PASS', r['reason'])

    def test_pile_recompute_still_yielding_fails_and_stops(self):
        make_pier_plastic(self.p)
        pile = record(self.p, 'F1', 'longitudinal', 'E2', 'e2_moment')
        pile['demand'] = 2500.0
        pile['overstrength'] = overstrength(2100.0)
        r = evaluate(self.p)
        self.assertEqual(item(r, 'F1', 'longitudinal', 'E2', 'e2_moment')['verdict'], '进入屈服')
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'shear')['status'], 'SKIPPED')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear')['status'], 'SKIPPED')

    def test_invalid_recompute_evidence_blocks(self):
        make_pier_plastic(self.p)
        pile = record(self.p, 'F1', 'longitudinal', 'E2', 'e2_moment')
        pile['demand'] = 2500.0
        pile['overstrength'] = dict(overstrength(1800.0), reviewed=False)
        self.assertEqual(item(evaluate(self.p), 'F1', 'longitudinal', 'E2', 'e2_moment')['status'], 'BLOCKED')

    def test_pile_yield_with_elastic_pier_fails(self):
        record(self.p, 'F1', 'transverse', 'E2', 'e2_moment')['demand'] = 2500.0
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(item(r, 'F1', 'transverse', 'E2', 'e2_moment')['verdict'], '进入屈服')
        self.assertEqual(item(r, 'B0', 'longitudinal', 'E2', 'bearing_displacement')['status'], 'SKIPPED')

    def test_shear_failure_stops(self):
        make_pier_plastic(self.p)
        record(self.p, 'P1', 'transverse', 'E2', 'shear')['demand'] = 300.0
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(item(r, 'P1', 'transverse', 'E2', 'shear')['verdict'], '剪切破坏')
        self.assertEqual(item(r, 'B0', 'transverse', 'E2', 'bearing_sliding')['status'], 'SKIPPED')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear')['status'], 'SKIPPED')
        self.assertEqual(r['stops'][0]['gate'], 'shear')

    def test_bearing_failure_does_not_stop_ductility(self):
        make_pier_plastic(self.p)
        record(self.p, 'B0', 'longitudinal', 'E2', 'bearing_sliding')['demand'] = 30.0
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'FAIL')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear')['status'], 'PASS')

    def test_hinge_shear_failure_skips_missing_ductility_items(self):
        make_pier_plastic(self.p, ductility=False)
        add_ductility(self.p, hinge=(400.0, 300.0), displacement=None, reinforcement=None)
        r = evaluate(self.p)
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear')['verdict'], '不满足')
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'ductility_displacement')['status'], 'SKIPPED')
        self.assertEqual(r['status'], 'FAIL')

    def test_ductility_records_for_elastic_pier_not_applicable(self):
        add_ductility(self.p, 'transverse')
        r = evaluate(self.p)
        self.assertEqual(item(r, 'P1', 'transverse', 'E2', 'hinge_shear')['status'], 'NA')
        self.assertEqual(r['status'], 'PASS')

    def test_strength_reduction_factor(self):
        make_pier_plastic(self.p, ductility=False)
        add_ductility(self.p, hinge=(100.0, 110.0))
        record(self.p, 'P1', 'longitudinal', 'E2', 'hinge_shear')['phi'] = 0.9
        hinge = item(evaluate(self.p), 'P1', 'longitudinal', 'E2', 'hinge_shear')
        self.assertEqual((hinge['status'], hinge['capacity'], hinge['phi'], hinge['ratio']), ('FAIL', 110.0, 0.9, 0.99))


class BearingAndDetailingTests(unittest.TestCase):
    def setUp(self):
        self.p = base_package()

    def test_provisional_bearing_limit(self):
        b = record(self.p, 'B0', 'longitudinal', 'E1', 'bearing_displacement')
        b.update(capacity=None, limit_status='not_provided')
        r = evaluate(self.p)
        result = item(r, 'B0', 'longitudinal', 'E1', 'bearing_displacement')
        self.assertEqual((result['status'], result['capacity'], result['provisional']), ('PASS', 0.0375, True))
        self.assertIn('0.0375', result['limit_basis'])
        self.assertEqual(r['status'], 'PASS')
        self.assertTrue(r['provisional'])

    def test_provisional_limit_exceeded_fails(self):
        b = record(self.p, 'B0', 'transverse', 'E2', 'bearing_displacement')
        b.update(capacity=None, limit_status='not_provided', demand=0.05)
        self.assertEqual(evaluate(self.p)['status'], 'FAIL')

    def test_zero_demand_has_no_ratio(self):
        record(self.p, 'B0', 'transverse', 'E1', 'bearing_displacement')['demand'] = 0.0
        result = item(evaluate(self.p), 'B0', 'transverse', 'E1', 'bearing_displacement')
        self.assertEqual((result['status'], result['ratio']), ('PASS', None))

    def test_not_applicable_declaration(self):
        for level in ('E1', 'E2'):
            for direction in ('longitudinal', 'transverse'):
                self.p['checks'].remove(record(self.p, 'B0', direction, level, 'bearing_sliding'))
                self.p['not_applicable'].append({'component': 'B0', 'direction': direction, 'level': level,
                                                 'kind': 'bearing_sliding', 'reason': '盆式支座不做抗滑移验算', 'evidence': 'calc'})
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(item(r, 'B0', 'longitudinal', 'E1', 'bearing_sliding')['status'], 'NA')

    def test_detailing_failure(self):
        self.p['detailing']['level3'][0]['satisfied'] = False
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'FAIL')
        detailing = items_by(r, kind='detailing')
        self.assertEqual([i['verdict'] for i in detailing], ['满足', '不满足'])
        self.assertEqual(items_by(r, kind='edge_distance')[0]['verdict'], '通过')

    def test_detailing_missing_blocks(self):
        del self.p['detailing']
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(gate(r, 'detailing')['status'], 'BLOCKED')

    def test_pilecap_checks(self):
        self.p['pilecap'] = {'checks': [{'id': 'punching', 'title': '承台冲切承载力验算', 'direction': 'transverse',
                                         'rows': [['γ0Fld', 'KN', '2648']], 'demand': 2648.0, 'capacity': 24739.0}]}
        r = evaluate(self.p)
        cap = items_by(r, kind='pilecap')[0]
        self.assertEqual((cap['verdict'], cap['ratio']), ('满足', 9.343))
        self.p['pilecap']['checks'][0]['capacity'] = 2000.0
        self.assertEqual(evaluate(self.p)['status'], 'FAIL')


class RetrofitTests(unittest.TestCase):
    def setUp(self):
        base = base_package()
        make_pier_plastic(base, ductility=False)
        add_ductility(base, hinge=(1143.5, 538.0), displacement=None, reinforcement=None)
        self.p = with_retrofit(base)

    def test_retrofit_resolves_ductility(self):
        retro = self.p['retrofit']
        retro['checks'].append(check('P1', 'longitudinal', 'E2', 'e2_moment', 3200.0, 2500.0, 'kN*m', '1#墩底'))
        add_ductility(self.p, hinge=(1459.9, 3195.7), displacement=(0.0213, 0.10), reinforcement=(0.004, 0.00436),
                      checks_key='retrofit', revision=retro['model_revision'])
        for r in retro['checks']:
            r['model_revision'] = retro['model_revision']
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'PASS', r['reason'])
        self.assertEqual(item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear', stage='original')['status'], 'FAIL')
        after = item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear', stage='retrofit')
        self.assertEqual((after['status'], after['before']['capacity']), ('PASS', 538.0))
        self.assertTrue(after['final'])
        self.assertFalse(item(r, 'P1', 'longitudinal', 'E2', 'hinge_shear', stage='original')['final'])
        self.assertEqual(gate(r, 'retrofit')['status'], 'PASS')

    def test_without_retrofit_items_failure_stands(self):
        self.assertEqual(evaluate(self.p)['status'], 'FAIL')

    def test_retrofit_revision_must_differ_and_match(self):
        self.p['retrofit']['checks'].append(check('P1', 'longitudinal', 'E2', 'hinge_shear', 100.0, 300.0, 'kN', '1#墩底'))
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertTrue(any('加固' in issue for issue in r['issues']))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.p = base_package()

    def assertBlocked(self, fragment=None):
        r = evaluate(self.p)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertFalse(r['evaluated'])
        if fragment:
            self.assertTrue(any(fragment in issue for issue in r['issues']), r['issues'])
        return r

    def test_unit(self):
        record(self.p, 'P1', 'longitudinal', 'E1', 'e1_capacity')['unit'] = 'kN*m'
        self.assertBlocked('单位')

    def test_non_finite(self):
        record(self.p, 'P1', 'longitudinal', 'E1', 'e1_capacity')['capacity'] = float('nan')
        self.assertBlocked('数值')

    def test_negative(self):
        record(self.p, 'P1', 'longitudinal', 'E2', 'shear')['demand'] = -1.0
        self.assertBlocked('数值')

    def test_duplicate(self):
        self.p['checks'].append(copy.deepcopy(self.p['checks'][0]))
        self.assertBlocked('重复')

    def test_version_mixing(self):
        record(self.p, 'P1', 'longitudinal', 'E2', 'shear')['model_revision'] = 'other'
        self.assertBlocked('模型版本')

    def test_missing_evidence(self):
        record(self.p, 'P1', 'longitudinal', 'E2', 'shear')['evidence'] = 'nowhere'
        self.assertBlocked('证据')

    def test_evidence_tamper(self):
        self.p['sources']['calc']['content'] = {'note': 'changed'}
        self.assertBlocked('SHA256')

    def test_e1_pair_mismatch(self):
        self.p['actions'][0]['N_kN'] = 1200.0
        self.assertBlocked('配对')

    def test_e1_requires_constant_eccentricity(self):
        record(self.p, 'P1', 'longitudinal', 'E1', 'e1_capacity')['method'] = 'pure_axial'
        self.assertBlocked('偏心')

    def test_analysis_not_converged(self):
        self.p['analysis']['converged'] = False
        self.assertBlocked('分析')

    def test_scope_not_approved(self):
        self.p['scope_review']['approved'] = False
        self.assertBlocked('范围')

    def test_one_direction(self):
        self.p['components'][0]['directions'] = ['longitudinal']
        self.assertBlocked('纵横')

    def test_unknown_component(self):
        record(self.p, 'P1', 'longitudinal', 'E2', 'shear')['component'] = 'X9'
        self.assertBlocked('构件')

    def test_e1_shear_not_part_of_flow(self):
        self.p['checks'].append(check('P1', 'longitudinal', 'E1', 'shear', 1.0, 2.0, 'kN'))
        self.assertBlocked('水准')

    def test_pile_without_parent(self):
        self.p['components'][1]['parent_pier'] = 'P9'
        self.assertBlocked('桩基')

    def test_not_applicable_conflicts_with_record(self):
        self.p['not_applicable'].append({'component': 'B0', 'direction': 'longitudinal', 'level': 'E1', 'kind': 'bearing_sliding',
                                         'reason': '冲突声明测试', 'evidence': 'calc'})
        self.assertBlocked('不适用')

    def test_schema_violation(self):
        self.p['contract_version'] = '1.0'
        self.assertBlocked('contract_version')

    def test_template_is_blocked(self):
        template = json.loads((CONTRACTS_DIR / 'handoff.template.json').read_text(encoding='utf-8'))
        r = evaluate(template)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertFalse(r['evaluated'])

    def test_structurally_broken_input(self):
        r = evaluate({'checks': [None]})
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertFalse(r['engineering_release'])

    def test_revision_constant(self):
        self.assertEqual(REVISION, self.p['model_revision'])


if __name__ == '__main__':
    unittest.main()
