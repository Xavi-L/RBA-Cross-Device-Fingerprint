# Privacy policy and residual risk

This is a conservative internal export, not a certified anonymous dataset. No observations are authorized for public distribution.

## Implemented controls

1. Samples, source-specific groups and relationships use random UUIDs generated for this release. Original session, installation, device, receipt and pair identities are never hashed into public IDs. The reusable mapping and exact source references remain under the ignored, owner-only `.private/` directory.
2. A fixed field allowlist admits only the 177/244 fingerprint schema and an explicit numeric/boolean geometry supplement. Top-level raw metadata, tickets, logs, tokens, IP fields, arbitrary paths and infrastructure are never copied into features.
3. All free-text/high-entropy values are suppressed by default, including build/device strings, user agents, renderer/vendor strings, Canvas/audio/font/plugin hashes, proxy configuration, package names and error strings. The full field policy appears in `field_catalog.json` and `SCHEMA.md`.
4. Exact build/install/update/performance timestamps and uptime clocks are removed. Narrowly validated language/locale/timezone values, geometry and numeric/boolean features are retained for cross-view semantics. Unexpected semantic strings are suppressed rather than passed through.
5. Collector status, original slot presence and privacy redaction have independent fields. Redaction does not turn an unavailable value into an observation, and missing source values do not become synthetic measurements. A suppressed original value is null with an explicit privacy reason.
6. The geometry supplement retains numeric host dimensions/padding/content sizes, synchronized Web operands and the relative acquisition bracket duration, plus the usable-window flag. Document/session IDs, URLs, absolute clocks and log text are excluded.
7. A pattern scan checks candidate strings, including nested arrays, for email, IPv4, local home paths, common credential forms, phone numbers, exact timestamps, direct-identity keys and the local account name. Field-policy enforcement rejects non-pattern-matching values in suppress-all fields. ZIP creation uses an explicit file allowlist and excludes mappings, original records and Git history.

## Limits of these controls

A pattern scan cannot prove that all secrets or identities are absent. Numeric hardware characteristics, API versions, screen geometry, language/timezone combinations, availability patterns, intervention labels and retained grouping can enable reidentification or linkage. Random IDs still permit within-release linking. Source hashes and already exposed original records can aid external linkage. Source-scoped group IDs do not establish global device identities or eliminate cross-study dependence.

Some attacks change suppressed fields. Their original labels remain valid only within the recorded evidence scope; the released feature projection may no longer expose the effect. Do not evaluate the original full detector and attribute any altered result to the manuscript. Memory/timezone and geometry semantics are retained where the field policy permits, but final minimization and utility decisions require human review.

Before public release, review every retained field and relationship, especially rare feature combinations and cross-file joins. Decide whether additional coarsening, task-specific projections, restricted access or source exclusion is necessary. Obtain the permissions in `RELEASE_REVIEW.md`. A clean automated scan does not override pending approval.
