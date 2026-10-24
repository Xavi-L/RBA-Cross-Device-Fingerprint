#!/usr/bin/env python3
"""Migrate the approved Markdown input into editable ACM LaTeX.

The source prose is retained. Changes are limited to typesetting, automatic
citations/cross-references, and the optional Table 3 presentation variant.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / 'input_markdown'
TABLE_LABELS = {
    1: 'related', 2: 'materials', 3: 'app', 4: 'specialists',
    5: 'normals', 6: 'paired',
}
FIGURES = {
    1: ('HybridGuard_Fig1_surfaces_v2', 'surfaces', '\\textwidth',
        'Native, WebView Host, and App Web observations form complementary surfaces. '
        'Memory and timezone relations are integrated; Host geometry is a separate '
        'study. An external Browser supplies an optional linked timezone reference.'),
    2: ('HybridGuard_Fig2_pipeline_v2', 'pipeline', '\\textwidth',
        'Offline candidate construction, sparse selection, and retention yield '
        'frozen checks. Current-record evaluation returns an empty model, failure, '
        'alert, no alert, or unknown using the ordered decision semantics.'),
    3: ('HybridGuard_Fig3_mechanisms_v2', 'mechanisms', '\\textwidth',
        'Three illustrative panels show a Native memory bound, legitimate timezone '
        'co-change versus a Web-only change, and a standalone Host geometry bound.'),
}


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.migrate-', dir=path.parent)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as out:
        out.write(text)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def pandoc(text):
    result = subprocess.run(
        ['pandoc', '--from=markdown+tex_math_dollars+raw_tex+raw_attribute', '--to=latex',
         '--wrap=none', '--top-level-division=section'],
        input=text, text=True, capture_output=True, check=True,
    )
    converted = result.stdout.strip().replace(r'\textasciitilde{}\ref', r'~\ref')
    # Permit a line break after a literal underscore in long model/file names.
    # The visible characters remain identical to the Markdown source.
    return converted.replace(r'\_', r'\_\allowbreak{}')


def citations(text):
    def replace(match):
        ids = []
        for item in match.group(1).split(','):
            ends = re.split(r'[-–]', item.strip())
            if len(ends) == 2:
                ids.extend(range(int(ends[0]), int(ends[1]) + 1))
            else:
                ids.append(int(ends[0]))
        assert all(1 <= n <= 15 for n in ids)
        return '\\cite{' + ','.join(f'ref{n:02}' for n in ids) + '}'
    return re.sub(r'\[([0-9]+(?:\s*[,–-]\s*[0-9]+)*)\]', replace, text)


def cross_references(text):
    text = re.sub(r'Appendix A\.([1-5])\b',
                  lambda m: 'Appendix~\\ref{app:' + m[1] + '}', text)
    text = re.sub(r'Appendix A\b', r'Appendix~\\ref{app:main}', text)
    text = re.sub(r'Section ([1-7])\.([1-9])\b',
                  lambda m: 'Section~\\ref{sec:' + m[1] + '-' + m[2] + '}', text)
    text = re.sub(r'Section ([1-7])\b',
                  lambda m: 'Section~\\ref{sec:' + m[1] + '}', text)
    text = re.sub(r'Table ([1-6])\b',
                  lambda m: 'Table~\\ref{tab:' + TABLE_LABELS[int(m[1])] + '}', text)
    text = re.sub(r'Figure ([1-3])\b',
                  lambda m: 'Figure~\\ref{fig:' + FIGURES[int(m[1])][1] + '}', text)
    return text


def text_transforms(text):
    text = citations(text)
    text = cross_references(text)
    # Keep literal repository paths readable without changing their text.
    text = re.sub(r'`([^`\n]+)`',
                  lambda m: ('`\\path|' + m[1] + '|`{=latex}') if '/' in m[1] else m[0], text)
    return text


def move_floats(text, stats):
    table_pattern = re.compile(
        r'^\*\*Table ([1-6])\. (.*?)\*\*(.*?)\n\n(\|[^\n]*\n(?:\|[^\n]*\n?)+)',
        re.M | re.S,
    )
    def table(match):
        n = int(match[1])
        stats['tables'].append(n)
        if n == 3:
            return ('\\ifHGMatrix\n\\input{tables/table_03_matrix.tex}\n'
                    '\\else\n\\input{tables/table_03.tex}\n\\fi\n\n')
        return f'\\input{{tables/table_{n:02}.tex}}\n\n'
    text = table_pattern.sub(table, text)
    fig_pattern = re.compile(
        r'^!\[Figure ([1-3])\.[^\n]*\]\([^\n]+\)\n\n'
        r'\*\*Figure \1\.\*\* ([^\n]+)\n', re.M,
    )
    def figure(match):
        n = int(match[1])
        stem, label, width, description = FIGURES[n]
        caption = pandoc(text_transforms(match[2]))
        body = (
            '\\begin{figure*}[t]\n  \\centering\n'
            f'  \\includegraphics[width={width}]{{figures/{stem}.pdf}}\n'
            f'  \\caption{{{caption}}}\n'
            f'  \\label{{fig:{label}}}\n'
            f'  \\Description{{{description}}}\n'
            '\\end{figure*}\n'
        )
        atomic_text(ROOT / 'floats' / f'figure_{n:02}.tex', body)
        stats['figures'].append(n)
        return f'\\input{{floats/figure_{n:02}.tex}}\n\n'
    return fig_pattern.sub(figure, text)


def headings(text, appendix=False):
    if appendix:
        text = re.sub(r'^# Appendix A\. (.+)$', r'# \1 {#app:main}', text, flags=re.M)
        text = re.sub(r'^## A\.([1-5]) (.+)$',
                      lambda m: '## ' + m[2] + ' {#app:' + m[1] + '}', text, flags=re.M)
    else:
        text = re.sub(r'^# ([1-7]) (.+)$',
                      lambda m: '# ' + m[2] + ' {#sec:' + m[1] + '}', text, flags=re.M)
        text = re.sub(r'^## ([1-7])\.([1-9]) (.+)$',
                      lambda m: '## ' + m[3] + ' {#sec:' + m[1] + '-' + m[2] + '}',
                      text, flags=re.M)
    return text


def polish_matrix_layout():
    """Place the matrix floats without editing prose or authored table files.

    Double-column floats normally cannot appear at the top of the page on
    which they are encountered. Registering these floats in the preceding
    section puts them beside their discussion. The baseline branch keeps its
    original float calls and therefore its original page layout.
    """
    names = ['01_introduction.tex', '02_background_and_scope.tex',
             '03_method.tex', '04_evaluation_protocol.tex', '05_results.tex']
    texts = {name: (ROOT / 'sections' / name).read_text() for name in names}

    # ACM double-column tables cannot float to the page where they are first
    # registered. Queue Table 1 during the Introduction so it appears alongside
    # the Section 2 prior-work discussion, not after Section 3 has started.
    related = r'\input{tables/table_01.tex}'
    assert texts['02_background_and_scope.tex'].count(related) == 1
    texts['02_background_and_scope.tex'] = texts['02_background_and_scope.tex'].replace(
        related, "% Table 1 was queued earlier to keep it with Section 2.")
    intro_anchor = "Android hybrid applications offer complementary observations"
    assert texts['01_introduction.tex'].count(intro_anchor) == 1
    texts['01_introduction.tex'] = texts['01_introduction.tex'].replace(
        intro_anchor,
        "% Register the Related Work double-column table early for Section 2.\n"
        + related + "\n\n" + intro_anchor)

    def matrix_only(command):
        return '\\ifHGMatrix\n' + command + '\n\\fi'

    def baseline_only(command):
        return '\\ifHGMatrix\\else\n' + command + '\n\\fi'

    def insert_before(name, marker, command):
        assert texts[name].count(marker) == 1
        texts[name] = texts[name].replace(
            marker, matrix_only(command) + '\n\n' + marker)

    materials = r'\input{tables/table_02.tex}'
    assert texts['04_evaluation_protocol.tex'].count(materials) == 1
    texts['04_evaluation_protocol.tex'] = texts['04_evaluation_protocol.tex'].replace(
        materials, baseline_only(materials))
    insert_before('03_method.tex', r'\hypertarget{sec:3-5}', materials)

    matrix = r'\input{tables/table_03_matrix.tex}'
    original_branch = ('\\ifHGMatrix\n' + matrix +
                       '\n\\else\n\\input{tables/table_03.tex}\n\\fi')
    assert texts['05_results.tex'].count(original_branch) == 1
    texts['05_results.tex'] = texts['05_results.tex'].replace(
        original_branch, baseline_only(r'\input{tables/table_03.tex}'))
    insert_before('04_evaluation_protocol.tex', r'\hypertarget{sec:4-2}', matrix)

    # Keep Figure 3 at its RQ2 discussion rather than registering it next to
    # Table 3. This lets prose separate the full-width result table and figure.

    for name, text in texts.items():
        atomic_text(ROOT / 'sections' / name, text)

    # Tables are authored independently; migration never rewrites their layout.


def main():
    lock = json.loads((ROOT / 'notes/abstract_lock.json').read_text())
    abstract_md = (INPUT / 'sections/00_abstract.md').read_bytes()
    assert hashlib.sha256(abstract_md).hexdigest() == lock['sha256']
    original = (ROOT / 'baseline_source/main.tex').read_text()
    abstract_tex = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',
                             original, re.S).group(1).strip()
    canonical = (ROOT / 'baseline_source/abstract_verbatim.txt').read_text().strip()
    visible = abstract_tex.replace('\\%', '%').replace("'", '’')
    assert visible == canonical, 'The submitted abstract must remain verbatim.'
    title = re.search(r'\\title\{([^\n]+)\}', original).group(0)
    ccs = re.search(r'\\begin\{CCSXML\}.*?\\keywords\{[^\n]+\}', original, re.S).group(0)
    atomic_text(ROOT / 'frontmatter.tex', title + '\n\\begin{abstract}\n' +
                abstract_tex + '\n\\end{abstract}\n' + ccs + '\n\\maketitle\n')
    stats = {'tables': [], 'figures': [], 'sections': [],
             'abstract_preserved': True, 'source_prose_edited': False,
             'approved_input_edits': ['A1', 'A2', 'A3', 'B1'],
             'source_prose_edited_note': 'This migration preserves its input; the four user-approved edits are already present in input_markdown.',
             'typesetting_changes': ['automatic headings, citations, and cross-references',
                                    'editable table floats; vector figure inclusion',
                                    'two-line geometry equation; breakable literal paths']}
    for path in sorted((INPUT / 'sections').glob('*.md')):
        if path.name.startswith(('00_', '08_')):
            continue
        text = path.read_text()
        text = move_floats(text, stats)
        text = headings(text)
        text = text_transforms(text)
        geometry = (r'$$P>H_{\mathrm{view}}+\epsilon,\quad '
                    r'\epsilon=2+4\cdot2^{-23}\max(|P|,|H_{\mathrm{view}}|,1)\ \text{pixels}.$$')
        split_geometry = (r'$$\begin{aligned}P&>H_{\mathrm{view}}+\epsilon,\\'
                          r'\epsilon&=2+4\cdot2^{-23}\max(|P|,|H_{\mathrm{view}}|,1)'
                          r'\ \text{pixels}.\end{aligned}$$')
        text = text.replace(geometry, split_geometry)
        converted = pandoc(text)
        atomic_text(ROOT / 'sections' / (path.stem + '.tex'), converted + '\n')
        stats['sections'].append(path.stem)
    appendix = (INPUT / 'supplement/00_Appendix_English.md').read_text()
    appendix = text_transforms(headings(appendix, appendix=True))
    atomic_text(ROOT / 'sections/08_appendix.tex', pandoc(appendix) + '\n')
    assert stats['tables'] == list(range(1, 7)), stats
    assert stats['figures'] == [1, 2, 3], stats
    for item in json.loads((ROOT / 'figures/FROZEN.json').read_text())['files']:
        assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256']
    polish_matrix_layout()
    stats['typesetting_changes'].append(
        'matrix version: earlier registration for Tables 2 and 3; Figure 3 remains at its RQ2 discussion')
    stats['typesetting_changes'].append(
        'independently authored semantic table symbols, concise labels and legends; '
        'Table 5 is single-column; source prose, results and frozen figure assets are preserved')
    atomic_text(ROOT / 'qa/migration.json', json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
