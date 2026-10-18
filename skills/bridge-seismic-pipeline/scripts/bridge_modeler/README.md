# sap_modeler —— SAP2000 参数化桥梁抗震建模包（Subagent3 核心）

输入一份桥梁参数 JSON（与 Subagent1 图纸识别输出对齐），自动生成 SAP2000 模型、
E1/E2 反应谱工况、运行分析并提取墩底内力/墩顶位移/支座力，供 Subagent4 生成报告。

## 文件结构

| 文件 | 作用 |
|---|---|
| `params.py` | 参数 Schema（BridgeParams 等 dataclass），**即 Subagent1→3 的接口契约** |
| `sap_driver.py` | OAPI 连接驱动（comtypes），支持 dry-run 记录模式 |
| `builder.py` | 参数化建模器：脊梁式主梁 + 双柱墩 + 盖梁 + 桩基 m 法土弹簧 + 支座 Link |
| `spectrum.py` | JTG/T 2231-01-2020 形式反应谱生成（Smax=2.25·Ci·Cs·Cd·A） |
| `run_demo.py` | 入口脚本 |
| `K44+430.json` | 样例参数（来自小样本 OCR 提取结果） |

## 用法

```bash
# ① 无 SAP2000 环境：验证建模逻辑，输出全部 261 条 OAPI 调用记录
python run_demo.py --params "K44+430.json" --dry-run

# ② 有 SAP2000 的机器：真实建模 + 保存 + 分析
pip install comtypes numpy
python run_demo.py --params "K44+430.json" --save "K44+430.sdb" --run
```

## 当前验证状态（2026-09-25）

- ✅ dry-run 全链路通过：75 节点 / 68 单元 / 261 条 OAPI 调用（见 `output/sap_dryrun_log.jsonl`）
- ⚠️ **本机未安装 SAP2000，OAPI 函数签名按 v1 API 文档编写，首次真机运行必须逐条核对**
  （重点：`PropFrame.SetGeneral` 参数顺序、`Func.FuncRS.SetUser`、`PointObj.SetSpring`、
  `Constraint.SetBody` 占位调用需改为 Diaphragm/Equal 约束）
- ⚠️ 待专业确认项：反应谱 Ci/Cs/Cd 与 Tg 取值、支座刚度换算（当前为演示值）、
  墩高为假定值（P1=12m/P2=14m，正式值需从桥型布置图读取）、E2 峰值加速度暂按 2×E1 演示
- 简化假定：曲线桥按直线建模、忽略 5.8% 纵坡、主梁按脊梁式等效——报告中需声明

## 下一步（对应执行方案阶段 2/3）

1. 在有 SAP2000 的机器上跑通真实建模，修正 OAPI 签名差异
2. 与既有手动模型（见 `2 模型截图/`）对标：自振周期、墩底弯矩误差 <5%
3. 补齐验算 skill：E1 强度 + E2 墩柱抗弯/抗剪 + 位移能力 + 支座 + 防落梁长度
4. 批量模式：遍历 `output/*.json`（OCR 提取结果）→ 自动生成多桥参数 → 队列计算
