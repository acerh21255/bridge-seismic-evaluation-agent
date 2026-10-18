"""Reproducible, read-only import of the two local source models and drawing previews."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_report.server.assets import sap_geometry
import pypdfium2 as pdfium

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path, help='包含两个原始桥梁资料文件夹的目录')
CASES = {
    'golden-76K': ('76K278+308', '0.15改0.1g-NEW/0.10g.$2k', '76K278+308.pdf'),
    'golden-53K': ('53K271+730', '0424抗滑所有new/SAP/E1反应谱/E1.$2k', '53K271+730.pdf'),
}


def main():
    source = parser.parse_args().source
    out = ROOT / 'examples/visuals'
    out.mkdir(exist_ok=True)
    for ident, (bridge, model, drawing) in CASES.items():
        folder = source / bridge
        raw = (folder / model).read_bytes()
        geometry = sap_geometry(raw.decode('utf-8-sig', errors='replace'))
        with pdfium.PdfDocument(folder / drawing) as pdf:
            # Show full first sheet, preserving the source drawing's aspect ratio.
            selected = 12 if ident == 'golden-76K' else 13
            page = pdf[selected]
            page.render(scale=min(2, 2400 / max(page.get_size()))).to_pil().convert('RGB').save(out / (ident + '.jpg'), quality=93)
            count = len(pdf)
        data = {'geometry': geometry, 'preview': f'/api/visuals/{ident}.jpg', 'drawing_pages': count,
                'drawing_name': drawing, 'drawing_page': selected + 1, 'model_name': model,
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'note': '原始图纸预览与 SAP 文本模型重建。显示结构拓扑，不代表重新运行 SAP 求解，也不是照片级外观。'}
        (out / (ident + '.json')).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        print(ident, len(geometry['nodes']), len(geometry['edges']), geometry['source_units'])


if __name__ == '__main__':
    main()
