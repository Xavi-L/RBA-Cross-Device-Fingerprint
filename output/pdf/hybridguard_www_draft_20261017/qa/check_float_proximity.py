#!/usr/bin/env python3
"""Check that every main-text float stays close to its first relevant subsection."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
aux = (root / "main.aux").read_text(encoding="utf-8")
sections = "\n".join(
    p.read_text(encoding="utf-8") for p in sorted((root / "sections").glob("*.tex"))
)

def page_of(label):
    prefix = r"\newlabel{" + label + "}"
    lines = [row for row in aux.splitlines() if row.startswith(prefix)]
    assert len(lines) == 1, f"Missing or duplicated label: {label}"
    match = re.search(r"\{\{[^{}]*\}\{([0-9]+)\}", lines[0])
    assert match, f"Cannot read page for {label}: {lines[0]}"
    return int(match.group(1))

# Each float's closest substantive discussion is in the indicated subsection.
# The first explicit citation must occur in sections/, not only in captions.
plan = [
    ("Table 1", "tab:related", "sec:2-1", "Related-work comparison"),
    ("Figure 1", "fig:surfaces", "sec:2-2", "Observation surfaces"),
    ("Figure 2", "fig:pipeline", "sec:3-1", "Collection and model-construction pipeline"),
    ("Table 2", "tab:materials", "sec:4-1", "Evaluation materials"),
    ("Table 3", "tab:app", "sec:5-1", "RQ1 detection and ablations"),
    ("Table 4", "tab:specialists", "sec:5-2", "RQ2 reference mechanisms"),
    ("Figure 3", "fig:mechanisms", "sec:5-2", "RQ2 reference mechanisms"),
    ("Table 5", "tab:normals", "sec:5-3", "RQ3 normal alarms and availability"),
    ("Table 6", "tab:paired", "sec:5-4", "RQ4 linked-Browser extension"),
]

rows = []
for name, ref, sec, context in plan:
    float_page, text_page = page_of(ref), page_of(sec)
    gap = abs(float_page - text_page)
    citation = r"\ref{" + ref + "}"
    assert citation in sections, f"{name} has no explicit prose citation in sections/: {ref}"
    assert gap <= 1, (
        f"{name} on p.{float_page} is too far from related text "
        f"{sec} (p.{text_page}); page gap={gap}"
    )
    rows.append((name, float_page, sec, text_page, gap, context))

assert page_of("marker:main-text-end") <= 8, "Main text exceeds eight pages"
assert page_of("tab:app") + 1 == page_of("fig:mechanisms"), (
    "Table 3 and Figure 3 must occupy consecutive, distinct pages"
)
assert page_of("TotPages") <= 12, "Entire draft exceeds twelve pages"

out = [
    "# Float proximity check (2026-10-25)",
    "",
    "Verified against a fresh pdflatex build and main.aux. Each float has "
    "an explicit in-text reference; the float is at most one PDF page away "
    "from the start of its relevant discussion subsection.",
    "",
    "| Float | PDF page | Related section | Section starts | Page gap | Context |",
    "| --- | ---: | --- | ---: | ---: | --- |",
]
for name, fpage, sec, spage, gap, context in rows:
    out.append(f"| {name} | {fpage} | {sec.replace('sec:', '').replace('-', '.')} | {spage} | {gap} | {context} |")
out.extend([
    "",
    f"- Table 3: p.{page_of('tab:app')}; Figure 3: p.{page_of('fig:mechanisms')}.",
    f"- Main text ends on p.{page_of('marker:main-text-end')}; entire PDF has {page_of('TotPages')} pages.",
    "- All float placements pass the <=1-page proximity constraint.",
    "",
])
report = "\n".join(out)
(root / "qa/float_proximity_20261025.md").write_text(report, encoding="utf-8")
print(report)
