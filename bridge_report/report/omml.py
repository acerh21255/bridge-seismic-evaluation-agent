"""Word native equation (OMML) builders following the reference report conventions."""
from lxml import etree

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NSMAP = {'m': M, 'w': W}


def q(tag):
    return '{%s}%s' % (M, tag)


def qw(tag):
    return '{%s}%s' % (W, tag)


def _element(tag):
    return etree.Element(q(tag), nsmap=NSMAP)


def _fonts(parent, font):
    rpr = etree.SubElement(parent, qw('rPr'))
    etree.SubElement(rpr, qw('rFonts'), {qw('ascii'): font, qw('hAnsi'): font, qw('cs'): 'Times New Roman'})
    return rpr


def r(text):
    """Italic math run (letters render italic, digits and operators upright)."""
    run = _element('r')
    etree.SubElement(run, q('rPr'))
    _fonts(run, 'Cambria Math')
    etree.SubElement(run, q('t')).text = text
    return run


def text(value):
    """Upright normal-text run inside an equation, e.g. subscripts like max or units."""
    run = _element('r')
    mpr = etree.SubElement(run, q('rPr'))
    etree.SubElement(mpr, q('nor'))
    etree.SubElement(mpr, q('sty'), {q('val'): 'p'})
    rpr = _fonts(run, 'Times New Roman')
    etree.SubElement(rpr, qw('b'), {qw('val'): '0'})
    etree.SubElement(rpr, qw('i'), {qw('val'): '0'})
    etree.SubElement(run, q('t')).text = value
    return run


def _append(parent, part):
    parent.append(r(part) if isinstance(part, str) else part)


def _box(tag, *parts):
    box = _element(tag)
    for part in parts:
        _append(box, part)
    return box


def sub(base, subscript):
    node = _element('sSub')
    node.append(_box('e', base))
    node.append(_box('sub', subscript))
    return node


def sup(base, superscript):
    node = _element('sSup')
    node.append(_box('e', base))
    node.append(_box('sup', superscript))
    return node


def subsup(base, subscript, superscript):
    node = _element('sSubSup')
    node.append(_box('e', base))
    node.append(_box('sub', subscript))
    node.append(_box('sup', superscript))
    return node


def frac(numerator, denominator):
    node = _element('f')
    node.append(_box('num', numerator))
    node.append(_box('den', denominator))
    return node


def math(*parts):
    node = _element('oMath')
    for part in parts:
        _append(node, part)
    return node


def display(math_element):
    node = _element('oMathPara')
    node.append(math_element)
    return node


def to_text(element):
    """Linear text for previews and checks: fractions as a/b, superscripts as ^x."""
    tag = etree.QName(element).localname
    if tag == 't':
        return element.text or ''
    if tag == 'f':
        num = element.find(q('num'))
        den = element.find(q('den'))
        return f'{to_text(num)}/{to_text(den)}'
    if tag in ('sSup', 'sSubSup'):
        base = to_text(element.find(q('e')))
        lower = to_text(element.find(q('sub'))) if element.find(q('sub')) is not None else ''
        return f'{base}{lower}^{to_text(element.find(q("sup")))}'
    return ''.join(to_text(child) for child in element if etree.QName(child).namespace == M)
