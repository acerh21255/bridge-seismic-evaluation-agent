# -*- coding: utf-8 -*-
"""
参数化桥梁建模器（脊梁式单主梁 + 双柱墩 + 桩基 m 法土弹簧 + 支座 Link 单元）
模型拓扑：
  桥面系：沿 X 轴的连续脊梁（等效截面），节点间距 ~2m
  桥墩：盖梁（横向 Y）+ 双柱 + 桩（竖向分段，节点加 m 法水平土弹簧）
  支座：盖梁顶 <-> 主梁 之间的 Link 单元（板式橡胶支座，竖向固结/水平线性）
  桥台：主梁端部按纵向活动支座简化约束
"""
import math
from params import BridgeParams, Pier

PILE_SEGMENTS = 8      # 桩身分段数
DECK_NODE_STEP = 2.0   # 主梁节点间距 m


class BridgeBuilder:
    def __init__(self, drv, params: BridgeParams):
        self.d = drv
        self.p = params
        self.node_map = {}   # 语义名 -> SAP 点名
        self.frame_map = {}
        self.node_coords = {}  # 语义名 -> (x, y, z)，供可视化
        self.frame_links = []  # [(n1, n2, section_tag)]，供可视化

    # ================= 材料与截面 =================
    def define_materials(self):
        for m in self.p.materials.values():
            self.d.call("PropMaterial.SetMaterial", m.name, 2)          # 2=Concrete
            self.d.call("PropMaterial.SetMPIsotropic", m.name,
                        m.elastic_mod * 1e3, 0.2, 1e-5)                 # MPa->kN/m2

    def define_sections(self):
        p = self.p
        # 主梁：等效 General 截面
        deck = p.deck
        self.d.call("PropFrame.SetGeneral", "GIRDER", deck.material,
                    3.0, deck.width, deck.area,
                    deck.shear_as2, deck.shear_as3,
                    deck.torsion_j, deck.inertia_22, deck.inertia_33,
                    0.0, 0.0)
        for pier in p.piers:
            suffix = pier.pier_id
            self.d.call("PropFrame.SetCircle", f"COL_{suffix}",
                        pier.column_material, pier.column_diameter)
            self.d.call("PropFrame.SetCircle", f"PILE_{suffix}",
                        pier.pile_material, pier.pile_diameter)
            self.d.call("PropFrame.SetRectangle", f"CAP_{suffix}",
                        pier.column_material,
                        pier.cap_beam_height, pier.cap_beam_width)

    # ================= 几何 =================
    def _add_point(self, key, x, y, z):
        name = self.d.call("PointObj.AddCartesian", x, y, z, "", key, ret=key)
        if not self.d.dry_run:
            name = name[1] if isinstance(name, (list, tuple)) else key
        self.node_map[key] = name
        self.node_coords[key] = (x, y, z)
        return name

    def _add_frame(self, key, n1, n2, section):
        name = self.d.call("FrameObj.AddByPoint", n1, n2, section, key, ret=key)
        if not self.d.dry_run:
            name = name[1] if isinstance(name, (list, tuple)) else key
        self.frame_map[key] = name
        self.frame_links.append((n1, n2, section))
        return name

    def build_deck(self):
        """主梁脊梁：节点从 0 到桥长，z=0"""
        L = self.p.total_length
        xs = []
        x = 0.0
        while x < L:
            xs.append(round(x, 3))
            x += DECK_NODE_STEP
        if xs[-1] != L:
            xs.append(L)
        self.deck_xs = xs
        for i, xi in enumerate(xs):
            self._add_point(f"D{i}", xi, 0.0, 0.0)
        for i in range(len(xs) - 1):
            self._add_frame(f"G{i}", f"D{i}", f"D{i+1}", "GIRDER")
        # 主梁自重由材料自重+质量源自动考虑

    def build_piers(self):
        """每个墩：盖梁 + 双柱 + 桩（分段+土弹簧）"""
        for pier in self.p.piers:
            self._build_one_pier(pier)

    def _deck_node_at(self, x):
        """距 x 最近的主梁节点"""
        i = min(range(len(self.deck_xs)), key=lambda k: abs(self.deck_xs[k] - x))
        return f"D{i}"

    def _build_one_pier(self, pier: Pier):
        pid = pier.pier_id
        x = pier.location
        s = pier.column_spacing / 2.0
        deck_node = self._deck_node_at(x)
        # 盖梁两端（柱顶）
        self._add_point(f"{pid}_CAP_L", x, -s, -pier.cap_beam_height)
        self._add_point(f"{pid}_CAP_R", x, s, -pier.cap_beam_height)
        self._add_frame(f"{pid}_CAP", f"{pid}_CAP_L", f"{pid}_CAP_R", f"CAP_{pid}")
        # 双柱 + 桩
        for tag, y in (("L", -s), ("R", s)):
            top = f"{pid}_CAP_{tag}"
            z_col_bot = -pier.cap_beam_height - pier.height
            self._add_point(f"{pid}_{tag}_CBOT", x, y, z_col_bot)
            self._add_frame(f"{pid}_{tag}_COL", top, f"{pid}_{tag}_CBOT", f"COL_{pid}")
            # 桩：分段 + 水平土弹簧（m 法：K = m * b * z_seg，简化按节点影响宽度）
            seg = pier.pile_length / PILE_SEGMENTS
            kx = pier.soil_m * pier.pile_diameter * seg   # kN/m 每节点水平弹簧
            prev = f"{pid}_{tag}_CBOT"
            for j in range(1, PILE_SEGMENTS + 1):
                key = f"{pid}_{tag}_P{j}"
                self._add_point(key, x, y, z_col_bot - seg * j)
                self._add_frame(f"{pid}_{tag}_PILE{j}", prev, key, f"PILE_{pid}")
                if j < PILE_SEGMENTS:
                    # m 法水平弹簧（X/Y 向），桩底固结
                    self.d.call("PointObj.SetSpring", key,
                                [kx, kx, 0.0, 0.0, 0.0, 0.0], False, "Global")
                prev = key
            self.d.call("PointObj.SetRestraint", prev,
                        [True, True, True, True, True, True])
        # 支座：盖梁顶 <-> 主梁（Link 单元）
        for tag in ("L", "R"):
            cap_pt = f"{pid}_CAP_{tag}"
            deck_pt = self._add_point(f"{pid}_BRG_{tag}", x,
                                      -s if tag == "L" else s, 0.0)
            # 主梁节点与支座点刚臂连接
            self.d.call("PointObj.SetRestraint", f"{pid}_BRG_{tag}",
                        [False] * 6)
            link_name = self.d.call("LinkObj.AddByPoint", deck_pt, f"{pid}_BRG_{tag}",
                                    "BRG", f"{pid}_BRG{tag}", ret=f"{pid}_BRG{tag}")
            # 支座与主梁刚接约束（约束方程）
            self.d.call("Constraint.SetBody", f"C_{pid}_{tag}",
                        [self._deck_node_at(x)], 1)  # 占位：实际用 Diaphragm/Equal
        self._define_bearing_prop()

    def _define_bearing_prop(self):
        """板式橡胶支座 Link 属性：竖向大刚度、水平按剪切刚度（演示值，需按实际支座换算）"""
        self.d.call("PropLink.SetLinear", "BRG",
                    [True, True, True, False, False, False],
                    [0.0] * 6,
                    [1e6, 1e4, 1e4, 0.0, 0.0, 0.0],
                    [0.0] * 6, 0.0, 0.0)

    def build_abutments(self):
        """桥台：主梁端部纵向活动、横向竖向约束"""
        L = self.p.total_length
        for i, x in ((0, 0.0), (len(self.deck_xs) - 1, L)):
            # U1 纵向释放, U2/U3 约束, R1/R2/R3 释放（活动支座简化）
            self.d.call("PointObj.SetRestraint", f"D{i}",
                        [False, True, True, False, False, False])

    # ================= 荷载与分析 =================
    def define_loads(self):
        # 恒载工况（自重）
        self.d.call("LoadPatterns.Add", "DEAD", 1, 1.0)  # LTYPE_DEAD=1, 自重乘数1
        # 二期恒载（桥面铺装+防撞墙，演示按 40 kN/m 均布）
        self.d.call("LoadPatterns.Add", "SDL", 15, 0.0)  # LTYPE_SUPERDEAD
        for i in range(len(self.deck_xs) - 1):
            self.d.call("FrameObj.SetLoadDistributed", f"G{i}", "SDL", 1, 10,
                        0.0, 1.0, "Global", True, True, -40.0, -40.0, -40.0, -40.0)

    def define_mass(self):
        self.d.call("SourceMass.SetMassSource", "MASS", False, True, False,
                    True, 1, ["DEAD"], [1.0], [], [], [], [])

    def define_spectrum_cases(self, spec_points_e1, spec_points_e2):
        for tag, pts, case in (("E1", spec_points_e1, "RS_E1"),
                               ("E2", spec_points_e2, "RS_E2")):
            ts = [t for t, _ in pts]
            vs = [v for _, v in pts]
            self.d.call("Func.FuncRS.SetUser", f"SPEC_{tag}", len(pts), ts, vs, 0.05)
            self.d.call("LoadCases.ResponseSpectrum.SetCase", case)
            self.d.call("LoadCases.ResponseSpectrum.SetLoads", case, 1,
                        [f"SPEC_{tag}"], ["U1"], [1.0], ["Global"],
                        [0.0], [0.0])
        # 模态工况：Ritz/特征值，足够振型数使质量参与 >=90%
        self.d.call("LoadCases.ModalEigen.SetCase", "MODAL")
        self.d.call("LoadCases.ModalEigen.SetParameters", "MODAL",
                    30, 0.0, 1e-6, 0.0)

    # ================= 主流程 =================
    def build(self):
        self.define_materials()
        self.define_sections()
        self.build_deck()
        self.build_piers()
        self.build_abutments()
        self.define_loads()
        self.define_mass()
        return self
