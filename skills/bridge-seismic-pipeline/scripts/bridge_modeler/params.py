# -*- coding: utf-8 -*-
"""
桥梁参数 Schema 定义
与 Subagent1 图纸识别输出（extract_sample.py 的 15 类参数）对齐，
是 Subagent1/2 -> Subagent3 的接口契约。
单位约定：长度 m，力 kN，质量 t，应力 MPa。
"""
from dataclasses import dataclass, field
import json


@dataclass
class Material:
    name: str                 # 如 "C30"（墩柱）"C25"（桩基）
    fck: float                # 混凝土轴心抗压标准值 MPa
    elastic_mod: float = 3.0e4  # 弹性模量 MPa


@dataclass
class Span:
    length: float             # 单跨跨径 m


@dataclass
class Pier:
    """双柱式桥墩（可扩展）"""
    pier_id: str              # 如 "P1"
    location: float           # 距起点里程坐标 m
    height: float             # 墩高 m
    n_columns: int = 2        # 柱数
    column_diameter: float = 1.2    # 墩柱直径 m
    column_spacing: float = 5.0     # 柱间距 m（横向）
    cap_beam_height: float = 1.5    # 盖梁高 m
    cap_beam_width: float = 1.8     # 盖梁宽 m
    pile_diameter: float = 1.4      # 桩径 m
    pile_length: float = 25.0       # 桩长 m
    soil_m: float = 10000.0         # m 法地基比例系数 kN/m^4
    column_material: str = "C30"
    pile_material: str = "C25"


@dataclass
class Abutment:
    location: float           # 0 或 桥长
    type: str = "重力式台"
    restraint: str = "纵向活动"  # 边界假定


@dataclass
class Deck:
    """上部结构（简化为脊梁式单主梁，抗震常规简化）"""
    girder_type: str = "T形连续梁"
    width: float = 12.0       # 桥面宽 m
    area: float = 6.0         # 主梁等效面积 m^2
    inertia_33: float = 4.0   # 竖弯惯性矩 m^4
    inertia_22: float = 30.0  # 横弯惯性矩 m^4
    torsion_j: float = 6.0
    shear_as2: float = 5.0
    shear_as3: float = 5.0
    unit_weight: float = 26.0  # kN/m^3
    material: str = "C50"


@dataclass
class Seismic:
    intensity: int = 7              # 设防烈度
    ag: float = 0.1                 # E1 地震动峰值加速度 g
    site_class: str = "II"          # 场地类别
    tg: float = 0.45                # 特征周期 s
    ci: float = 1.0                 # 重要性系数
    cs: float = 1.0                 # 场地系数
    cd: float = 1.0                 # 阻尼调整系数
    damping: float = 0.05


@dataclass
class BridgeParams:
    bridge_name: str
    stake: str
    spans: list                     # List[Span]
    piers: list                     # List[Pier]
    abutments: list
    deck: Deck
    materials: dict                 # name -> Material
    seismic: Seismic
    curve_radius: float = 0.0       # 0=直线桥（v1 简化：曲线桥按直线建模，影响在报告中说明）
    grade: float = 0.0              # 纵坡 %（v1 简化忽略）
    source_drawing: str = ""        # 溯源：图纸文件名

    @staticmethod
    def from_json(path: str) -> "BridgeParams":
        d = json.load(open(path, encoding="utf-8"))
        return BridgeParams(
            bridge_name=d["bridge_name"],
            stake=d["stake"],
            spans=[Span(**s) for s in d["spans"]],
            piers=[Pier(**p) for p in d["piers"]],
            abutments=[Abutment(**a) for a in d["abutments"]],
            deck=Deck(**d["deck"]),
            materials={k: Material(**v) for k, v in d["materials"].items()},
            seismic=Seismic(**d["seismic"]),
            curve_radius=d.get("curve_radius", 0.0),
            grade=d.get("grade", 0.0),
            source_drawing=d.get("source_drawing", ""),
        )

    @property
    def total_length(self) -> float:
        return sum(s.length for s in self.spans)
