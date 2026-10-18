# 抗震分析与验算方法说明

## 建模方法（builder.py）

脊梁式单主梁模型（规则梁桥抗震常规简化）：
- 主梁：等效 General 截面连续脊梁，节点间距 2m，自重由材料密度+质量源自动计入
- 桥墩：盖梁（横向）+ 双柱/单柱 + 桩基（8 段划分）
- 桩土相互作用：m 法，桩身节点水平弹簧 K = m·d·Δz（桩底固结）
- 支座：盖梁顶与主梁间 Link 单元（竖向大刚度、水平线性，刚度为演示值需按支座型号换算）
- 桥台：主梁端部纵向活动、横竖向约束
- 已知简化：曲线桥按直线建模、忽略纵坡——报告中必须声明

## 反应谱（spectrum.py）

JTG/T 2231-01-2020 形式：`Smax = 2.25·Ci·Cs·Cd·A`
- 0<T≤0.1s：Smax(0.45+5.5T)；0.1<T≤Tg：Smax；T>Tg：Smax·Tg/T
- E2 峰值加速度暂按 2×E1（演示），正式按规范表取值
- SAP2000 中用 `Func.FuncRS.SetUser` 输入离散点，模态工况 30 阶（质量参与≥90%）

## 验算方法（check.py，无 SAP2000 时的简化演示算法）

规则桥梁简化法（规范容许的分析思路）：
1. 墩按等效悬臂：k = n·3EI/(H+1.5)³（+1.5m 为桩基嵌固点近似）
2. 周期 T = 2π√(m从属/k)，从属质量=相邻跨各半的桥面质量
3. **E1 强度**：S(T) 查谱 → 墩底剪力 F=S·W、弯矩 M=F·H_eff，
   与截面抗弯能力（配筋率 2% 假定估算）比较
4. **E2 变形**：位移需求 δd = S(T)·g·T²/4π²，
   与位移能力（屈服位移 δy=0.004H_eff × 延性 μΔ=4.8）比较
5. 输出逐墩 E1/E2 通过/不通过 + 安全系数 + 总结论（JSON + Markdown 表）

⚠️ 简化算法的角色：无 SAP2000 环境下打通"分析→验算"流程与输出格式。
真机跑通后，应将内力/位移数据源替换为 OAPI 提取值（Results.FrameForce /
Results.JointDispl），验算输出格式不变，并与简化结果交叉校核（量级一致性检查）。

## 首次真机运行核对清单

- [ ] SAP2000 已安装且 license 可用；`pip install comtypes numpy`
- [ ] OAPI 签名核对（v1 API 文档）：`PropFrame.SetGeneral` 参数顺序、
      `Func.FuncRS.SetUser`、`PointObj.SetSpring`、`PointObj.SetRestraint`
- [ ] `builder.py` 中 `Constraint.SetBody` 为占位调用，需改为 Diaphragm/Equal 约束
- [ ] 与既有手动模型对标：自振周期、墩底弯矩误差目标 <5%
