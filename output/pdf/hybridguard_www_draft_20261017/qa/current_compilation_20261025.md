# WWW draft compiled from current LaTeX — 2026-10-25 prose consolidation

- Task: reorganize the previously identified defensive/repeated qualifications while retaining scientific meaning and meeting the page budget.
- Baseline: the preceding Table 1 package refresh, based on HEAD `af994650`, main revision `faac01fe`, and existing local `main.tex` layout additions.
- Changed LaTeX: sections 2, 3, 5, 6, appendix A, and one Table 3 legend sentence. Corresponding edited Markdown prose is synchronized.
- Section 2 consolidates attribution, true-value, intent, and authenticity boundaries; section 3 states uniform saved-model evaluation directly.
- Section 5 separates the nine main-benchmark differences from the twelve specialist detections and directly compares standalone Host results with frozen Integrated App behavior.
- Section 6 consolidates deployment evaluation requirements. Appendix A consolidates error-bound and post hoc sensitivity limitations without changing the frozen coefficient or verification scope.
- Table 3 keeps all symbol definitions and removes only the redundant overall-quality disclaimer.
- Additional source-alignment repair: the Markdown Host paragraph and fixed-0.005 explanation previously lagged the LaTeX and now match its current description.
- Net whitespace-token reduction across changed LaTeX: 141 (99 in main-text sources/table note; 42 in appendix). This is a source-token count, not a formal natural-language word count.
- Per-file numeric-token, equation, citation, and label comparisons: PASS. All table bodies are unchanged.
- Abstract, main.tex, ACM class, table styling, bibliography, and all figure files are unchanged from the baseline package.
- Independent semantic review: PASS. Refitting/development exposure, unknown/failure semantics, no-effect operations, missed detections, Host standalone scope, and post hoc validation requirements remain intact.
- Entry: `main.tex`; compiler: pdfLaTeX via latexmk. Historical migration was not run.
- Command: `latexmk -g -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build main.tex`.
- Main text ends on p.8; references begin on p.9; entire PDF has 11 pages.
- Main-text <= 8 pages: PASS. Total <= 12 pages: PASS.
- Table 1 on p.2; Table 3 on p.6; Figure 3 on p.7. All nine main-paper floats remain within one page of the related discussion.
- Overfull boxes: 0. Undefined citations/references: 0. Existing ACM `printacmref=false` warning and ordinary underfull messages remain.
- All 11 PDF pages were rendered and inspected. No clipping, overlap, or lost text was observed.
- Independent archive extraction and compilation: PASS, 11 pages. Text and rendered pixels match all workspace pages.
- Final archive retains 150 member paths. Metadata updates after the clean build do not alter its compiled source inputs; final member content is compared directly with current files.
- `HybridGuard_WWW_Draft.pdf` is copied from the fresh `build/main.pdf`.

Previous package-refresh, dataset-release, and targeted-style reports describe their historical revisions. This record supersedes their page counts and package-currentness claims.
