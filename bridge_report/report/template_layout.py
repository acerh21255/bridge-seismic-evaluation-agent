"""Shared structural contract for visible and legacy style-only report masters."""
import copy
from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def section_holders(document):
    body = document.element.body
    holders = [p for p in body.findall(W + 'p') if p.find(W + 'pPr/' + W + 'sectPr') is not None]
    if len(holders) != 2 or len(list(body.iter(W + 'sectPr'))) != 3 or body.find(W + 'sectPr') is None:
        raise ValueError('母版须保留封面、目录、正文三个分节，请基于系统母版修改。')
    return holders


def clear_examples(document):
    """Keep edited section geometry, styles and headers; never leak sample text into reports."""
    holders = section_holders(document)
    sections = [copy.deepcopy(p.find(W + 'pPr/' + W + 'sectPr')) for p in holders]
    body = document.element.body
    final = body.find(W + 'sectPr')
    for child in list(body):
        if child is not final:
            body.remove(child)
    for section in sections:
        paragraph = etree.Element(W + 'p')
        etree.SubElement(paragraph, W + 'pPr').append(section)
        final.addprevious(paragraph)
    return section_holders(document)
