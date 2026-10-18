"""HTML rendering of the report model: a lightweight preview when Word is unavailable and a shareable summary."""
import base64
import html
import io
from pathlib import Path

from lxml import etree

from ..paths import LIBRARY_DIR
from . import omml
from .model import Equation, Figure, FigureRow, Fragment, Heading, PageBreak, Para, Picture, Table

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
MAX_PX = 900
CSS = """
body{margin:0;background:#e9edf1;font:15px/1.9 'Times New Roman','SimSun','Songti SC',serif;color:#111}
.page{max-width:794px;margin:24px auto;background:#fff;padding:72px 80px;box-shadow:0 2px 12px rgba(0,0,0,.12)}
.cover{text-align:center;padding-top:160px;min-height:900px}
.cover h1{font-size:26px;line-height:1.6;margin:0;font-weight:700}
.cover .org{margin-top:260px;font-size:20px}
.cover .note{margin-top:18px;font-size:13px;color:#555}
.hdr{font-size:12px;border-bottom:1.5px solid #000;padding-bottom:4px;margin-bottom:28px;text-align:center}
h2.h1{font-size:21px;text-align:center;margin:48px 0 12px}
h3.h2{font-size:20px;margin:18px 0 8px}
h4.h3{font-size:18px;margin:14px 0 6px}
h5.h4{font-size:16px;font-weight:400;margin:10px 0 4px}
p{margin:0;text-indent:2em;text-align:justify}
p.plain,p.center,p.note{text-indent:0}
p.center{text-align:center}
p.note{font-size:14px}
.cap{text-align:center;font-weight:700;font-size:14px;margin:8px 0;text-indent:0}
figure{margin:12px 0;text-align:center}
figure img{max-width:100%}
.sub{font-size:14px;text-align:center;text-indent:0}
.missing{border:1px dashed #888;color:#777;padding:28px;font-size:14px;text-indent:0}
table{border-collapse:collapse;margin:0 auto 10px;width:100%;font-size:14px}
table.check{border:3px double #000}
td,th{border:1px solid #000;padding:2px 6px;text-align:center;vertical-align:middle}
th{font-weight:700}
.eq{text-align:center;text-indent:0;font-style:italic;margin:6px 0}
.eq span{float:right;font-style:normal}
.frag p{text-indent:2em}
"""


def esc(value):
    return html.escape('' if value is None else str(value), quote=True)


def runs_html(runs):
    parts = []
    for run in runs:
        if run.math is not None:
            parts.append(f'<i>{esc(omml.to_text(run.math))}</i>')
        elif run.sub:
            parts.append(f'<sub>{esc(run.text)}</sub>')
        elif run.sup:
            parts.append(f'<sup>{esc(run.text)}</sup>')
        elif run.bold:
            parts.append(f'<b>{esc(run.text)}</b>')
        else:
            parts.append(esc(run.text))
    return ''.join(parts)


def image_uri(path):
    """Downscaled JPEG data URI keeps the single-file HTML reasonably small."""
    from PIL import Image
    with Image.open(path) as image:
        image = image.convert('RGB')
        if image.width > MAX_PX:
            image = image.resize((MAX_PX, round(image.height * MAX_PX / image.width)))
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=80)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def figure_html(figure):
    parts = ['<figure>']
    subcaptions = figure.subcaptions or []
    for n, (image, _) in enumerate(figure.images()):
        if image and Path(image).is_file():
            parts.append(f'<img alt="{esc(figure.caption)}" src="{image_uri(image)}">')
        else:
            parts.append(f'<div class="missing">【图件待补充】{esc(figure.caption)}</div>')
        if n < len(subcaptions) and subcaptions[n]:
            parts.append(f'<div class="sub">{esc(subcaptions[n])}</div>')
    parts.append(f'<figcaption class="cap">图{esc(figure.label)} {esc(figure.caption)}</figcaption></figure>')
    return ''.join(parts)


def table_html(table):
    rows = []
    for index, row in enumerate(table.header + table.rows):
        tag = 'th' if index < len(table.header) else 'td'
        cells = []
        for n, cell in enumerate(row):
            if cell.vmerge == 'continue':
                continue
            span = ''
            if cell.vmerge == 'restart':
                depth = 1
                for later in (table.header + table.rows)[index + 1:]:
                    if n < len(later) and later[n].vmerge == 'continue':
                        depth += 1
                    else:
                        break
                span += f' rowspan="{depth}"'
            if cell.span > 1:
                span += f' colspan="{cell.span}"'
            content = runs_html(cell.runs)
            cells.append(f'<{tag}{span}>{"<b>" + content + "</b>" if cell.bold and tag == "td" else content}</{tag}>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    caption = f'<div class="cap">表{esc(table.label)} {esc(table.caption)}</div>' if table.caption else ''
    notes = ''.join(f'<p class="note">{runs_html(n.runs)}</p>' for n in table.notes)
    return f'{caption}<table class="{esc(table.kind)}">{"".join(rows)}</table>{notes}'


def fragment_html(name):
    root = etree.parse(str(LIBRARY_DIR / 'fragments' / f'{name}.xml')).getroot()
    parts = ['<div class="frag">']
    for child in root:
        local = etree.QName(child).localname
        if local == 'tbl':
            for tr in child.iter('{%s}tr' % W):
                cells = [_text(tc) for tc in tr.iter('{%s}tc' % W)]
                parts.append('<p class="eq">' + esc(cells[0]) + (f'<span>{esc(cells[-1])}</span>' if len(cells) > 1 else '') + '</p>')
        elif local == 'p':
            text = _text(child)
            if text:
                parts.append(f'<p>{esc(text)}</p>')
    parts.append('</div>')
    return ''.join(parts)


def _text(element):
    out = []
    for node in element.iter():
        if node.tag in ('{%s}t' % W, '{%s}t' % M):
            out.append(node.text or '')
    return ''.join(out).strip()


def block_html(block):
    if isinstance(block, Heading):
        title = f'{block.label} {block.title}' if block.label else block.title
        return f'<h{block.level + 1} class="h{block.level}">{esc(title)}</h{block.level + 1}>'
    if isinstance(block, Para):
        return f'<p class="{esc(block.style)}">{runs_html(block.runs)}</p>'
    if isinstance(block, Figure):
        return figure_html(block)
    if isinstance(block, FigureRow):
        return ''.join(figure_html(f) for f in block.figures)
    if isinstance(block, Table):
        return table_html(block)
    if isinstance(block, Equation):
        number = f'<span>（{esc(block.label)}）</span>' if block.numbered else ''
        return f'<p class="eq">{esc(omml.to_text(block.omml))}{number}</p>'
    if isinstance(block, Fragment):
        return fragment_html(block.name)
    if isinstance(block, Picture):
        return f'<figure><img alt="公式" src="{image_uri(block.image)}"></figure>' if block.image else ''
    if isinstance(block, PageBreak):
        return ''
    raise TypeError(type(block).__name__)


def write_html(doc, path):
    meta = doc.meta
    cover = ''.join(f'<h1>{esc(line)}</h1>' for line in meta['cover_lines'])
    note = f'<div class="note">{esc(meta["cover_note"])}</div>' if meta.get('cover_note') else ''
    body = ''.join(block_html(block) for block in doc.blocks)
    page = (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(meta.get("title"))}</title>'
            f'<style>{CSS}</style></head><body>'
            f'<section class="page cover">{cover}<div class="org">{esc(meta["organization"])}<br>{esc(meta["date"])}</div>{note}</section>'
            f'<section class="page"><div class="hdr">{esc(meta["header_text"])}</div>{body}</section></body></html>')
    Path(path).write_text(page, encoding='utf-8')
    return Path(path)
