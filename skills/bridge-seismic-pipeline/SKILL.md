---
name: bridge-seismic-pipeline
description: 既有桥梁自动化抗震评估流水线（Subagent3）。输入桥梁筛选数据表（xlsx/csv，G8511筛选结果格式）或参数 JSON，批量完成：参数提取转换 → SAP2000 参数化建模（真机 OAPI 或 dry-run 记录）→ E1/E2 反应谱分析设定 → 抗震验算（E1强度/E2位移，逐墩通过/不通过）→ 输出建模文件、验算结果(JSON/MD)、建模动画与批量汇总。This skill should be used when 用户要求对桥梁筛选结果表进行批量抗震建模/分析/验算，或要求生成单座桥的 SAP2000 参数化模型与验算报告。
agent_created: true
---

# 桥梁抗震评估流水线（Subagent3）

## 用途

把 Subagent2 的桥梁筛选数据表一键转成：每座桥的参数 JSON、SAP2000 建模产物、
E1/E2 抗震验算结论和演示动画。无 SAP2000 的机器上也能完整运行
（dry-run 记录 OAPI 指令 + 规范简化法验算），有 SAP2000 时切真机模式。

## 环境与前置

- Python 环境：统一仓库根目录 `.venv\Scripts\python.exe`（Windows）或已激活的 Python 3.12+ 环境
  （dry-run 需要 matplotlib / imageio / imageio-ffmpeg / numpy / openpyxl）
- 真机模式额外要求：本机安装 SAP2000（license 可用）+ `pip install comtypes`
- 脚本目录：`skills/bridge-seismic-pipeline/scripts/`，建模包：`skills/bridge-seismic-pipeline/scripts/bridge_modeler/`
- **以下命令从统一仓库根目录执行**

## 主流程（一条命令）

```powershell
python skills\bridge-seismic-pipeline\scripts\run_pipeline.py <筛选表.xlsx|csv> `
  --outdir <输出目录> [--select K257+528] [--animate] [--real] [--ag 0.10]
```

- 默认 dry-run：每桥输出 参数JSON + `*_oapi_log.jsonl`（SAP2000 将执行的完整指令序列）
  + `*_验算结果.json/.md` + `batch_summary.md` 批量汇总
- `--real`：连接 SAP2000 真机建模、保存 .sdb、运行分析（首次使用前先按
  `references/check_method.md` 末尾的"真机核对清单"逐项确认）
- `--animate`：每桥渲染建模生长动画 MP4（批量时较慢，建议配合 `--select` 单桥使用）
- 输入也可以是参数 JSON 目录（跳过表格转换直接批量处理）

## 分步使用（调试/演示时）

```powershell
# 1. 表格 -> 参数 JSON（含转换警告与假定值声明）
python skills\bridge-seismic-pipeline\scripts\xlsx_to_params.py 筛选表.csv --outdir .\params

# 2. 单桥建模（dry-run 验证 / 真机去掉 --dry-run）
python skills\bridge-seismic-pipeline\scripts\bridge_modeler\run_demo.py --params "skills\bridge-seismic-pipeline\scripts\bridge_modeler\K257+528.json" --dry-run
python skills\bridge-seismic-pipeline\scripts\bridge_modeler\run_demo.py --params "skills\bridge-seismic-pipeline\scripts\bridge_modeler\K257+528.json" --save model.sdb --run   # 真机

# 3. 单桥验算
python skills\bridge-seismic-pipeline\scripts\bridge_modeler\check.py "skills\bridge-seismic-pipeline\scripts\bridge_modeler\K257+528.json" <输出目录>

# 4. 单桥建模动画
python skills\bridge-seismic-pipeline\scripts\bridge_modeler\animate_model.py --params "skills\bridge-seismic-pipeline\scripts\bridge_modeler\K257+528.json" --out <输出目录>\build.mp4
```

## 关键规则

1. **假定值必须随结果声明**：柱间距/桩长/等效截面/设防参数/配筋率等假定值
   记录在每个 JSON 的 `_note` 与 `_warnings` 字段，交付与汇报时不得省略。
2. **验算"不通过"是有效产出**：如实呈现，不得调参凑"通过"。
3. **dry-run 产物 ≠ 有限元结果**：验算数值来自规范简化法，对外表述必须说明；
   真机跑通后用 OAPI 提取值替换数据源，输出格式不变。
4. 不支持的桥型（拱/斜拉/悬索、墩尺寸缺失）自动跳过并记入
   `params/_conversion_summary.json`，汇报时说明跳过原因与数量。
5. 修改 Schema 前阅读 `references/schema.md`；修改验算方法前阅读
   `references/check_method.md`。

## 参考文件

- `references/schema.md` —— 参数 JSON Schema（= Subagent2→3 接口契约）与输入表格式要求
- `references/check_method.md` —— 建模假定、反应谱公式、验算算法与真机核对清单
- `scripts/bridge_modeler/K257+528.json` / `K44+430.json` —— 参数样例
