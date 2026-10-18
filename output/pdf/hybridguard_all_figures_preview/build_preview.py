"""Insert the accepted figures into an isolated copy of the existing ACM draft."""
from pathlib import Path
import json
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'output/pdf/hybridguard_triangle_template_preview'
FIGURES = ROOT / 'paper/figures'
OVERVIEW = FIGURES / 'overview_triangle/style_full_v1'
F01 = FIGURES / 'f01_app_detection/style_www_v1'
F03 = FIGURES / 'f03a_f04_mechanisms/style_www_v1'
F05 = FIGURES / 'f05a_cross_endpoint/style_www_v1'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def outside_status():
    prefix = str(HERE.relative_to(ROOT)).encode() + b'/'
    tokens = git('status', '--porcelain=v1', '-z', '--untracked-files=all').split(b'\0')
    records = []
    i = 0
    while i < len(tokens) - 1:
        record = [tokens[i]]
        code = tokens[i][:2]
        i += 1
        if b'R' in code or b'C' in code:
            record.append(tokens[i])
            i += 1
        if not record[0][3:].startswith(prefix):
            records.append(record)
    return records


def copy(src, relative):
    target = HERE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return {'source': str(src.relative_to(ROOT)), 'destination': relative}


def measure(text, prefix, boxname):
    match = re.search(r'\\includegraphics\[([^\]]+)\]\{([^}]+)\}', text)
    assert match
    slash = chr(92)
    replacement = '\n'.join([
        r'\sbox{' + slash + boxname + '}{' + match[0] + '}',
        r'\typeout{' + prefix + r'-TEXTWIDTH=\the\textwidth}',
        r'\typeout{' + prefix + r'-COLUMNWIDTH=\the\columnwidth}',
        r'\typeout{' + prefix + r'-TEXTHEIGHT=\the\textheight}',
        r'\typeout{' + prefix + r'-GRAPHIC-WIDTH=\the\wd' + slash + boxname + '}',
        r'\typeout{' + prefix + r'-GRAPHIC-HEIGHT=\the\ht' + slash + boxname + '}',
        r'\typeout{' + prefix + r'-GRAPHIC-DEPTH=\the\dp' + slash + boxname + '}',
        r'\usebox{' + slash + boxname + '}',
    ])
    hooks = '\n'.join([
        r'\newsavebox{' + slash + boxname + '}', r'\begingroup', r'\makeatletter',
        r'\let\PreviewEndFloatBox\@endfloatbox',
        r'\def\@endfloatbox{\PreviewEndFloatBox',
        r'\typeout{' + prefix + r'-FLOAT-HEIGHT=\the\ht\@currbox}',
        r'\typeout{' + prefix + r'-FLOAT-DEPTH=\the\dp\@currbox}}',
        r'\makeatother', '',
    ])
    return hooks + text.replace(match[0], replacement) + '\\endgroup\n'


def main():
    before = outside_status()
    head = git('rev-parse', 'HEAD')
    index = git('diff', '--cached', '--name-status', '-z')
    copied = []
    for src in sorted(SOURCE.rglob('*')):
        if src.is_file() and src.suffix in {'.tex', '.cls', '.bst', '.bib'}:
            copied.append(copy(src, str(src.relative_to(SOURCE))))

    artwork = []
    for src in [OVERVIEW / 'HybridGuard_overview_candidate.pdf',
                F01 / 'F01_main_rev4.pdf', F03 / 'F03a_F04_main.pdf', F05 / 'F05a_main.pdf']:
        artwork.append(copy(src, 'figures/' + src.name))
    overview_fragment = OVERVIEW / 'template_preview/figures/overview_figure.tex'
    copy(overview_fragment, 'figures/overview_figure.tex')

    old_f01 = (F01 / 'template_preview_rev4/figures/overview_figure.tex').read_text()
    caption = re.search(r'\\caption\{([^\n]*)\}', old_f01)[1]
    description = re.search(r'\\Description\{([^\n]*)\}', old_f01)[1]
    f01 = '\n'.join([
        r'\begin{figure*}[t]', r'  \centering',
        r'  \includegraphics[width=\textwidth]{figures/F01_main_rev4.pdf}',
        r'  \caption{' + caption + '}', r'  \Description{' + description + '}',
        r'  \label{fig:app-modification-detection}', r'\end{figure*}', '',
    ])
    f03 = (F03 / 'F03a_F04_figure.tex').read_text().replace(
        '{F03a_F04_main.pdf}', '{figures/F03a_F04_main.pdf}')
    f05 = (F05 / 'F05a_figure.tex').read_text().replace(
        '{F05a_main.pdf}', '{figures/F05a_main.pdf}')
    for filename, text, prefix, box in [
        ('app_detection_figure.tex', f01, 'FONE', 'PreviewAppGraphic'),
        ('app_mechanisms_figure.tex', f03, 'MECHANISMS', 'PreviewMechanismGraphic'),
        ('paired_timezone_figure.tex', f05, 'FIVE', 'PreviewPairedGraphic'),
    ]:
        (HERE / 'figures' / filename).write_text(measure(text, prefix, box))

    insertions = [
        ('sections/07_current_app177_results.tex', r'\label{sec:current-results}',
         '\n\n\\input{figures/app_detection_figure}', 'after'),
        ('sections/07_current_app177_results.tex', r'\subsection{Interpretation and Current Boundary}',
         '\\input{figures/app_mechanisms_figure}\n\n', 'before'),
        ('sections/09_future_browser67.tex', r'\label{sec:browser-future}',
         '\n\n\\input{figures/paired_timezone_figure}', 'after'),
    ]
    for relative, anchor, addition, position in insertions:
        target = HERE / relative
        text = target.read_text()
        assert text.count(anchor) == 1, (relative, anchor)
        replacement = anchor + addition if position == 'after' else addition + anchor
        target.write_text(text.replace(anchor, replacement))

    unchanged = []
    for entry in copied:
        relative = entry['destination']
        if relative == 'figures/overview_figure.tex':
            continue
        current = (HERE / relative).read_bytes()
        for section, _, addition, _ in insertions:
            if section == relative:
                assert current.count(addition.encode()) == 1
                current = current.replace(addition.encode(), b'')
        assert current == (SOURCE / relative).read_bytes(), relative
        unchanged.append(relative)
    for entry in artwork:
        assert (ROOT / entry['source']).read_bytes() == (HERE / entry['destination']).read_bytes()
    for text, original in [(f01, old_f01), (f03, (F03 / 'F03a_F04_figure.tex').read_text()),
                           (f05, (F05 / 'F05a_figure.tex').read_text())]:
        assert re.search(r'\\caption\{([^\n]*)\}', text)[1] == re.search(r'\\caption\{([^\n]*)\}', original)[1]

    command = ['/Library/TeX/texbin/latexmk', '-gg', '-pdf', '-bibtex',
               '-interaction=nonstopmode', '-halt-on-error', 'hybridguard_draft.tex']
    with (HERE / 'build_console.txt').open('w') as stream:
        result = subprocess.run(command, cwd=HERE, stdout=stream, stderr=subprocess.STDOUT)
    assert result.returncode == 0, 'ACM compilation failed; inspect build_console.txt'
    log = (HERE / 'hybridguard_draft.log').read_text(errors='replace')
    issues = {
        'overfull': re.findall(r'Overfull \\[hv]box[^\n]*', log),
        'font_or_character_errors': re.findall(r'(?:Missing character|LaTeX Font Warning)[^\n]*', log),
        'unresolved_references': re.findall(r'(?:LaTeX Warning:.*undefined|There were undefined references|Label .* multiply defined)[^\n]*', log),
        'retained_class_warnings': re.findall(r'Class acmart Warning[^\n]*', log),
    }
    # Preserve the draft's existing end-of-document balancing. Small output-box
    # warnings require visual inspection; horizontal/text overflow remains fatal.
    major_overfull = [warning for warning in issues['overfull']
                      if r'\hbox' in warning or float(re.search(r'\(([0-9.]+)pt', warning)[1]) > 2]
    assert not major_overfull and not issues['font_or_character_errors'] and not issues['unresolved_references'], issues
    measurements = {}
    for prefix in ['HG', 'FONE', 'MECHANISMS', 'FIVE']:
        measurements[prefix] = {k: round(float(v) * 25.4 / 72.27, 6)
                                for k, v in re.findall(prefix + r'-([A-Z-]+)=([0-9.]+)pt', log)}
    assert outside_status() == before and git('rev-parse', 'HEAD') == head
    assert git('diff', '--cached', '--name-status', '-z') == index
    report = {
        'source': str(SOURCE.relative_to(ROOT)), 'head_at_build': head.decode().strip(),
        'class_options': 'sigconf,anonymous,review', 'artwork': artwork,
        'existing_prose_tables_class_bibliography_unchanged': True,
        'verified_sources_unchanged_after_removing_only_figure_inputs': unchanged,
        'added_inputs': [{'section': x[0], 'input': x[2].strip()} for x in insertions],
        'captions_unchanged_from_accepted_figures': True, 'overview_unchanged_from_accepted_candidate': True,
        'template_measurements_mm': measurements, 'compiler_diagnostics': issues,
        'outside_status_records': len(before), 'outside_status_unchanged': True,
        'head_and_index_unchanged': True, 'visual_review': 'PENDING',
        'scope': 'Layout preview only. Historical manuscript prose is intentionally unchanged; no research-content reconciliation.',
    }
    (HERE / 'CHECK.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'compiled': True, 'source_preserved': True, 'outside_records_preserved': len(before),
                      'measurements_mm': measurements, 'diagnostics': issues}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
