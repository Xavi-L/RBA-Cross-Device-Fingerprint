HybridGuard WWW working draft

Upload this ZIP as a new Overleaf project.
Main document: main.tex
Compiler: pdfLaTeX (TeX Live 2025 or newer recommended).
The acmart class and ACM bibliography style are included.

Local build: latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
Saved-count verification (no detector execution): python3 tables/verify_tables.py

Format: ACM sigconf, anonymous, review; WWW 2027 Research Track draft.
Expected PDF: 7 main-text pages, 1 reference page, 1 appendix page.
The draft suppresses the publication-only ACM reference block; acmart emits a nonfatal printacmref warning. Citation/reference resolution is unaffected.

This package contains one overview and four editable English tables adapted from the accepted 16 October materials. Aggregate counts and original group mappings accompany the tables. It does not contain raw device fingerprints or pair tickets.

The manuscript reports saved controlled/development-exposed evidence, including missed modifications, normal alarms, unknowns and unintegrated conditions. It is a complete writing draft, not a claim of submission acceptance, independent generalization, ethical approval, or operational deployment readiness. Author and institutional decisions remain necessary before submission.
