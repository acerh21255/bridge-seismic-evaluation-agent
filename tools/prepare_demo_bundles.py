"""Copy original evidence and build portable demo handoff ZIPs, without changing sources."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    '76K278+308': ('0.15改0.1g-NEW', '0.10g.$2k'),
    '53K271+730': ('0424抗滑所有new', 'SAP/E1反应谱/E1.$2k'),
}


def prepare(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'bridge_report/report/template/lab_template.docx', destination / '系统报告母版.docx')
    for case, (revision, model) in CASES.items():
        folder = destination / case
        folder.mkdir(exist_ok=True)
        golden = ROOT / 'examples/golden' / case
        shutil.copytree(golden, folder / '交接包', dirs_exist_ok=True)
        with zipfile.ZipFile(folder / f'{case}-交接包.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(golden.rglob('*')):
                if file.is_file():
                    archive.write(file, file.relative_to(golden).as_posix())
        base = source / case
        drawing = base / f'{case}.pdf'
        if not drawing.exists():
            drawing = source / f'{case}.pdf'
        files = [(drawing, Path('图纸') / drawing.name),
                 (base / revision / model, Path('模型') / revision / model)]
        files += [(f, Path('验算表') / f.relative_to(base)) for f in sorted(base.glob('*.xlsx')) if not f.name.startswith('~$')]
        files += [(f, Path('验算表') / f.relative_to(base)) for f in sorted((base / revision).rglob('*.xlsx')) if not f.name.startswith('~$')]
        reference = next((ROOT / 'templates/reference').glob(f'*{case}*.docx'))
        files.append((reference, Path('原报告') / reference.name))
        records = []
        for original, relative in files:
            target = folder / '原始资料' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
            records.append({'file': str(target.relative_to(folder)), 'source': str(original.resolve()),
                            'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        (folder / '资料清单.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        (folder / '测试说明.md').write_text(
            f'# {case} 测试包\n\n'
            f'1. 在工作台左侧“导入交接包”中选择 `{case}-交接包.zip`，图件已包含在 ZIP 内。\n'
            '2. 在“选择原始资料”中按需上传原始资料目录内的 PDF、SAP 文本模型（.$2k）和 Excel。\n'
            '3. 点击“识别并检查交接资料”，核对桥梁和模型版本后勾选确认，再生成离线报告。\n'
            '4. 可在模型设置页填写服务商地址、模型 ID 和密钥，测试通过后切换真实模型。\n\n'
            '交接数据来自现有原报告复现案例；原始表格仅作为核对证据，未自动覆盖交接数值。'
            '保留既有缺项和不满足结论，未重新运行 SAP 求解。资料清单记录来源及 SHA256。\n', encoding='utf-8')
        print(case, len(records), 'original files; ZIP ready')
    (destination / 'README.md').write_text(
        '# 两个 Demo 测试资料\n\n每个案例包含可直接导入的交接包 ZIP、解压目录、原始图纸 PDF、'
        'SAP 文本模型、原始 Excel 验算表、原报告及来源清单。\n\n'
        '请先阅读各案例的测试说明。系统报告母版.docx 可直接编辑后上传工作台。\n'
        '资料仅用于已有案例的流程测试和原报告复现。\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / '测试资料')
    args = parser.parse_args()
    prepare(args.source, args.out)
