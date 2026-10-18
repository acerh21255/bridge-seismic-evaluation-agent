"""Report document model: blocks, inline runs, numbering and cross references.

Chapter builders emit blocks in document order; finalize() assigns heading, figure, table and
equation labels (sample conventions: 6.3 / 表6.3-1 / 图8-1 / （7-1）) and resolves Run.ref keys.
"""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Run:
    text: str = ''
    sub: bool = False
    sup: bool = False
    italic: bool = False
    bold: bool = False
    math: object = None
    ref: str | None = None


@dataclass
class Heading:
    level: int
    title: str
    numbered: bool = True
    key: str | None = None
    label: str = ''


@dataclass
class Para:
    runs: list
    style: str = 'body'


@dataclass
class Figure:
    """One caption over one or more stacked images; subcaptions label the stacked images."""
    key: str
    caption: str
    image: Path | list | None = None
    width_cm: float | list | None = None
    subcaptions: list | None = None
    label: str = ''

    def images(self):
        images = self.image if isinstance(self.image, (list, tuple)) else [self.image]
        widths = self.width_cm if isinstance(self.width_cm, (list, tuple)) else [self.width_cm] * len(images)
        return list(zip(images, widths))


@dataclass
class FigureRow:
    figures: list


@dataclass
class Picture:
    """Uncaptioned centered image, e.g. a formula scanned as a picture."""
    image: Path | None
    width_cm: float | None = None


@dataclass
class Cell:
    runs: list
    bold: bool = False
    vmerge: str | None = None
    span: int = 1
    nowrap: bool = False


@dataclass
class Table:
    key: str | None
    caption: str | None
    header: list
    rows: list
    notes: list = field(default_factory=list)
    kind: str = 'check'
    widths: list | None = None
    label: str = ''


@dataclass
class Equation:
    omml: object
    key: str | None = None
    numbered: bool = False
    label: str = ''


@dataclass
class Fragment:
    name: str


@dataclass
class PageBreak:
    pass


@dataclass
class ReportDoc:
    meta: dict
    blocks: list
    labels: dict = field(default_factory=dict)


def text_runs(*items):
    """Build a run list from strings and Run objects."""
    return [item if isinstance(item, Run) else Run(str(item)) for item in items]


def iter_runs(doc):
    for block in doc.blocks:
        if isinstance(block, Para):
            yield from block.runs
        elif isinstance(block, Table):
            for row in block.header + block.rows:
                for cell in row:
                    yield from cell.runs
            for note in block.notes:
                yield from note.runs


class _Counter:
    def __init__(self):
        self.heading = [0, 0, 0]
        self.scope = ''
        self.figure = 0
        self.table = 0
        self.equation = 0
        self.labels = {}

    def register(self, key, label):
        if key is None:
            return
        if key in self.labels:
            raise ValueError(f'报告编号键重复：{key}')
        self.labels[key] = label

    def heading_label(self, level):
        self.heading[level - 1] += 1
        for i in range(level, 3):
            self.heading[i] = 0
        parts = [str(n) for n in self.heading[:level]]
        if level == 1:
            self.scope = parts[0]
            self.figure = self.table = self.equation = 0
            return parts[0] + '.'
        if level == 2:
            self.scope = '.'.join(parts)
            self.figure = self.table = 0
        return '.'.join(parts)

    def figure_label(self):
        self.figure += 1
        return f'{self.scope}-{self.figure}'

    def table_label(self):
        self.table += 1
        return f'{self.scope}-{self.table}'

    def equation_label(self):
        self.equation += 1
        return f'{self.heading[0]}-{self.equation}'


def finalize(doc):
    counter = _Counter()
    for block in doc.blocks:
        if isinstance(block, Heading) and block.numbered and block.level <= 3:
            block.label = counter.heading_label(block.level)
            counter.register(block.key, block.label.rstrip('.'))
        elif isinstance(block, Figure):
            block.label = counter.figure_label()
            counter.register(block.key, '图' + block.label)
        elif isinstance(block, FigureRow):
            for figure in block.figures:
                figure.label = counter.figure_label()
                counter.register(figure.key, '图' + figure.label)
        elif isinstance(block, Table) and block.caption:
            block.label = counter.table_label()
            counter.register(block.key, '表' + block.label)
        elif isinstance(block, Equation) and block.numbered:
            block.label = counter.equation_label()
            counter.register(block.key, f'（{block.label}）')
    doc.labels = counter.labels
    for run in iter_runs(doc):
        if run.ref is not None:
            run.text = doc.labels[run.ref]
    return doc
