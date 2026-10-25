# Release decisions and remaining checks

Public release authorization: **CONFIRMED_BY_PROJECT_LEAD**, as explicitly reported by the user on 2026-10-25. The authorization covers all **1,509 selected observations**, including the 891 MTC observations. Earlier ownership and third-party-redistribution pending states are superseded; they are not reopened by this build. Data license: **Creative Commons Attribution 4.0 International (`CC-BY-4.0`)**, explicitly selected by the user. `LICENSE_DATA.md` defines the 15 licensed data/documentation resources and the anonymous attribution format. Bundled-software license: **`NOT_SPECIFIED`**; the data-license grant excludes the scripts.

| Item | Recorded state | Consequence |
|---|---|---|
| All selected source publication authorization | Confirmed by project lead, reported by user | Controlled, specialist, Linked Browser and MTC records are all in release scope |
| Source scope | Fixed at 1,509 observations | Duplicate snapshots, nonrepresentative and out-of-cohort records remain excluded for methodological reasons |
| Label scope | 618 recorded-evidence labels; 891 unlabeled MTC | Authorization does not add benign labels or change experiment outcomes |
| Data structure | 558 App177; 951 Paired244; three incomplete records | Missingness and real endpoint relationships remain unchanged |
| Privacy projection | Existing suppression and random IDs retained | No raw identities, private maps, exact source references or credentials enter the archive |
| Scientific limits | Explicit in README and Dataset Card | No independent-device count, independent replication or full detector-score reproduction is claimed |
| Package checks | Automated results recorded in `VALIDATION.md` and generated reports | Their scope is content and consistency, not proof against every possible linkage attack |
| Data license | CC-BY-4.0, explicitly selected | Creative Commons Attribution 4.0 International applies to the 15 designated resources in `LICENSE_DATA.md` |
| Bundled-code license | NOT_SPECIFIED | No applicable repository-wide or file-specific license was established for the two bundled scripts; the data license excludes them |
| Hosting and review visibility | Manual action; not performed here | Choose the review-sharing mode and inspect the actual logged-out landing page and download |

The formal archive is `reviewer_release/Cross_View_Consistency_Dataset_v1.0_Reviewer.zip`. It is distinct from the legacy internal-review archive. Its payload includes all authorized observations, independent loading and validation code, schema, computed statistics and anonymous documentation. The generated archive contains no original-source hash inventory, source tree, raw logs, identity map or Git history.

The data-license decision is complete. Use **Creative Commons Attribution 4.0 International (CC BY 4.0)** for the deposit's data-license field, and preserve the explicit software exclusion in its description and bundled notice. During double-blind review, attribute the supplied neutral title and version, provide the CC BY 4.0 link and describe changes; retain notices, source URI and creator information when supplied as the license requires. No author identity is invented. Identity and a permanent citation will be supplied after double-blind review. The license notice adds no review-only, noncommercial or approval restriction.

The remaining decisions concern **software licensing and hosting presentation**. The tracked repository has no root software license, and the two bundled scripts have no file-specific license header. Licenses found for illustration assets and frozen third-party dependencies do not license these scripts. Their status is therefore `NOT_SPECIFIED`, rather than an inferred MIT, Apache or Creative Commons grant. A future software-license choice should update its own notice and manifest; it does not change the already selected data license.

Institutional-review or exemption details were not independently verified by this packaging task, and no affirmative institutional-review claim is made. This does not reopen the project lead's reported public authorization. The original research data and manuscript results remain unchanged.

Retained feature combinations can still link observations to other available materials. Content checks remove direct author identifiers and source linkage artifacts from the package, but neither a clean scan nor a private review link can prove global unlinkability. The uploader should inspect the actual platform metadata, related links, displayed authors and downloadable files. `FIGSHARE_UPLOAD.md` supplies the title, description, keywords and file list without performing an upload.
