# -*- coding: utf-8 -*-
"""
桥梁抗震评估流水线编排器（Subagent3 主入口）
输入: 筛选数据表(xlsx/csv) 或 参数JSON目录
输出(每桥): 参数JSON + 建模结果(SAP2000真机.sdb 或 dry-run OAPI记录)
           + 验算结果(JSON/MD) [+ 建模动画MP4]
           + 批量汇总 batch_summary.md

用法:
  # 无 SAP2000（dry-run 验证 + 简化验算）
  python run_pipeline.py G8511筛选结果.csv --outdir ../output/batch
  # 只跑指定桥
  python run_pipeline.py G8511筛选结果.csv --select K257+528 --animate
  # 有 SAP2000 的机器：真实建模+分析
  python run_pipeline.py G8511筛选结果.csv --real
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODELER = os.path.join(HERE, "bridge_modeler")
sys.path.insert(0, HERE)
sys.path.insert(0, MODELER)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def process_bridge(json_path, outdir, real=False, animate=False, rho=0.02):
    from params import BridgeParams
    from sap_driver import SapDriver
    from builder import BridgeBuilder
    from spectrum import spectrum_points, Seismic
    check_mod = load_module("check_mod", os.path.join(MODELER, "check.py"))

    params = BridgeParams.from_json(json_path)
    # 输出文件前缀用 JSON 文件名（含序号），避免同桩号多联/多幅互相覆盖
    stake = os.path.splitext(os.path.basename(json_path))[0].replace("+", "_").replace("/", "_")
    os.makedirs(outdir, exist_ok=True)
    res = {"stake": stake, "bridge": params.bridge_name}

    # 1) 建模
    log_path = os.path.join(outdir, f"{stake}_oapi_log.jsonl")
    drv = SapDriver(dry_run=not real, log_path=log_path)
    drv.new_model(units=6)
    builder = BridgeBuilder(drv, params).build()
    seis_e2 = Seismic(**{**params.seismic.__dict__, "ag": params.seismic.ag * 2.0})
    builder.define_spectrum_cases(spectrum_points(params.seismic),
                                  spectrum_points(seis_e2))
    if real:
        sdb = os.path.join(outdir, f"{stake}.sdb")
        drv.save(sdb)
        drv.run_analysis()
        res["model_sdb"] = sdb
    drv.close()
    res["model"] = {
        "mode": "SAP2000 真机" if real else "dry-run(OAPI记录)",
        "nodes": len(builder.node_map), "elements": len(builder.frame_map),
        "oapi_calls": len(drv.calls), "log": log_path,
    }

    # 2) 验算（简化法；真机模式下后续可替换为 OAPI 结果驱动）
    rep = check_mod.check_bridge(params, rho=rho)
    res["check"] = {"总结论": rep["总结论"],
                    "piers": {p["pier_id"]: {"E1": p["E1"]["验算"], "E2": p["E2"]["验算"]}
                              for p in rep["piers"]}}
    with open(os.path.join(outdir, f"{stake}_验算结果.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, f"{stake}_验算结果.md"), "w", encoding="utf-8") as f:
        f.write(check_mod.to_markdown(rep))

    # 3) 动画（可选）
    if animate:
        anim = load_module("anim_mod", os.path.join(MODELER, "animate_model.py"))
        mp4 = os.path.join(outdir, f"{stake}_build.mp4")
        anim.render(params, anim.build_geometry(json_path)[1], mp4)
        res["animation"] = mp4
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="筛选数据表(xlsx/csv) 或 参数JSON目录")
    ap.add_argument("--outdir", default="./pipeline_output")
    ap.add_argument("--select", default="", help="只处理包含该字符串的桩号")
    ap.add_argument("--real", action="store_true", help="连接 SAP2000 真机建模分析")
    ap.add_argument("--animate", action="store_true", help="生成建模动画")
    ap.add_argument("--ag", type=float, default=0.10)
    ap.add_argument("--rho", type=float, default=0.02, help="墩柱配筋率假定（默认2%%）")
    args = ap.parse_args()

    params_dir = os.path.join(args.outdir, "params")
    if os.path.isdir(args.input):
        params_dir = args.input
        jsons = sorted(os.path.join(params_dir, f) for f in os.listdir(params_dir)
                       if f.endswith(".json") and not f.startswith("_"))
    else:
        conv = load_module("conv_mod", os.path.join(HERE, "xlsx_to_params.py"))
        summary = conv.convert(args.input, params_dir, ag=args.ag)
        jsons = [b["json"] for b in summary["bridges"]]

    if args.select:
        jsons = [j for j in jsons if args.select in os.path.basename(j)]
    print(f"待处理桥梁: {len(jsons)} 座，模式: {'SAP2000真机' if args.real else 'dry-run+简化验算'}")

    results, failed = [], []
    for j in jsons:
        name = os.path.basename(j)
        try:
            r = process_bridge(j, args.outdir, real=args.real, animate=args.animate, rho=args.rho)
            results.append(r)
            print(f"  [OK] {r['stake']}: {r['model']['elements']}单元, 验算 {r['check']['总结论']}")
        except Exception as e:
            failed.append({"json": name, "error": str(e)})
            print(f"  [FAIL] {name}: {e}")

    # 批量汇总
    lines = ["# 批量抗震评估汇总", "",
             f"- 输入: {args.input}　模式: {'SAP2000真机' if args.real else 'dry-run+简化验算'}",
             f"- 参数: ag={args.ag}g, 配筋率假定={args.rho:.0%}（其余假定值见各桥 JSON 的 _note）",
             f"- 成功 {len(results)} 座 / 失败 {len(failed)} 座", "",
             "| 桩号 | 单元数 | E1验算 | E2验算 | 总结论 |", "|---|---|---|---|---|"]
    for r in results:
        e1 = "/".join(sorted({v["E1"] for v in r["check"]["piers"].values()}))
        e2 = "/".join(sorted({v["E2"] for v in r["check"]["piers"].values()}))
        lines.append(f"| {r['stake']} | {r['model']['elements']} | {e1} | {e2} | {r['check']['总结论']} |")
    for f_ in failed:
        lines.append(f"| {f_['json']} | — | 失败 | — | {f_['error'][:40]} |")
    with open(os.path.join(args.outdir, "batch_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n汇总: {os.path.join(args.outdir, 'batch_summary.md')}")


if __name__ == "__main__":
    main()
