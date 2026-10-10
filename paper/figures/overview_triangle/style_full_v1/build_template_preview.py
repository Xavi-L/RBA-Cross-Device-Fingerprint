"""Copy the existing ACM preview sources; only the copied figure block changes.

Run after the candidate PDF renderer. No source manuscript writes, class
substitution, page geometry changes, height cap, or shell escape.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / 'output/pdf/hybridguard_triangle_template_preview'
DEST = HERE / 'template_preview'


def main():
    DEST.mkdir(exist_ok=True)
    inputs = {}
    for src in sorted(SOURCE.rglob('*')):
        if not src.is_file() or src.suffix not in {'.tex', '.cls', '.bst', '.bib'}:
            continue
        relative = src.relative_to(SOURCE)
        dest = DEST / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        inputs[str(relative)] = hashlib.sha256(src.read_bytes()).hexdigest()
    (DEST / 'SOURCE_MANIFEST.json').write_text(json.dumps({
        'source': str(SOURCE.relative_to(ROOT)),
        'class_options': 'sigconf,anonymous,review',
        'sha256': inputs,
        'copied_source_changes': ['figures/overview_figure.tex'],
        'formal_sources_written': False,
    }, indent=2) + '\n')
    shutil.copy2(HERE / 'HybridGuard_overview_candidate.pdf',
                 DEST / 'figures/HybridGuard_overview_candidate.pdf')
    figure = (SOURCE / 'figures/overview_figure.tex').read_text()
    caption = (HERE / 'CAPTIONS.md').read_text().split('## English\n\n', 1)[1].split('\n\n## 中文', 1)[0].strip()
    caption_tex = caption.replace('–', '--').replace('’', "'")
    figure = re.sub(r'\\caption\{[^\n]*\}', lambda _: '\\caption{' + caption_tex + '}', figure)
    figure = figure.replace('HybridGuard_overview_triangle.pdf', 'HybridGuard_overview_candidate.pdf')
    include = r'\includegraphics[width=\textwidth]{figures/HybridGuard_overview_candidate.pdf}'
    instrumentation = '\n'.join([
        r'\sbox{\HGgraphicbox}{' + include + '}',
        r'  \typeout{HG-TEXTWIDTH=\the\textwidth}',
        r'  \typeout{HG-TEXTHEIGHT=\the\textheight}',
        r'  \typeout{HG-GRAPHIC-WIDTH=\the\wd\HGgraphicbox}',
        r'  \typeout{HG-GRAPHIC-HEIGHT=\the\ht\HGgraphicbox}',
        r'  \typeout{HG-GRAPHIC-DEPTH=\the\dp\HGgraphicbox}',
        r'  \typeout{HG-BODY-FONT=\fontname\font}',
        r'  \usebox{\HGgraphicbox}',
    ])
    measurement_hook = '\n'.join([
        r'\newsavebox{\HGgraphicbox}',
        r'\begingroup',
        r'\makeatletter',
        r'\let\HGoriginalendfloatbox\@endfloatbox',
        r'\def\@endfloatbox{\HGoriginalendfloatbox',
        r'  \typeout{HG-FLOAT-HEIGHT=\the\ht\@currbox}',
        r'  \typeout{HG-FLOAT-DEPTH=\the\dp\@currbox}}',
        r'\makeatother',
        '',
    ])
    figure = measurement_hook + figure.replace(include, instrumentation) + '\\endgroup\n'
    (DEST / 'figures/overview_figure.tex').write_text(figure)
    command = ['/Library/TeX/texbin/latexmk', '-pdf', '-bibtex',
               '-interaction=nonstopmode', '-halt-on-error', 'hybridguard_draft.tex']
    with (DEST / 'build_console.txt').open('w') as output:
        result = subprocess.run(command, cwd=DEST, stdout=output, stderr=subprocess.STDOUT)
    print(json.dumps({'returncode': result.returncode, 'preview': str(DEST), 'command': command}))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
