# 变更记录

## Unreleased

### 统一仓库

- 将图纸识别、桥梁筛选、建模验算和报告决策四个组件整理到同一源码仓库。
- 保留第 4 步应用的原始 Python 包路径、工作台启动方式、Word 模板、示例与回归测试。
- 增加统一 README、组件数据流说明、演示视频索引、发布权利说明和仓库验证脚本。
- 修正图纸识别 Skill 的 Python 路径说明。
- 修正建模流水线 Skill 中依赖本地用户目录的 Python 路径。
- 修复 dry-run 批量汇总在 GBK 控制台下因勾选符号导致的 `UnicodeEncodeError`。
- 修复模型协议测试对 HTTP 头名称大小写过于敏感的问题；HTTP 头比较现按大小写不敏感处理。
- 增加 GitHub Actions：Python 编译、157 项回归测试、图纸识别 doctor 和流水线 dry-run。

### 当前版本

- `bridge-drawing-recognition`：0.2.0
- `bridge-screening`：1.2
- `bridge-seismic-pipeline`：1.0
- `bridge_report`：3.3.0
