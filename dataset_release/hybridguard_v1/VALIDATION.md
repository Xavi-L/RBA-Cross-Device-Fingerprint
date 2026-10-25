# Validation record

Result: **PASS for internal technical preparation; publication NOT_APPROVED**.

Commands executed from the repository root:

```sh
python3 dataset_release/hybridguard_v1/scripts/release.py all
python3 dataset_release/hybridguard_v1/scripts/release.py build
python3 dataset_release/hybridguard_v1/scripts/release.py verify
python3 -m unittest discover -s dataset_release/hybridguard_v1/tests -v
python3 dataset_release/hybridguard_v1/scripts/check_public_tree.py
python3 dataset_release/hybridguard_v1/scripts/load_example.py --data dataset_release/hybridguard_v1/.private/candidate
python3 dataset_release/hybridguard_v1/scripts/release.py package
```

- 28 focused tests passed: missingness and false/zero preservation, no invented Browser, source bindings and linked study labels, random-ID persistence, symlink/path boundaries, schema types, privacy policy enforcement, corrupted statistics/relationships and frozen-source checks before packaging.
- 767 original input files are covered by the frozen source lock. Their current contents matched the recorded digests; originals were not edited.
- All 1,509 exported observations reconciled with original feature/annotation evidence. Record types, unique IDs, one-to-one sidecars and 1,157 relationships passed validation. Historical MTC labels remain unverified.
- Five candidate files (four JSONL sidecars plus statistics) were byte-identical on an unchanged rebuild using the private release-ID map.
- The actual README Python loading block executed successfully. The independent CLI loader returned 1,509 observations with 558 App177 and 951 Paired244.
- The internal review ZIP contains 21 allowlisted entries. Its four data sidecars matched the reviewed candidate bytes; archive integrity and path checks passed. It was extracted into an isolated private temporary directory, and the bundled loader returned the same counts without the original repository sources.
- Public prose/JSON and intended tracked files passed the author-identity/pattern scan. Timestamp-bearing receipt basenames are masked. Private/sample paths are ignored and not tracked. Synthetic negative-test fixtures are explicitly excluded from prose/data scanning.

These checks establish consistency of the exported projection and saved evidence. They do not prove independent physical-device counts, global anonymity, redistribution rights, new experiment replication, or reproduction of original detector scores after feature suppression.
