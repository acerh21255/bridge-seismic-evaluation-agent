"""Status labels and verdict wording (sample report wording, decision D8)."""

STATUS_LABELS = {'PASS': '满足', 'FAIL': '不满足', 'BLOCKED': '待补正', 'PLASTIC': '进入塑性', 'SKIPPED': '未开展', 'NA': '不适用'}

DIRECTION_LABELS = {'longitudinal': '纵桥向', 'transverse': '横桥向'}
INPUT_LABELS = {'longitudinal': '纵向地震', 'transverse': '横向地震'}

KIND_LABELS = {
    'e1_capacity': 'E1截面承载力',
    'e2_moment': 'E2抗弯',
    'shear': '抗剪',
    'bearing_displacement': '支座位移',
    'bearing_sliding': '支座抗滑移',
    'measures': '抗滑/限位措施',
    'hinge_shear': '塑性铰区抗剪',
    'ductility_displacement': '位移延性',
    'ductility_reinforcement': '延性构造配箍率',
    'additional': '专项构件',
    'edge_distance': '一级抗震措施（梁端边距）',
    'detailing': '构造措施',
    'pilecap': '承台验算',
}

COMPONENT_LABELS = {'pier': '桥墩', 'pile': '桩基', 'bearing': '支座', 'measure': '抗滑/限位措施', 'capbeam': '盖梁',
                    'tiebeam': '系梁'}

_FAIL_WORDS = {'e1_capacity': '强度破坏', 'shear': '剪切破坏'}


def verdict(kind, component_kind, status):
    """Wording for the “验算结果” column."""
    if status == 'BLOCKED':
        return '待补正'
    if status == 'SKIPPED':
        return '未开展'
    if status == 'NA':
        return '不适用'
    if status == 'PLASTIC':
        return '进入塑性'
    if status == 'PASS':
        return '满足' if kind in ('detailing', 'pilecap') else '通过'
    if kind == 'e2_moment':
        return '进入屈服' if component_kind == 'pile' else '进入塑性'
    return _FAIL_WORDS.get(kind, '不满足')


def is_failure_word(text):
    return text in ('强度破坏', '剪切破坏', '进入屈服', '不满足')
