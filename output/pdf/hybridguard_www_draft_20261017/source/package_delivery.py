#!/usr/bin/env python3
"""Package the reviewed source and copy the polished matrix PDF."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT.parent / 'output' / 'pdf'
TOP = ['README.md', 'main.tex', 'main_matrix.tex', 'frontmatter.tex',
       'table_visuals.tex', 'acmart.cls', 'ACM-Reference-Format.bst', 'references.bib']
TREES = ['sections', 'tables', 'floats', 'figures', 'input_markdown',
         'data', 'notes', 'source', 'reviews']
BASELINE = ['baseline_source/main.tex', 'baseline_source/abstract_verbatim.txt',
            'baseline_source/provenance.json']


def atomic_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.delivery-', dir=path.parent)
    with os.fdopen(fd, 'wb') as out:
        out.write(content)
        out.flush()
        os.fsync(out.fileno())
    os.replace(name, path)


def main():
    paths = [ROOT / name for name in TOP + BASELINE]
    for tree in TREES + ['baseline_source/table_evidence']:
        paths.extend(p for p in (ROOT / tree).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and not p.name.startswith('.'))
    paths.extend(p for p in (ROOT / 'qa').rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts
                 and not any(part.startswith('render') for part in p.relative_to(ROOT/'qa').parts)
                 and p != ROOT / 'qa/package_manifest.json')
    paths = sorted(set(paths))
    assert all(p.is_file() for p in paths)
    manifest = {'date': '2026-10-22', 'hash': 'sha256',
                'scope': 'All ZIP members except this manifest itself.', 'files': {}}
    for path in paths:
        data = path.read_bytes()
        manifest['files'][path.relative_to(ROOT).as_posix()] = {
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    manifest_path = ROOT / 'qa/package_manifest.json'
    atomic_bytes(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2)
                                + '\n').encode())
    paths.append(manifest_path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.source-', suffix='.zip', dir=OUTPUT)
    os.close(fd)
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(paths):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),
                                   date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    destination = OUTPUT / 'HybridGuard_LaTeX_v1.zip'
    os.replace(name, destination)
    deliveries = [destination]
    for variant, filename in [('matrix', 'HybridGuard_layout_v1_matrix.pdf')]:
        target = OUTPUT / filename
        atomic_bytes(target, (ROOT / 'build' / variant / filename).read_bytes())
        deliveries.append(target)
    print(json.dumps([{'path': str(p), 'bytes': p.stat().st_size,
                       'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in deliveries], indent=2))


if __name__ == '__main__':
    main()
