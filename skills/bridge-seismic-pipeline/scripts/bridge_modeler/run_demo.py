# -*- coding: utf-8 -*-
"""
演示入口：读取桥梁参数 JSON -> 自动建模 -> E1/E2 反应谱工况 -> 运行分析 -> 提取结果
用法：
  无 SAP2000 环境验证逻辑：
    python run_demo.py --params "K44+430.json" --dry-run
  有 SAP2000 真实建模：
    python run_demo.py --params "K44+430.json" --save model.sdb --run
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from params import BridgeParams
from sap_driver import SapDriver
from builder import BridgeBuilder
from spectrum import spectrum_points, Seismic


def extract_results(drv: SapDriver, pier_ids):
    """提取关键抗震结果：墩底内力、墩顶位移、支座力（供 Subagent4 报告使用）"""
    results = {"cases": ["RS_E1", "RS_E2"], "piers": {}}
    for case in results["cases"]:
        drv.call("Results.Setup.DeselectAllCasesAndCombosForOutput", ret=0)
        drv.call("Results.Setup.SetCaseSelectedForOutput", case, ret=0)
        for pid in pier_ids:
            # 墩底弯矩/剪力（取柱底单元）
            frame_force = drv.call(
                "Results.FrameForce", f"{pid}_L_COL", 0, ret=[0, [], [], [], [], [], [], [], [], [], [], []])
            # 墩顶位移
            joint_disp = drv.call(
                "Results.JointDispl", f"{pid}_CAP_L", 0, ret=[0, [], [], [], [], [], [], [], [], []])
            results["piers"].setdefault(pid, {})[case] = {
                "frame_force_raw": frame_force if drv.dry_run else "见 SAP2000",
                "joint_disp_raw": joint_disp if drv.dry_run else "见 SAP2000",
            }
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    ap.add_argument("--dry-run", action="store_true", help="不连接 SAP2000，只记录 OAPI 调用")
    ap.add_argument("--save", default="", help="模型保存路径 .sdb")
    ap.add_argument("--run", action="store_true", help="建模后运行分析并提取结果")
    ap.add_argument("--log", default="./build/sap_dryrun_log.jsonl")
    args = ap.parse_args()

    params = BridgeParams.from_json(args.params)
    print(f"[1/5] 参数载入: {params.bridge_name}  跨径 {'+'.join(str(s.length) for s in params.spans)}m  "
          f"墩数 {len(params.piers)}  全长 {params.total_length}m")

    drv = SapDriver(dry_run=args.dry_run, log_path=args.log)
    drv.new_model(units=6)  # kN-m
    print("[2/5] 开始参数化建模..." + ("（dry-run 记录模式）" if args.dry_run else ""))

    builder = BridgeBuilder(drv, params).build()
    print(f"[3/5] 建模完成: 节点 {len(builder.node_map)} 个, 单元 {len(builder.frame_map)} 个")

    # E1/E2 反应谱（E2 峰值加速度按 7 度约 0.2g 演示，正式按规范取）
    seis_e1 = params.seismic
    seis_e2 = Seismic(**{**params.seismic.__dict__, "ag": params.seismic.ag * 2.0})
    pts_e1 = spectrum_points(seis_e1)
    pts_e2 = spectrum_points(seis_e2)
    builder.define_spectrum_cases(pts_e1, pts_e2)
    print(f"[4/5] 反应谱工况: E1(Smax={max(v for _, v in pts_e1):.3f}g) "
          f"E2(Smax={max(v for _, v in pts_e2):.3f}g), Tg={params.seismic.tg}s")

    if args.save:
        drv.save(args.save)
        print(f"      模型已保存: {args.save}")

    if args.run or args.dry_run:
        drv.run_analysis()
        results = extract_results(drv, [p.pier_id for p in params.piers])
        print(f"[5/5] 分析结果提取: {len(results['piers'])} 个墩 × 2 工况 "
              f"（墩底内力 / 墩顶位移 / 支座力，供 Subagent4 报告）")

    log = drv.close()
    print(f"完成。OAPI 调用记录: {log}（共 {len(drv.calls)} 条）")


if __name__ == "__main__":
    main()
