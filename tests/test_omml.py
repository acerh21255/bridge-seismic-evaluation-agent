import unittest

from bridge_report.report import omml


class OmmlTests(unittest.TestCase):
    def test_bearing_stiffness_formula(self):
        m = omml.math('k=', omml.frac(omml.sub('F', omml.text('max')), omml.sub('x', 'y')), '=',
                      omml.frac('15.04', '0.002'), '=7520.1', omml.text(' kN/m'))
        self.assertEqual(etree_local(m), 'oMath')
        self.assertEqual(omml.to_text(m), 'k=Fmax/xy=15.04/0.002=7520.1 kN/m')
        self.assertEqual(len(m.findall('.//' + omml.q('f'))), 2)
        self.assertEqual(len(m.findall('.//' + omml.q('sSub'))), 2)

    def test_upright_text_run(self):
        run = omml.text('max')
        self.assertIsNotNone(run.find(omml.q('rPr')).find(omml.q('nor')))
        self.assertEqual(run.find(omml.q('rPr')).find(omml.q('sty')).get(omml.q('val')), 'p')

    def test_italic_math_run_uses_cambria(self):
        run = omml.r('F')
        fonts = run.find(omml.qw('rPr')).find(omml.qw('rFonts'))
        self.assertEqual(fonts.get(omml.qw('ascii')), 'Cambria Math')

    def test_display_wrapper(self):
        p = omml.display(omml.math('V≤', omml.sub('V', 'cs')))
        self.assertEqual(etree_local(p), 'oMathPara')
        self.assertEqual(omml.to_text(p), 'V≤Vcs')

    def test_sup_and_subsup(self):
        m = omml.math(omml.sup('H', '2'), '+', omml.subsup('f', 'cu,k', '0.55'))
        self.assertEqual(omml.to_text(m), 'H^2+fcu,k^0.55')


def etree_local(element):
    return element.tag.rsplit('}', 1)[1]


if __name__ == '__main__':
    unittest.main()
