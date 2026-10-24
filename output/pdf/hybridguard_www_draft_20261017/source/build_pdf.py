#!/usr/bin/env python3
"""Compile both editable ACM layouts with pdfLaTeX and BibTeX."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=['baseline', 'matrix', 'both'], default='both')
    parser.add_argument('--no-migrate', action='store_true')
    parser.add_argument('--force', action='store_true', help='Rerun after an environment/dependency change.')
    args = parser.parse_args()
    if not args.no_migrate:
        subprocess.run(['python3', str(ROOT / 'source/migrate_manuscript.py')], check=True)
    env = os.environ.copy()
    workspace_texmf = ROOT.parent / 'tmp/texmf'
    if workspace_texmf.exists():
        env['TEXMFHOME'] = str(workspace_texmf)
        env['TEXMFVAR'] = str(ROOT.parent / 'tmp/texmf-var')
        env['TEXMFCONFIG'] = str(ROOT.parent / 'tmp/texmf-config')
    variants = ['baseline', 'matrix'] if args.variant == 'both' else [args.variant]
    for variant in variants:
        name = 'HybridGuard_layout_v1' + ('_matrix' if variant == 'matrix' else '')
        source = 'main_matrix.tex' if variant == 'matrix' else 'main.tex'
        outdir = ROOT / 'build' / variant
        outdir.mkdir(parents=True, exist_ok=True)
        command = ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
                   '-file-line-error', '-outdir=' + str(outdir), '-jobname=' + name, source]
        if args.force:
            command.insert(1, '-g')
        with (outdir / 'build_console.txt').open('w') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                    stderr=subprocess.STDOUT)
        if result.returncode:
            print((outdir / 'build_console.txt').read_text()[-14000:])
            raise SystemExit(result.returncode)
        print(f'{variant}: {outdir / (name + ".pdf")}')


if __name__ == '__main__':
    main()
