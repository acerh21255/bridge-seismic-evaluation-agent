# -*- coding: utf-8 -*-
"""
简化抗震验算 skill（无 SAP2000 环境下的独立验算演示）
方法依据：JTG/T 2231-01-2020 对规则桥梁容许的简化分析思路
  - 桥墩按等效悬臂构件（固定端取至桩顶以下嵌固点近似）
  - E1：弹性反应谱底部剪力法 -> 墩底弯矩需求 vs 截面抗弯能力（估算）
  - E2：等效单自由度位移需求 vs 墩柱容许位移（延性简化法）
⚠️ 演示算法：用于打通"分析->验算"流程与输出格式，
   正式结果须由 SAP2000 模型分析提供内力/位移后复算，并与本简化结果交叉校核。
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import BridgeParams
from spectrum import spectrum_points

G = 9.81
FIXITY_EXTRA = 1.5  # 桩基嵌固点附加深度 m（简化假定）


def pier_effective_stiffness(d_m, h_m, e_mpa, n_cols):
    """单墩等效抗侧刚度 kN/m：k = n * 3EI / Heff^3"""
    I = math.pi * d_m ** 4 / 64.0
    E = e_mpa * 1e3  # MPa -> kN/m2
    Heff = h_m + FIXITY_EXTRA
    return n_cols * 3 * E * I / Heff ** 3, I, Heff


def deck_tributary_mass(params: BridgeParams, pier_idx: int, rho_kn_m3=26.0):
    """墩 i 的从属桥面质量 t（相邻跨各一半）"""
    spans = [s.length for s in params.spans]
    a = params.deck.area
    trib = spans[pier_idx - 1] / 2 + spans[pier_idx] / 2 if 0 < pier_idx < len(spans) else spans[0] / 2
    return a * rho_kn_m3 * trib / G  # kN/(m/s2)=t


def spectrum_S(pts, T):
    """从反应谱离散点插值取 S(T)，单位 g"""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if T <= xs[0]:
        return ys[0]
    if T >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if T <= xs[i]:
            t0, t1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            return y0 + (y1 - y0) * (T - t0) / (t1 - t0)
    return ys[-1]


def moment_capacity(d_m, fck_mpa, rho=0.02, fy_mpa=400):
    """圆形截面墩柱抗弯能力粗略估算 kN·m（假定配筋率2%，HRB400）
       Mu ≈ 0.8 * rho * fy * As... 采用简化: Mu ≈ 0.35*fy*rho*D^3 （文献常用量级）"""
    return 0.35 * fy_mpa * rho * (d_m * 1000) ** 3 / 1e6


def check_bridge(params: BridgeParams, e2_factor: float = 2.0, rho: float = 0.02):
    seis = params.seismic
    pts_e1 = spectrum_points(seis)
    seis_e2 = type(seis)(**{**seis.__dict__, "ag": seis.ag * e2_factor})
    pts_e2 = spectrum_points(seis_e2)
    E_pier = params.materials[params.piers[0].column_material].elastic_mod

    report = {"bridge": params.bridge_name, "stake": params.stake,
              "方法": "规则桥梁简化法（演示），JTG/T 2231-01-2020 思路",
              "E1设防": f"{seis.intensity}度 ag={seis.ag}g",
              "E2设防": f"ag={seis.ag * e2_factor}g",
              "配筋率假定": rho, "piers": []}

    for i, pier in enumerate(params.piers):
        k, I, Heff = pier_effective_stiffness(
            pier.column_diameter, pier.height, E_pier, pier.n_columns)
        m = deck_tributary_mass(params, i)  # t
        T = 2 * math.pi * math.sqrt(m / k)  # s（m 单位 t=kN·s²/m，k 单位 kN/m）
        # ---- E1 强度 ----
        S1 = spectrum_S(pts_e1, T)
        F1 = S1 * m * G                # kN
        M1 = F1 * Heff                 # kN·m 墩底弯矩需求
        Mu = moment_capacity(pier.column_diameter,
                             params.materials[pier.column_material].fck,
                             rho=rho) * pier.n_columns
        # ---- E2 位移 ----
        S2 = spectrum_S(pts_e2, T)
        delta_d = S2 * G * T ** 2 / (4 * math.pi ** 2)  # m 位移需求
        # 位移能力：容许曲率延性 μφ=6 简化 -> δu = μΔ * δy，屈服位移 δy=F_y/k
        # 简化取屈服位移 δy = Heff * 0.004（曲率屈服转角量级），μΔ 限值 4.8（规范限值附近）
        delta_y = Heff * 0.004
        delta_u = 4.8 * delta_y
        report["piers"].append({
            "pier_id": pier.pier_id,
            "墩高m": pier.height,
            "等效周期s": round(T, 3),
            "从属质量t": round(m, 1),
            "E1": {
                "S(T)g": round(S1, 4),
                "墩底剪力需求kN": round(F1, 1),
                "墩底弯矩需求kNm": round(M1, 0),
                "截面抗弯能力kNm(估)": round(Mu, 0),
                "验算": "通过" if Mu >= M1 else "不通过",
                "安全系数": round(Mu / M1, 2) if M1 > 0 else None,
            },
            "E2": {
                "S(T)g": round(S2, 4),
                "位移需求m": round(delta_d, 4),
                "位移能力m(估)": round(delta_u, 4),
                "验算": "通过" if delta_u >= delta_d else "不通过",
                "安全系数": round(delta_u / delta_d, 2) if delta_d > 0 else None,
            },
        })
    ok = all(p["E1"]["验算"] == "通过" and p["E2"]["验算"] == "通过"
             for p in report["piers"])
    report["总结论"] = "通过" if ok else "存在不通过项"
    report["声明"] = (f"简化演示算法：配筋率按{rho:.0%}假定、嵌固点按+1.5m假定、"
                    "位移能力按μΔ=4.8简化。正式结论须以 SAP2000 模型分析+截面精细验算为准。")
    return report


def to_markdown(rep: dict) -> str:
    lines = [f"# {rep['bridge']} 抗震验算结果（简化法演示）", "",
             f"- 桩号：{rep['stake']}　方法：{rep['方法']}",
             f"- E1：{rep['E1设防']}　E2：{rep['E2设防']}　**总结论：{rep['总结论']}**", "",
             "| 墩号 | 墩高(m) | 周期(s) | E1弯矩需求(kN·m) | E1抗弯能力(kN·m) | E1结论 | E2位移需求(m) | E2位移能力(m) | E2结论 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for p in rep["piers"]:
        lines.append(
            f"| {p['pier_id']} | {p['墩高m']} | {p['等效周期s']} "
            f"| {p['E1']['墩底弯矩需求kNm']:.0f} | {p['E1']['截面抗弯能力kNm(估)']:.0f} | {p['E1']['验算']}({p['E1']['安全系数']}) "
            f"| {p['E2']['位移需求m']:.4f} | {p['E2']['位移能力m(估)']:.4f} | {p['E2']['验算']}({p['E2']['安全系数']}) |")
    lines += ["", f"> {rep['声明']}"]
    return "\n".join(lines)


if __name__ == "__main__":
    params_path = sys.argv[1] if len(sys.argv) > 1 else "K257+528.json"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "../output"
    rho = float(sys.argv[3]) if len(sys.argv) > 3 else 0.02
    params = BridgeParams.from_json(params_path)
    rep = check_bridge(params, rho=rho)
    os.makedirs(out_dir, exist_ok=True)
    base = params.stake.replace("+", "_")
    with open(os.path.join(out_dir, f"{base}_验算结果.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    md = to_markdown(rep)
    with open(os.path.join(out_dir, f"{base}_验算结果.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
