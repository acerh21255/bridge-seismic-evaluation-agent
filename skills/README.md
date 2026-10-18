# Agent Skills

本目录收录端到端评估链路的前三个组件：

| 目录 | 版本 | 用途 |
|---|---|---|
| `bridge-drawing-recognition/` | 0.2.0 | 扫描图纸识别与证据化台账输出 |
| `bridge-screening/` | 1.2 | 15 条专家标准的代表性桥梁筛选知识包 |
| `bridge-seismic-pipeline/` | 1.0 | 参数化建模、dry-run 与 E1/E2 简化验算 |

每个目录均保留自己的 `SKILL.md`、参考资料和必要的运行时文件。宿主 Agent 应以各目录的 `SKILL.md` 为入口；其中的命令和路径已按本统一仓库的目录结构校正。

第 4 步位于仓库根目录，以 Python 包 [`bridge_report/`](../bridge_report/) 和本地工作台形式提供。
