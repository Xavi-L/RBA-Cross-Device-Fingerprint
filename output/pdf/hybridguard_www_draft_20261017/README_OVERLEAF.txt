HybridGuard: Cross-Layer Consistency as Integrity Evidence for Android Web Environments
WWW working draft — first whole-paper editorial pass, 18 October 2026

Upload this ZIP as an Overleaf project.
Main document: main.tex
Compiler: pdfLaTeX
The acmart class and ACM bibliography style are included.

Local build: latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
Saved-count verification (no detector execution): python3 tables/verify_tables.py

Format: ACM sigconf, anonymous, review, using the existing template settings.
Verified PDF: 11 pages; main text on pages 1–9, references on page 10, appendix on page 11.
These ranges come from the isolated build for this editorial pass, not a submission-limit assessment.
The build retains the pre-existing diagnostics of a 1.47083pt overfull hbox in the Abstract and a nonfatal acmart warning caused by suppressing the publication-only ACM reference block. Page construction also produces underfull vbox notices; the rendered pages show no overlap or isolated headings. Page 9 has an empty right column, with the bibliography still starting on a new page under the original settings. Citations and references resolve normally.

This package contains one overview and four editable English tables adapted from the accepted 16 October materials. Aggregate counts and original group mappings accompany the tables. This editorial pass leaves the methods, parameters, results, tables, overview, bibliography, appendix, and template settings unchanged. The ZIP contents were compared with the current source files and compiled after extraction into a separate directory.

The manuscript reports controlled and development-exposed evidence, including missed modifications, normal alarms, unknowns, and unintegrated conditions. Host geometry remains a separate study. Full App includes within-view and cross-view checks; Full App+C1 is the retained cross-endpoint extension. A no-alert result does not establish authenticity, and the observations do not create a root of trust.

Institutional review, exemption, and participant-consent status are not established by the available study documentation. The draft does not establish independent device-attack generalization or production deployment performance. This package contains no raw device payloads, pair tickets, stable device identifiers, or reference-paper PDFs; this statement concerns the package, not the repository as a whole.
