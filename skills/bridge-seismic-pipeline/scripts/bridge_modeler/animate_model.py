# -*- coding: utf-8 -*-
"""
建模过程 3D 动画渲染（无需 SAP2000）
用 builder 的真实几何输出（节点坐标+单元连接）渲染"桥梁自动生成"动画，
供演示视频使用。输出 MP4。
用法: python animate_model.py --params "K44+430.json" --out ../output/bridge_build.mp4
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa
import imageio.v2 as imageio

from params import BridgeParams
from sap_driver import SapDriver
from builder import BridgeBuilder

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 单元类型 -> (颜色, 线宽, 标签)
STYLE = {
    "GIRDER": ("#2E86C1", 5, "主梁（T形连续梁）"),
    "CAP": ("#E67E22", 5, "盖梁"),
    "COL": ("#C0392B", 6, "墩柱（双柱式）"),
    "PILE": ("#7F8C8D", 4, "钻孔灌注桩"),
}


def classify(section: str) -> str:
    for k in STYLE:
        if section.startswith(k):
            return k
    return "GIRDER"


def build_geometry(params_path):
    params = BridgeParams.from_json(params_path)
    drv = SapDriver(dry_run=True, log_path=os.devnull)
    b = BridgeBuilder(drv, params).build()
    elems = []
    for n1, n2, sec in b.frame_links:
        p1, p2 = b.node_coords[n1], b.node_coords[n2]
        elems.append((p1, p2, classify(sec)))
    return params, elems, b


def render(params, elems, out_path, fps=14, intro_s=1.5, outro_s=2.5):
    xs = [p[0] for e in elems for p in e[:2]]
    ys = [p[1] for e in elems for p in e[:2]]
    zs = [p[2] for e in elems for p in e[:2]]
    zmin = min(zs)

    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor("#F7F9FB")
    ax.set_facecolor("#F7F9FB")

    def setup_axis(title, subtitle):
        ax.clear()
        ax.set_facecolor("#F7F9FB")
        ax.set_xlim(min(xs) - 3, max(xs) + 3)
        ax.set_ylim(min(ys) - 9, max(ys) + 9)
        ax.set_zlim(zmin - 2, 4)
        ax.view_init(elev=14, azim=-52)
        ax.set_box_aspect((max(xs) - min(xs) + 6, 18, 4 - zmin + 2))
        ax.set_axis_off()
        ax.set_title(title, fontsize=20, fontweight="bold", color="#1B2631", pad=2)
        ax.text2D(0.5, 0.02, subtitle, transform=ax.transAxes,
                  ha="center", fontsize=12, color="#5D6D7E")
        # 地面线
        ax.plot([min(xs) - 3, max(xs) + 3], [0, 0], [zmin, zmin],
                color="#B2BABB", lw=1, ls="--")

    spans = "+".join(str(int(s.length)) for s in params.spans)
    title = f"{params.bridge_name}  参数化自动建模"
    writer = imageio.get_writer(out_path, fps=fps, codec="libx264",
                                quality=8, macro_block_size=8)

    def shot(n=1):
        for _ in range(n):
            fig.canvas.draw()
            buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
            writer.append_data(buf)

    # 片头：标题 + 参数信息
    setup_axis(title, f"跨径布置 {spans} m ｜ 双柱式墩 × {len(params.piers)} ｜ "
                      f"钻孔灌注桩基础 ｜ 全长 {params.total_length:.0f} m")
    shot(int(intro_s * fps))

    # 逐单元生长：按类型顺序（主梁 -> 盖梁 -> 墩柱 -> 桩）
    order = {"GIRDER": 0, "CAP": 1, "COL": 2, "PILE": 3}
    seq = sorted(elems, key=lambda e: order[e[2]])
    drawn = []
    seen_types = set()
    for i, (p1, p2, typ) in enumerate(seq):
        drawn.append((p1, p2, typ))
        seen_types.add(typ)
        label = " → ".join(STYLE[t][2] for t in
                           sorted(seen_types, key=lambda t: order[t]))
        setup_axis(title, f"正在生成：{label}   [{i + 1}/{len(seq)}]")
        for q1, q2, t in drawn:
            c, lw, _ = STYLE[t]
            ax.plot([q1[0], q2[0]], [q1[1], q2[1]], [q1[2], q2[2]],
                    color=c, lw=lw, solid_capstyle="round")
        shot(1)

    # 片尾：完整模型 + 标注
    setup_axis(title, f"模型完成：{len(elems)} 个单元 ｜ 下一步：E1/E2 反应谱分析")
    for q1, q2, t in drawn:
        c, lw, _ = STYLE[t]
        ax.plot([q1[0], q2[0]], [q1[1], q2[1]], [q1[2], q2[2]],
                color=c, lw=lw, solid_capstyle="round")
    handles = [plt.Line2D([0], [0], color=STYLE[k][0], lw=4, label=STYLE[k][2])
               for k in ["GIRDER", "CAP", "COL", "PILE"]]
    ax.legend(handles=handles, loc="upper right", fontsize=11, frameon=False)
    shot(int(outro_s * fps))
    writer.close()
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", default="../output/bridge_build.mp4")
    ap.add_argument("--fps", type=int, default=14)
    args = ap.parse_args()
    params, elems, _ = build_geometry(args.params)
    print(f"几何提取: {len(elems)} 个单元，开始渲染动画...")
    render(params, elems, args.out, fps=args.fps)
    print(f"动画已输出: {args.out}")


if __name__ == "__main__":
    main()
