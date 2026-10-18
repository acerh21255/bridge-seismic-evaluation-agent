# 参与开发

## 环境

```powershell
.\scripts\setup.ps1
.\scripts\verify.ps1
```

## 修改约束

- 工程数值、判定状态和结论只能来自确定性代码；不得用模型输出覆盖 `result.json` 或判定引擎结果。
- 修改交接 Schema 前先阅读 `docs/第三步数据交接说明.md` 和 `contracts/handoff.schema.json`。
- 修改建模或简化验算前先阅读 `skills/bridge-seismic-pipeline/references/check_method.md`。
- 修改筛选权重或阈值时保留旧版、记录变化，并复查 Badcase 与原本正确案例。
- 不提交 `.venv/`、`build/`、`测试资料/`、API Key、访问令牌、运行数据库或未脱敏工程资料。
- 新规则必须附带回归测试；测试不通过不接受合并。

## 提交前检查

```powershell
.\scripts\verify.ps1
git status --short
git diff --check
```

报告工作台涉及 Word 模板时，可额外设置 `BRIDGE_TEST_WORD=1` 运行真实 Word 专项测试。
