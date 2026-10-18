# Bridge Field Contract

| Code | Field | Required | Main evidence |
|---|---|---|---|
| A | 是否有图纸 | No | Ignore completely |
| B | 序号 | Yes | Title block/drawing list |
| C | 桩号/桥名 | No | Drawing list/title block |
| D | 设计桩号 | Yes | Title block/general arrangement |
| E | 左幅/右幅 | Yes | General arrangement |
| F | 跨径 | Yes | Elevation/quantity table |
| G | 桥跨组合 | Yes | Quantity table/elevation |
| H | 一联总长 | Yes | Quantity table/dimension chain |
| I | 主梁形式 | Yes | Girder section/title |
| J | 结构形式 | Yes | Elevation/design notes |
| K | 支座形式 | No | Bearing/general notes |
| L | 桥台形式 | No | Abutment/general arrangement |
| M | 桥墩形式 | No | Pier/general arrangement |
| N | 桥墩尺寸 | No | Pier section |
| O | 纵向墩高差 | No | Derived, engineering definition required |
| P | 横向墩高差 | No | Derived, engineering definition required |
| Q | 桩基形式 | No | Pile/general notes |
| R | 桩基直径 | No | Pile/general notes |
| S | 盖梁顺桥向宽度 | No | Cap beam/pier section |
| T/U | 盖梁配筋图与配筋率 | No | Drawing list/rebar table |
| V/W | 桥墩配筋图与配筋率 | No | Drawing list/rebar table |
| X/Y | 系梁配筋图与配筋率 | No | Drawing list/rebar table |
| Z/AA | 桩配筋图与配筋率 | No | Drawing list/rebar table |
| AB+ | 各桥墩高度 | No | Pier elevations; optional enhancement |

Only T/V/X/Z are existence flags. U/W/Y/AA require an explicit numeric value
in the drawing or notes. AB and later pier-height fields are optional and must
not block acceptance.
