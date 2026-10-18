"""Shared helpers for chapter builders: data access, rich text, number formatting and table construction."""
import re
from pathlib import Path

from ...engine.terms import INPUT_LABELS
from ..model import Cell, Equation, Figure, FigureRow, Fragment, Heading, Para, Picture, Run, Table

MARKUP = re.compile(r'([_^])\{([^{}]*)\}')
EMPHASIS = ('强度破坏', '剪切破坏', '进入屈服', '进入塑性', '不满足', '待补正')
FALLBACK = '（资料未提供）'


def rich(text):
    """Parse `_{sub}` / `^{sup}` markup into runs."""
    text = '' if text is None else str(text)
    runs, pos = [], 0
    for match in MARKUP.finditer(text):
        if match.start() > pos:
            runs.append(Run(text[pos:match.start()]))
        runs.append(Run(match.group(2), sub=match.group(1) == '_', sup=match.group(1) == '^'))
        pos = match.end()
    if pos < len(text) or not runs:
        runs.append(Run(text[pos:]))
    return runs


def plain(text):
    return MARKUP.sub(lambda m: m.group(2), '' if text is None else str(text))


def fmt(value, decimals=None):
    if value is None:
        return '—'
    if isinstance(value, str):
        return value
    if decimals is not None:
        return f'{value:.{decimals}f}'
    if float(value).is_integer():
        return str(int(value))
    return f'{value:.6f}'.rstrip('0').rstrip('.')


def ratio_text(value):
    return '—' if value is None else f'{value:.3f}'


def ref(key):
    return Run(ref=key)


def cell(text, bold=False, vmerge=None, span=1, nowrap=False):
    runs = text if isinstance(text, list) else rich(text)
    return Cell(runs, bold=bold, vmerge=vmerge, span=span, nowrap=nowrap)


def verdict_cell(verdict):
    return cell(verdict, bold=verdict in EMPHASIS, nowrap=True)


class Builder:
    def __init__(self, package, result, workdir):
        self.package = package
        self.data = package.data
        self.result = result
        self.workdir = Path(workdir)
        self.blocks = []
        self.missing = []
        self.assets = package.assets()

    # -- data access ---------------------------------------------------------------------------------
    def get(self, path, default=None, note=None):
        value = self.data
        for part in path.split('.'):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break
        if value in (None, '', [], {}):
            if note:
                self.missing.append(note)
            return default
        return value

    @property
    def short(self):
        return self.get('project.short_name', self.get('bridge_id', '本桥'))

    def asset(self, asset_id, what):
        """Return (path, width_cm, caption) for an asset id; records a missing note when unavailable."""
        entry = self.assets.get(asset_id) if asset_id else None
        path = self.package.asset_path(asset_id) if asset_id else None
        if path is None:
            self.missing.append(f'图件缺失：{what}')
        return path, (entry or {}).get('width_cm'), (entry or {}).get('caption')

    def items(self, stage='original', **filters):
        return [i for i in self.result.get('items', []) if i['stage'] == stage and all(i.get(k) == v for k, v in filters.items())]

    # -- block emitters -------------------------------------------------------------------------------
    def add(self, block):
        self.blocks.append(block)
        return block

    def h(self, level, title, key=None, numbered=True):
        return self.add(Heading(level, title, numbered=numbered and level <= 3, key=key))

    def p(self, *parts, style='body'):
        runs = []
        for part in parts:
            if isinstance(part, Run):
                runs.append(part)
            elif isinstance(part, list):
                runs.extend(part)
            else:
                runs.extend(rich(part))
        return self.add(Para(runs, style=style))

    def note(self, *parts):
        return self.p(*parts, style='note')

    def figure(self, key, caption=None, asset_id=None, what=None, image=None, width_cm=None, subcaptions=None, default=None):
        """Caption precedence: explicit caption, then the asset's caption, then `default`."""
        if asset_id is not None or what is not None:
            image, asset_width, asset_caption = self.asset(asset_id, what or caption or default)
            width_cm = width_cm or asset_width
            caption = caption or asset_caption
        return self.add(Figure(key, caption or default, image=image, width_cm=width_cm, subcaptions=subcaptions))

    def figure_row(self, figures):
        return self.add(FigureRow(figures))

    def picture(self, path, width_cm=None):
        return self.add(Picture(path, width_cm))

    def equation(self, omml, key=None, numbered=False):
        return self.add(Equation(omml, key=key, numbered=numbered))

    def fragment(self, name):
        return self.add(Fragment(name))

    def data_table(self, key, caption, table, notes=(), widths=None, merge_first=False):
        """Reference-data table from {'header': [...], 'rows': [[...]]}; empty cells continue a vertical merge."""
        header = [[cell(h) for h in table['header']]]
        rows = []
        for r, row in enumerate(table['rows']):
            cells = []
            for c, text in enumerate(row):
                if merge_first and c == 0:
                    starts = text != ''
                    continues = r + 1 < len(table['rows']) and table['rows'][r + 1][0] == ''
                    vmerge = 'continue' if not starts else ('restart' if continues else None)
                    cells.append(cell('' if not starts else text, vmerge=vmerge))
                else:
                    cells.append(cell(text))
            rows.append(cells)
        if any('—' in str(v) for row in rows for v in row) and not notes:
            notes = ['表中 — 表示资料未提供或本项未开展，须结合验算结论核对。']
        return self.add(Table(key, caption, header, rows, notes=[Para(rich(n), style='note') for n in notes], kind='data',
                              widths=widths))

    def check_table(self, key, caption, headers, items, values, widths=None, notes=()):
        """Verification table: first column is the merged seismic input label, last column the verdict."""
        last = len(headers) - 1
        header = [[cell(h, bold=True, nowrap=c in (0, 1, last)) for c, h in enumerate(headers)]]
        rows = []
        for n, item in enumerate(items):
            label = INPUT_LABELS.get(item.get('direction'), '')
            if len(items) == 1:
                first = cell(label, nowrap=True)
            else:
                first = cell(label if n == 0 else '', vmerge='restart' if n == 0 else 'continue', nowrap=True)
            values_ = values(item)
            rows.append([first, cell(values_[0], nowrap=True)] + [cell(v) for v in values_[1:]] + [verdict_cell(item['verdict'])])
        if any('—' in str(v) for row in rows for v in row):
            notes = list(notes) + ['表中 — 表示原始资料未提供或因前置条件未满足而未开展本项验算，不表示数值为零。']
        return self.add(Table(key, caption, header, rows, notes=[Para(rich(n), style='note') for n in notes], widths=widths))
