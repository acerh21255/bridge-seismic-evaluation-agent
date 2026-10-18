# -*- coding: utf-8 -*-
"""
公路桥梁抗震设计反应谱（JTG/T 2231-01-2020 形式）
S(T) 分段：
  0    < T <= 0.1 : Smax * (0.45 + 5.5*T)
  0.1  < T <= Tg  : Smax
  Tg   < T        : Smax * Tg / T
Smax = 2.25 * Ci * Cs * Cd * A   （A 为地震动峰值加速度，单位 g）
注意：Ci/Cs/Cd 与特征周期 Tg 需按具体桥位与规范版本核定，
此处默认值仅为演示，正式计算前必须由专业人员确认。
"""
from params import Seismic


def smax(seis: Seismic) -> float:
    return 2.25 * seis.ci * seis.cs * seis.cd * seis.ag


def spectrum_points(seis: Seismic, t_end: float = 10.0, n: int = 40):
    """生成反应谱曲线离散点 [(T, S/g)]，供 SAP2000 SetUser 输入"""
    sm = smax(seis)
    tg = seis.tg
    ts = [0.0, 0.02, 0.04, 0.06, 0.08, 0.1]
    # Tg 平台段 + 下降段加密
    import numpy as np
    tail = list(np.concatenate([
        np.linspace(0.1, tg, 6, endpoint=False)[1:],
        np.geomspace(tg, t_end, n),
    ]))
    ts += tail
    pts = []
    for t in ts:
        if t <= 0:
            s = 0.45 * sm
        elif t <= 0.1:
            s = sm * (0.45 + 5.5 * t)
        elif t <= tg:
            s = sm
        else:
            s = sm * tg / t
        pts.append((round(t, 4), round(s, 5)))
    return pts


if __name__ == "__main__":
    s = Seismic(intensity=7, ag=0.1, tg=0.45)
    for t, v in spectrum_points(s):
        print(f"T={t:6.3f}s  S={v:8.5f}g")
