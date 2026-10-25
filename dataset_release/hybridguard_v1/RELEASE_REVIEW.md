# Release decisions and remaining checks

Public release authorization: **CONFIRMED_BY_PROJECT_LEAD**, as explicitly reported by the user on 2026-10-25. The authorization covers all **1,509 selected observations**, including the 891 MTC observations. Earlier ownership and third-party-redistribution pending states are superseded; they are not reopened by this build. Dataset license: **PENDING_SELECTION**. No license rights are granted by this document, the authorization-status field or the packaging implementation.

| Item | Recorded state | Consequence |
|---|---|---|
| All selected source publication authorization | Confirmed by project lead, reported by user | Controlled, specialist, Linked Browser and MTC records are all in release scope |
| Source scope | Fixed at 1,509 observations | Duplicate snapshots, nonrepresentative and out-of-cohort records remain excluded for methodological reasons |
| Label scope | 618 recorded-evidence labels; 891 unlabeled MTC | Authorization does not add benign labels or change experiment outcomes |
| Data structure | 558 App177; 951 Paired244; three incomplete records | Missingness and real endpoint relationships remain unchanged |
| Privacy projection | Existing suppression and random IDs retained | No raw identities, private maps, exact source references or credentials enter the archive |
| Scientific limits | Explicit in README and Dataset Card | No independent-device count, independent replication or full detector-score reproduction is claimed |
| Package checks | Automated results recorded in `VALIDATION.md` and generated reports | Their scope is content and consistency, not proof against every possible linkage attack |
| Data license | Pending explicit selection | Recommended CC BY 4.0; CC0 is an alternative only if deliberately selected; neither is applied automatically |
| Bundled-code license | Confirm inherited coverage or explicitly choose the intended code license | Do not infer a new code license from a proposed data license |
| Hosting and review visibility | Manual action; not performed here | Choose the review-sharing mode and inspect the actual logged-out landing page and download |

The formal archive is `reviewer_release/Cross_View_Consistency_Dataset_v1.0_Reviewer.zip`. It is distinct from the legacy internal-review archive. Its payload includes all authorized observations, independent loading and validation code, schema, computed statistics and anonymous documentation. The generated archive contains no original-source hash inventory, source tree, raw logs, identity map or Git history.

The remaining decisions concern **license terms and hosting presentation**, not whether MTC or other authorized sources may be included. Publication authorization alone does not specify attribution conditions, commercial reuse permissions, waiver of rights or code licensing. Record the chosen licenses and attribution wording before publishing a platform item that requires those fields; rebuild the archive if its licensing documents must change. The present archive is a formal reviewer artifact with an explicitly unresolved reuse-license selection, not a claim that an open license has already been granted.

Institutional-review or exemption details were not independently verified by this packaging task, and no affirmative institutional-review claim is made. This does not reopen the project lead's reported public authorization. The original research data and manuscript results remain unchanged.

Retained feature combinations can still link observations to other available materials. Content checks remove direct author identifiers and source linkage artifacts from the package, but neither a clean scan nor a private review link can prove global unlinkability. The uploader should inspect the actual platform metadata, related links, displayed authors and downloadable files. `FIGSHARE_UPLOAD.md` supplies the title, description, keywords and file list without performing an upload.
