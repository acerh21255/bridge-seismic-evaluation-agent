"""Curated retrofit knowledge: failure modes of the E1/E2 workflow and the candidate measures that address them.
Descriptions stay qualitative; any quantity must come from a re-analysis delivered by step 3."""

CODES = {
    'seismic': '《公路桥梁抗震设计规范》（JTG/T 2231-01—2020）',
    'retrofit': '《公路桥梁加固设计规范》（JTG/T J22—2008）',
}

MEASURES = {
    'enlarge_section': {
        'title': '增大截面加固（钢筋混凝土 / ECC 外包）',
        'effect': '同时提高墩身抗弯、抗剪承载力和刚度，可配合加密环向箍筋改善约束。',
        'caution': '刚度与抗弯承载力提高会增大地震需求和墩底超强弯矩，须同步复核桩基、盖梁等能力保护构件；增加自重与截面尺寸。',
        'code': 'retrofit',
    },
    'steel_jacket': {
        'title': '外包钢套管 / 钢板约束加固',
        'effect': '提供连续侧向约束，显著提高塑性铰区抗剪能力、极限曲率和位移延性。',
        'caution': '套管端部与承台、盖梁间留缝时基本不提高抗弯承载力（有利于能力保护）；须做防腐并处理灌浆密实度。',
        'code': 'retrofit',
    },
    'frp_wrap': {
        'title': '纤维复合材料（FRP）环向包裹',
        'effect': '自重小、施工快，提高混凝土约束、抗剪能力与延性。',
        'caution': '对抗弯承载力贡献有限；须满足基面处理、环境温湿度与防火防护要求。',
        'code': 'retrofit',
    },
    'isolation': {
        'title': '更换减隔震支座（铅芯橡胶 / 摩擦摆等）',
        'effect': '延长结构周期、增加耗能，同时降低墩、桩的地震需求，是桩基难以加固时的首选思路。',
        'caution': '梁体位移增大，须同时复核伸缩缝、梁端支承长度与限位装置；需重新建模并由第三步复算。',
        'code': 'seismic',
    },
    'restrainer': {
        'title': '增设纵横向限位装置 / 抗震挡块 / 防落梁装置',
        'effect': '限制梁体过大位移，防止落梁，是三级抗震措施的直接补强方式。',
        'caution': '限位刚度会改变墩柱受力分配，设置后应复核相邻墩柱与挡块自身承载力。',
        'code': 'seismic',
    },
    'seat_extension': {
        'title': '盖梁 / 台帽加宽或增设牛腿',
        'effect': '增加梁端支承长度，满足梁端最小边距要求。',
        'caution': '须核算新增混凝土与原结构的连接及盖梁受力。',
        'code': 'retrofit',
    },
    'bearing_replace': {
        'title': '更换支座或增设支座抗滑限位构造',
        'effect': '恢复支座位移能力或抗滑能力，避免支座失效引起的梁体移位。',
        'caution': '更换需顶升梁体，须编制专项施工方案。',
        'code': 'seismic',
    },
    'foundation': {
        'title': '基础加固：扩大承台并增设补桩 / 桩周土加固',
        'effect': '提高桩基抗弯承载力与整体刚度。',
        'caution': '造价高、施工受地质和净空限制；一般与降低上部地震需求的措施比选后采用。',
        'code': 'retrofit',
    },
    'pilecap_strengthen': {
        'title': '承台加厚 / 外包加固',
        'effect': '提高承台冲切、拉杆与斜压杆承载力。',
        'caution': '须核算新老混凝土结合面，承台加厚后复核桩顶受力。',
        'code': 'retrofit',
    },
}

# Failure modes: what the engine outcome means physically, why it matters and which measures address it (priority order).
MODES = {
    'e1_strength': {
        'title': 'E1 截面强度不足', 'severity': 'critical',
        'meaning': 'E1 常遇地震下截面承载力小于配对内力需求，按流程 E2 验算不开展。',
        'measures': ['enlarge_section', 'isolation'],
    },
    'pier_plastic': {
        'title': 'E2 墩底进入塑性', 'severity': 'watch',
        'meaning': '属于预期的延性抗震机制，本身不是失效；关键在于塑性铰区抗剪、位移延性和配箍率能否支撑塑性变形，并保证桩基等能力保护构件不先屈服。延性项不满足时另列为薄弱环节。',
        'measures': [],
    },
    'pile_yield': {
        'title': '桩基能力保护不满足', 'severity': 'critical',
        'meaning': '桩基先于或随桥墩屈服，损伤发生在难以检查与修复的地下部位，违背能力保护原则，按流程停止后续验算。',
        'measures': ['isolation', 'foundation'],
        'note': '不宜单独增强桥墩抗弯承载力：墩底超强弯矩增大会进一步加重桩基需求。',
    },
    'member_shear': {
        'title': '墩桩抗剪不足', 'severity': 'critical',
        'meaning': '可能发生脆性剪切破坏，按流程停止后续验算。',
        'measures': ['steel_jacket', 'frp_wrap', 'enlarge_section'],
    },
    'hinge_shear': {
        'title': '塑性铰区抗剪不足', 'severity': 'critical',
        'meaning': '塑性铰形成后可能先发生剪切破坏，延性机制无法实现，其余延性项未开展。',
        'measures': ['steel_jacket', 'frp_wrap', 'enlarge_section'],
    },
    'ductility_disp': {
        'title': '位移延性不足', 'severity': 'critical',
        'meaning': '墩柱变形能力不足以承受 E2 位移需求。',
        'measures': ['steel_jacket', 'frp_wrap', 'isolation'],
    },
    'confinement': {
        'title': '延性构造配箍率不足', 'severity': 'major',
        'meaning': '塑性铰区约束不足，核心混凝土与纵筋屈曲控制不满足构造要求。',
        'measures': ['steel_jacket', 'frp_wrap'],
    },
    'bearing': {
        'title': '支座位移 / 抗滑不满足', 'severity': 'major',
        'meaning': '支座可能滑移或超出位移能力，引起梁体移位甚至落梁。',
        'measures': ['bearing_replace', 'restrainer', 'isolation'],
    },
    'restrainer': {
        'title': '限位 / 挡块等抗震措施不满足', 'severity': 'major',
        'meaning': '构造措施缺失时，梁体在 E2 下存在过大位移或落梁风险。',
        'measures': ['restrainer'],
    },
    'seat_length': {
        'title': '梁端支承长度不足', 'severity': 'major',
        'meaning': '梁端边距小于规范要求，存在落梁风险。',
        'measures': ['seat_extension', 'restrainer'],
    },
    'detailing': {
        'title': '其他构造措施不满足', 'severity': 'major',
        'meaning': '构造措施不满足规范要求，需逐项补强。',
        'measures': ['restrainer'],
    },
    'pilecap': {
        'title': '承台承载力不足', 'severity': 'critical',
        'meaning': '承台作为能力保护构件，不应先于桥墩破坏。',
        'measures': ['pilecap_strengthen', 'foundation'],
    },
    'data_overstrength': {
        'title': '缺超强弯矩传力复算', 'severity': 'data',
        'meaning': '关联桥墩已进入塑性且桩基直接需求超限，需按超强弯矩体系传力复算后才能判定桩基是否屈服。',
        'measures': [],
    },
    'data_missing': {
        'title': '资料缺项', 'severity': 'data',
        'meaning': '缺少判定所需数值，不能由报告 Agent 推定或补值。',
        'measures': [],
    },
}

SEVERITY_ORDER = {'critical': 0, 'major': 1, 'watch': 2, 'data': 3}
SEVERITY_LABEL = {'critical': '控制性问题', 'major': '需处理', 'watch': '需关注', 'data': '待补资料'}
