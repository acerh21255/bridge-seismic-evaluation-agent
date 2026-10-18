"""Add editable style examples to the three-section laboratory report master."""
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

CHAPTERS = [
    ('工程概况', '填写桥位、跨径、桥型、上下部结构和验算范围。桥梁事实以已确认交接数据为准。'),
    ('设计依据', '填写采用的规范名称、版本与适用范围，核对本次抗震评价所使用的依据。'),
    ('设计参数', '填写材料、场地条件及地震动参数，注明暂定参数与需复核的项目。'),
    ('地震作用', '说明 E1、E2 地震作用、输入方向、波组与组合方法，并引用对应分析结果。'),
    ('有限元模型', '说明模型版本、单元类型、边界条件、支座和桩土处理方式，插入实际模型图。'),
    ('抗震验算', '按 E1、E2 与能力保护流程填入需求和能力，说明停止后续验算的条件。'),
    ('延性验算', '对进入塑性的桥墩列示延性需求与能力。未触发或资料不足时说明原因。'),
    ('韧性提升与复核', '列示已提供的加固措施和加固后复核结果，不把建议当作已实施措施。'),
    ('结论与建议', '分别列示满足、不满足和待补正事项，结论与验算结果保持一致。'),
]


def add_examples(doc):
    from bridge_report.report.template_layout import clear_examples
    cover, toc = clear_examples(doc)
    def paragraph(text, style, anchor=None, size=None, before=0):
        p = doc.add_paragraph(text, style=style)
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(8)
        if size:
            for r in p.runs:
                r.font.size = Pt(size)
        if anchor is not None:
            anchor.addprevious(p._p)
        return p
    p = paragraph('桥梁抗震验算报告母版', '封面1', cover, 26, 90)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text in ('{{项目名称}}', '{{桥梁名称与桩号}}', '{{跨径与桥型}}', '抗震验算分析报告'):
        p = paragraph(text, '封面1', cover, 20)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph('{{编制单位}}', '报告-封面注记', cover, 15, 45)
    paragraph('{{报告日期}}', '报告-封面注记', cover, 12)
    paragraph('可编辑样式示例  上传后由系统生成实际报告内容', '报告-封面注记', cover, 10, 30)
    paragraph('目录与使用说明', '报告-目录标题', toc)
    for i, (title, _) in enumerate(CHAPTERS, 1):
        paragraph(f'{i}  {title}', '报告-无缩进', toc)
    paragraph('如何修改母版', '报告-无缩进', toc, 14, 16)
    paragraph('在 Word 或 WPS 中修改“报告-”样式、标题样式、页眉页脚及页边距，保留封面、目录、正文三个分节。', '报告-正文', toc)
    paragraph('正文示例用于查看排版。上传后，示例文字和表格会被本次交接数据生成的内容替换；直接改写示例文字不会成为固定报告条款。正式目录由系统生成。', '报告-正文', toc)
    paragraph('页眉中的 {{HEADER}} 和页脚中的 {{ORG}} 由系统填入桥梁信息及编制单位，请保留占位符。', '报告-正文', toc)
    for i, (title, explanation) in enumerate(CHAPTERS, 1):
        p = paragraph(f'{i}  {title}', 'Heading 1', before=10)
        p.paragraph_format.page_break_before = (i == 6)
        paragraph(explanation, '报告-正文')
        if i == 1:
            p = paragraph('1.1  桥梁概况', 'Heading 2')
            paragraph('正文样式示例：本桥的结构形式、建造年代和抗震评价范围由交接包提供。缺失信息应标为待补正。', '报告-正文')
        if i == 5:
            paragraph('〔在实际报告中插入有限元模型图〕', '报告-图')
            paragraph('图5.1-1  有限元模型图题示例', '报告-图题')
        if i == 6:
            paragraph('表6.1-1  验算结果表样式示例', '报告-表题')
            table = doc.add_table(rows=3, cols=4)
            values = [('构件', '需求', '能力', '判定'), ('{{构件名称}}', '待填', '待填', '待判定'), ('{{验算方向}}', '待填', '待填', '待判定')]
            for row_index, row in enumerate(table.rows):
                for cell, value in zip(row.cells, values[row_index]):
                    cell.text = value
                    cell.paragraphs[0].style = doc.styles['报告-表头' if row_index == 0 else '报告-表文']
            borders = OxmlElement('w:tblBorders')
            for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
                border = OxmlElement('w:' + edge)
                for k, v in [('val', 'single'), ('sz', '4'), ('color', '808080')]:
                    border.set(qn('w:' + k), v)
                borders.append(border)
            table._tbl.tblPr.append(borders)
            paragraph('注：本表仅显示样式，不包含可用于工程判定的数值。', '报告-表注')
