# 桥梁参数 JSON Schema（Subagent2 筛选表 → Subagent3 建模 接口契约）

每座桥一个 JSON 文件，字段如下（单位：m / kN / t / MPa）：

## 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `bridge_name` | str | 桥名（含左右幅/上下行） |
| `stake` | str | 设计桩号，如 `K257+528` |
| `source_drawing` | str | 溯源信息（图纸文件或筛选表序号） |
| `spans` | list | 跨径数组，`[{"length": 30}, ...]`，长度=跨数 |
| `piers` | list | 桥墩数组，长度=跨数-1，见下 |
| `abutments` | list | 两个桥台 `{location, type, restraint}` |
| `deck` | obj | 主梁等效截面（脊梁式简化） |
| `materials` | obj | 材料表 `{name: {fck, elastic_mod}}` |
| `seismic` | obj | 设防参数 `{intensity, ag, site_class, tg, ci, cs, cd, damping}` |
| `bearings` | str | 支座形式（记录用） |
| `_note` / `_warnings` | str/list | 假定值声明与转换警告，**必须随结果一并交付** |

## piers 元素

| 字段 | 默认/来源 | 说明 |
|---|---|---|
| `pier_id` | P1..Pn | |
| `location` | 跨径累加 | 距起点 x 坐标 m |
| `height` | 筛选表逐墩墩高（左右柱均值） | 缺失时用全桥均值补齐并记 warning |
| `n_columns` | 双柱=2 / 单柱=1 | |
| `column_diameter` | 筛选表"桥墩尺寸" | 矩形墩 a×b 按等效圆 φ=√(4ab/π) 近似并记 warning |
| `column_spacing` | 6.0（假定） | 横向柱间距 |
| `cap_beam_height/width` | 1.5 / 筛选表盖梁宽 | |
| `pile_diameter / pile_length` | 筛选表 / 25（假定） | |
| `soil_m` | 10000 kN/m⁴（假定） | m 法地基比例系数 |

## 已知假定值（必须在报告中声明）

柱间距 6.0m、桩长 25m、主梁等效截面（空心板/T梁/箱梁三档预设）、
设防参数（默认 7 度 0.10g II 类 Tg=0.45，可用 CLI `--ag --site --tg` 覆盖）、
m=10000 kN/m⁴、配筋率 2%（验算用）。
正式计算前需由图纸/地勘/规范核定。

## 输入表格式要求（xlsx_to_params.py 适配的版式）

G8511筛选结果 格式：首行表头；每桥 1–2 行（次行=另一柱墩高，序号桩号为空）；
数据行内含精确文本 `墩高` 标签列，其后为 均值列、空列、逐墩墩高值列。
关键列（0-based）：1=序号 3=设计桩号 4=左右幅 6=桥跨组合 8=主梁形式
9=结构形式 10=支座 11=桥台 12=桥墩形式 13=桥墩尺寸 16=桩基形式 17=桩基直径 18=盖梁宽。
拱桥/斜拉/悬索桥型 v1 跳过；桥墩尺寸缺失跳过；均记入 `_conversion_summary.json`。
