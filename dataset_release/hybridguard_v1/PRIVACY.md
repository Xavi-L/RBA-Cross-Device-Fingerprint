# Privacy projection and reviewer anonymity

All 1,509 selected observations have project-lead public authorization, as explicitly confirmed by the user on 2026-10-25. The privacy projection remains in force. This is a de-identified research release, not a proof of irreversible anonymity.

## Retained controls

1. Samples, source-specific groups and relationships retain the existing randomly generated release UUIDs. Original identifiers are not hashed into those IDs. The reusable identity map and exact source references remain private and are excluded from the reviewer archive.
2. The fixed feature allowlist admits the nominal 177/244 schema plus recorded numeric/boolean geometry measurements. Raw envelope metadata, tickets, credentials, IP addresses, paths and infrastructure do not enter the features.
3. Free-text/high-entropy values remain suppressed, including build/device strings, user agents, renderer/vendor strings, Canvas/audio/font/plugin hashes, proxy configuration, package names and error strings. `field_catalog.json` records the policy for every field.
4. Precise build/install/update/performance timestamps and uptime clocks remain suppressed. Numeric/boolean values and validated language/locale/timezone/geometry values are retained for scientific utility. Unexpected semantic strings are suppressed.
5. Collection status, original field presence and privacy redaction are separate. Missing source fields remain missing; suppressed values remain null with a redaction reason. No Browser or measured value is synthesized.
6. The geometry supplement retains host dimensions, padding and content sizes, synchronized Web operands, relative acquisition bracket duration and the usable-window flag. Document/session IDs, URLs, absolute clocks and log text remain excluded.
7. The independent Reviewer Release uses a file allowlist. It excludes original-source paths and SHA-256 inventories, builder/source manifests, private mappings, raw receipts, internal logs, Git history, system metadata and source documents that could link reviewers to author identities. Release checks inspect file names, text and archive metadata as well as data strings.

## Interpretation and remaining risk

Pattern checks cover direct identity and credential patterns; they cannot establish that every possible identifying combination is absent. Hardware characteristics, API versions, screen geometry, language/timezone, field availability, intervention labels and retained groups can support linkage or reidentification. Random IDs permit intentional within-release joins. Source-scoped groups are not global physical-device identities and do not establish independence.

Original-source hashes and repository locators are excluded from the reviewer archive because exact-match searches could reveal provenance. The repository-facing source inventory remains an audit artifact and is not the reviewer upload. Some original measurements were already accessible outside this artifact; removing explicit locators cannot prevent matching retained values to those materials.

Some interventions change suppressed fields. Their labels describe the original recorded evidence even when the released feature projection does not expose the changed value. Reproduction of every original detector score is therefore unsupported. The archive supports loading, structure and label checks, released-data statistics, and analyses using retained values within their recorded scope.

No public-authorization gate remains open for the selected sources. The selected data license is CC BY 4.0. The separate bundled-software license remains unspecified, and hosting choices are documented in `RELEASE_REVIEW.md`. Any later coarsening would change research utility and require a new version; the current build preserves the requested features, redaction policy, labels and associations. Inspect actual hosting metadata and review links separately before sharing, since local package checks cannot validate a page that has not been created.
