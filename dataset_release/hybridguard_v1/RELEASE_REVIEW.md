# Release review — all publication gates pending

Publication status: **NOT_APPROVED**. Dataset license: **PENDING_APPROVAL**. No upload to external artifact platforms is performed by this implementation.

| Gate | Current status | Required human decision/evidence |
|---|---|---|
| Ownership and device/collection authorization | PENDING_CONFIRMATION | Confirm the authority to distribute measurements from every source, including controlled studies |
| MTC third-party scope | PENDING_CONFIRMATION | Written platform/procurement confirmation covering derived fingerprint fields, original measurements, labels and metadata; collection permission alone is insufficient |
| Institutional review and consent basis | NOT_ESTABLISHED_BY_THIS_AUDIT | Determine applicable review/exemption and consent/authorization documentation; absence of records is not an exemption |
| Field-level minimization | PENDING_REVIEW | Approve retained numeric/categorical fields, rare combinations and geometry measurements; assess utility after suppression |
| Linkage and group privacy | PENDING_REVIEW | Approve random grouping, experiment relations and any cross-source relationships; account for existing raw-record exposure |
| Final source scope | PENDING_APPROVAL | Approve/exclude MTC and each specialist separately; keep evidence-only and repeated sources excluded |
| Dataset license | PENDING_APPROVAL | Select an appropriate data license only after ownership and third-party rights are resolved |
| Double-blind packaging and hosting | PENDING_REVIEW | Audit the final content, URLs, file hashes, histories and hosting account for author linkage; a name-free README is not sufficient |
| Scientific claims | PENDING_REVIEW | Approve the distinction between recorded-label reconciliation, altered feature projection and independent reproduction |
| Repository exposure/history | REQUIRES_SEPARATE_REVIEW | Decide how to handle raw data already present remotely; this work does not delete or rewrite history |

The local `.private/hybridguard_v1_INTERNAL_REVIEW_ONLY.zip` is the concrete internal review package. It excludes original data, sensitive mappings and exact row provenance, but contains candidate fingerprints and is **not approved for anonymous upload**. The tracked dataset directory contains code, documents and aggregates with an empty `data/` gate. Neither should be represented as a publicly approved dataset.

After human decisions, create a new reviewed release artifact from the approved scope, rerun source/evidence/quality/privacy checks, verify the final archive, and only then authorize distribution. This builder intentionally provides no flag that turns pending permissions into approval.
