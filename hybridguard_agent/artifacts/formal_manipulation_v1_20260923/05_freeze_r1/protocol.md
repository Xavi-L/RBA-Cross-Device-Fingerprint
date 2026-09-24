# Formal manipulation frozen protocol — packaging revision r1

This snapshot inherits the complete experimental semantics of `../05_freeze/protocol.json`.

- Protocol: `formal-manipulation-protocol-v2`
- Freeze revision: `formal-manipulation-freeze-r1`
- Digest: `9a6cb92a5d973a42d230305e176ab9ef824bca2e8aae045dafed515ce61c0f19`
- Parent digest: `d1eb5d9894ff8a9194692f8bcfdc22b7f6c603448f1f21ad8151980a3fb19d27`
- Contract: `formal-manipulation-relation-risk-attribution-v2`
- Policy: `formal-manipulation-family-or-v2`

Only packaging, explicit runtime resources and startup validation changed. See `PACKAGING_REVISION.json`, `SEMANTIC_INVARIANCE.json`, `SNAPSHOT_DIFF.json` and `STEP_REPORT.md`. Actual resource paths/digests are in `frozen_sources/RUNTIME_RESOURCES.json`. Use this snapshot's own source/config/policy paths; never fall back to the workspace. Synthetic full-chain logs are in the sibling `05_freeze_r1_validation/` directory.

S05-R acceptance is engineering/synthetic only. Real execution still requires separate review and step authorization. No S06 units or real predictions were created.
