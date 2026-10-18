"""Build the lab report master template, format spec and asset library from the 76K reference report.

The reference report is only read. Outputs:
  bridge_report/report/template/lab_template.docx  styles, three-section layout, header/footer placeholders
  bridge_report/report/template/format_spec.json   measured layout parameters (the format contract)
  bridge_report/report/library/                    generic figures and verbatim XML fragments (OMML formulas)
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from docx import Document
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bridge_report.paths import FORMAT_SPEC, LIBRARY_DIR, REFERENCE_76K, TEMPLATE_DIR, TEMPLATE_DOCX  # noqa: E402

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'

# Body element indexes in the reference report (see docs/superpowers/specs, section 4.1).
COVER_BREAK = 26
TOC_BREAK = 61
FRAGMENTS = {
    'materials_conversion': (100, 113, '新老规范混凝土强度换算说明、换算表与公式'),
    'shear_formulas': (242, 248, '斜截面受剪承载力公式（JTG 3362-2018）'),
    'hinge_shear_formulas': (338, 367, '塑性铰区抗剪公式（JTG/T 2231-02—2021）'),
    'displacement_ductility': (386, 389, '墩顶位移延性验算公式'),
    'stirrup_ratio': (393, 402, '延性构造最小配箍率公式'),
}
FIGURES = {
    'm_phi': (231, '等效屈服弯矩计算示意（原图6.1-1）'),
    'bearing_bilinear': (197, '支座双线性恢复力模型（原图5.2-1）'),
    'beam_end_formula': (320, '梁端最小距离公式（原式6.5）'),
    'beam_end_distance': (324, '梁端至墩台帽或盖梁边缘最小距离示意（原图6.4）'),
}
SIX_SPRING = ('six_spring', 'figures/six_spring.png',
              '桩基础六弹簧模型，自 Word 导出的原报告 PDF 第16页裁切（300 dpi，x 88–507 pt，y 200–401 pt，不含原题注）')

REPORT_STYLES = [
    # (styleId, name, basedOn, pPr xml, rPr xml)
    ('BRBody', '报告-正文', '1',
     '<w:ind w:firstLine="480" w:firstLineChars="200"/><w:spacing w:line="360" w:lineRule="auto"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'),
    ('BRPlain', '报告-无缩进', '1',
     '<w:spacing w:line="360" w:lineRule="auto"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'),
    ('BREquation', '报告-公式', '1',
     '<w:spacing w:line="360" w:lineRule="auto"/><w:jc w:val="center"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'),
    ('BRTableHead', '报告-表头', '1',
     '<w:widowControl w:val="0"/><w:jc w:val="center"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:b/><w:bCs/><w:sz w:val="22"/><w:szCs w:val="22"/>'),
    ('BRTableText', '报告-表文', '1',
     '<w:widowControl w:val="0"/><w:jc w:val="center"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="22"/><w:szCs w:val="22"/>'),
    ('BRTableData', '报告-资料表文', '1',
     '<w:widowControl w:val="0"/><w:jc w:val="center"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="21"/><w:szCs w:val="21"/>'),
    ('BRNote', '报告-表注', '25',
     '<w:jc w:val="both"/>', ''),
    ('BRFigure', '报告-图', '76',
     '<w:keepNext/><w:spacing w:before="163" w:beforeLines="50"/><w:ind w:firstLine="0" w:firstLineChars="0"/>', ''),
    ('BRFigCaption', '报告-图题', '76',
     '<w:spacing w:before="163" w:beforeLines="50" w:after="163" w:afterLines="50"/><w:ind w:firstLine="0" w:firstLineChars="0"/>', ''),
    ('BRTabCaption', '报告-表题', '76',
     '<w:keepNext/><w:spacing w:before="163" w:beforeLines="50" w:after="163" w:afterLines="50"/><w:ind w:firstLine="0" w:firstLineChars="0"/>', ''),
    ('BRCoverNote', '报告-封面注记', '1',
     '<w:jc w:val="center"/><w:spacing w:before="240"/>',
     '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="21"/><w:szCs w:val="21"/>'),
    ('BRTocTitle', '报告-目录标题', '20',
     '<w:jc w:val="center"/>',
     '<w:rFonts w:ascii="黑体" w:hAnsi="黑体" w:eastAsia="黑体"/><w:sz w:val="36"/><w:szCs w:val="36"/>'),
]


def q(tag, ns=W):
    return '{%s}%s' % (ns, tag)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strip_noise(element):
    """Remove bookmarks, proofing marks, paragraph ids and revision ids from a copied fragment."""
    for tag in ('bookmarkStart', 'bookmarkEnd', 'proofErr'):
        for e in list(element.iter(q(tag))):
            e.getparent().remove(e)
    for e in element.iter():
        for attr in list(e.attrib):
            local = etree.QName(attr).localname
            if local.startswith('rsid') or (etree.QName(attr).namespace == W14 and local in ('paraId', 'textId')):
                del e.attrib[attr]


def export_library(doc, out_dir):
    rels = {rid: rel for rid, rel in doc.part.rels.items()}
    kids = list(doc.element.body)
    (out_dir / 'figures').mkdir(parents=True, exist_ok=True)
    (out_dir / 'fragments').mkdir(parents=True, exist_ok=True)

    def save_blip(rid, name):
        part = rels[rid].target_part
        ext = Path(str(part.partname)).suffix
        target = out_dir / 'figures' / f'{name}{ext}'
        target.write_bytes(part.blob)
        return target

    figures = []
    for name, (index, title) in FIGURES.items():
        blip = next(kids[index].iter(q('blip', A)))
        path = save_blip(blip.get(q('embed', R)), name)
        figures.append({'name': name, 'file': f'figures/{path.name}', 'title': title, 'source_element': index})
    six_path = out_dir / SIX_SPRING[1]
    if not six_path.is_file():
        raise SystemExit(f'缺少 {six_path}，请先按 manifest 说明从原报告 PDF 裁切生成。')
    figures.append({'name': SIX_SPRING[0], 'file': SIX_SPRING[1], 'title': SIX_SPRING[2], 'source_element': 176})

    fragments = []
    for name, (start, end, title) in FRAGMENTS.items():
        wrapper = etree.Element(q('body'), nsmap=doc.element.nsmap)
        for element in kids[start:end + 1]:
            wrapper.append(copy.deepcopy(element))
        strip_noise(wrapper)
        for n, blip in enumerate(wrapper.iter(q('blip', A)), start=1):
            path = save_blip(blip.get(q('embed', R)), f'{name}_{n}')
            blip.set(q('embed', R), f'LIB:{path.name}')
            figures.append({'name': path.stem, 'file': f'figures/{path.name}', 'title': f'{title}（嵌入图）', 'source_element': start})
        target = out_dir / 'fragments' / f'{name}.xml'
        target.write_bytes(etree.tostring(wrapper, xml_declaration=True, encoding='UTF-8'))
        fragments.append({'name': name, 'file': f'fragments/{name}.xml', 'title': title, 'source_elements': [start, end]})

    for item in figures + fragments:
        item['sha256'] = sha256(out_dir / item['file'])
    manifest = {'source': REFERENCE_76K.name, 'source_sha256': sha256(REFERENCE_76K),
                'note': '通用示意图与公式片段按原样抽取；片段中的图片以 LIB:文件名 引用，渲染时重新挂接。',
                'figures': figures, 'fragments': fragments}
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def section_paragraph(sect):
    p = etree.Element(q('p'))
    ppr = etree.SubElement(p, q('pPr'))
    ppr.append(sect)
    return p


def drop_even_references(sect):
    for ref in list(sect):
        if etree.QName(ref).localname in ('headerReference', 'footerReference') and ref.get(q('type')) == 'even':
            sect.remove(ref)


def set_single_run_text(paragraph, text):
    runs = paragraph.findall(q('r'))
    for extra in runs[1:]:
        paragraph.remove(extra)
    run = runs[0]
    for child in list(run):
        if etree.QName(child).localname != 'rPr':
            run.remove(child)
    t = etree.SubElement(run, q('t'))
    t.text = text


def part_by_name(doc, partname):
    return next(p for p in doc.part.package.iter_parts() if str(p.partname) == partname)


def rewrite_headers_footers(doc):
    header2 = part_by_name(doc, '/word/header2.xml').element
    set_single_run_text(header2.find(q('p')), '{{HEADER}}')
    footer3 = part_by_name(doc, '/word/footer3.xml').element
    set_single_run_text(footer3.findall(q('p'))[1], '{{ORG}}')
    header1 = part_by_name(doc, '/word/header1.xml').element
    for run in list(header1.iter(q('r'))):
        run.getparent().remove(run)


def referenced_rel_ids(element):
    ids = set()
    for e in element.iter():
        for attr, value in e.attrib.items():
            if etree.QName(attr).namespace == R:
                ids.add(value)
    return ids


def drop_orphan_relationships(doc):
    explicit = ('/image', '/oleObject', '/chart', '/header', '/footer', '/hyperlink', '/package')
    used = referenced_rel_ids(doc.element)
    for rid, rel in list(doc.part.rels.items()):
        if rid not in used and rel.reltype.endswith(explicit):
            del doc.part.rels[rid]


def add_report_styles(doc):
    styles = doc.styles.element
    for style_id, name, based_on, ppr, rpr in REPORT_STYLES:
        xml = (f'<w:style xmlns:w="{W}" w:type="paragraph" w:customStyle="1" w:styleId="{style_id}">'
               f'<w:name w:val="{name}"/><w:basedOn w:val="{based_on}"/><w:qFormat/>'
               f'<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')
        styles.append(etree.fromstring(xml))
    h1 = next(s for s in styles.findall(q('style')) if s.find(q('name')).get(q('val')) == 'heading 1')
    ppr = h1.find(q('pPr'))
    ppr.insert(0, etree.fromstring(f'<w:pageBreakBefore xmlns:w="{W}"/>'))
    ppr.append(etree.fromstring(f'<w:jc xmlns:w="{W}" w:val="center"/>'))


def style_ids(doc):
    ids = {}
    for s in doc.styles.element.findall(q('style')):
        name = s.find(q('name'))
        if name is not None:
            ids[name.get(q('val'))] = s.get(q('styleId'))
    wanted = ['Normal', 'heading 1', 'heading 2', 'heading 3', 'heading 4', 'toc 1', 'toc 2', 'toc 3', '图表', '正文表格图名', '封面1',
              'header', 'footer'] + [s[1] for s in REPORT_STYLES]
    return {name: ids[name] for name in wanted if name in ids}


def sect_spec(sect):
    size = sect.find(q('pgSz'))
    margin = sect.find(q('pgMar'))
    number = sect.find(q('pgNumType'))
    return {'pgSz': {k: int(size.get(q(k))) for k in ('w', 'h')},
            'pgMar': {k: int(margin.get(q(k))) for k in ('top', 'right', 'bottom', 'left', 'header', 'footer')},
            'page_number_start': int(number.get(q('start'))) if number is not None and number.get(q('start')) else None,
            'title_page': sect.find(q('titlePg')) is not None}


def build():
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document(str(REFERENCE_76K))
    manifest = export_library(doc, LIBRARY_DIR)

    body = doc.element.body
    kids = list(body)
    cover_sect = copy.deepcopy(kids[COVER_BREAK].find(q('pPr')).find(q('sectPr')))
    toc_sect = copy.deepcopy(kids[TOC_BREAK].find(q('pPr')).find(q('sectPr')))
    final_sect = body.find(q('sectPr'))
    for child in list(body):
        if child is not final_sect:
            body.remove(child)
    for sect in (toc_sect, final_sect):
        drop_even_references(sect)
    final_sect.addprevious(section_paragraph(cover_sect))
    final_sect.addprevious(section_paragraph(toc_sect))

    rewrite_headers_footers(doc)
    drop_orphan_relationships(doc)
    add_report_styles(doc)
    from visible_master import add_examples
    add_examples(doc)
    doc.core_properties.author = ''
    doc.core_properties.last_modified_by = ''
    doc.core_properties.title = ''
    doc.save(str(TEMPLATE_DOCX))

    spec = {
        'source': {'file': REFERENCE_76K.name, 'sha256': sha256(REFERENCE_76K)},
        'sections': [sect_spec(s) for s in (cover_sect, toc_sect, final_sect)],
        'styles': style_ids(doc),
        'fonts': {'east_asian': '宋体', 'latin': 'Times New Roman', 'toc_title': '黑体'},
        'cover': {'blank_before_title': 8, 'title_size_half_points': 52, 'blank_after_title': 11,
                  'organization_size_half_points': 30},
        'table': {'width_pct': 5000, 'outer': {'val': 'double', 'sz': 6}, 'inner': {'val': 'single', 'sz': 4},
                  'cell_margin_lr': 108, 'header_row_height': 564, 'body_row_height': 276,
                  'check_font_half_points': 22, 'data_font_half_points': 21},
        'caption': {'figure_style': 'BRFigCaption', 'table_style': 'BRTabCaption', 'figure_position': 'below',
                    'table_position': 'above'},
        'numbering': {'heading': ['{1}.', '{1}.{2}', '{1}.{2}.{3}'], 'figure_in_h2': '{h2}-{n}',
                      'figure_in_h1': '{h1}-{n}', 'equation': '（{h1}-{n}）'},
        'library': {'figures': len(manifest['figures']), 'fragments': len(manifest['fragments'])},
    }
    FORMAT_SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'母版：{TEMPLATE_DOCX}（{TEMPLATE_DOCX.stat().st_size // 1024} KB）')
    print(f"素材库：图 {len(manifest['figures'])} 个，片段 {len(manifest['fragments'])} 个")


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
