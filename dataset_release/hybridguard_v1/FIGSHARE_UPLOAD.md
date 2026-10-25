# Suggested deposit metadata

This metadata is prepared for a manual deposit. No upload or publication is performed by the artifact. Select **Creative Commons Attribution 4.0 International (CC BY 4.0)** for the data-license field. Its SPDX identifier is `CC-BY-4.0`; the exact licensed scope and attribution are in `LICENSE_DATA.md`. The bundled scripts remain outside that grant, with software-license status `NOT_SPECIFIED`.

## Title

Cross-View Consistency Dataset v1.0: De-identified Android, WebView and Linked Browser Observations

## English description

This dataset contains 1,509 de-identified observations for studying consistency across Android Native, WebView Host, App Web and linked Browser Web contexts. It includes 558 App177 observations and 951 Paired244 observations. App177 comprises 84 Native, 26 Host and 67 App Web feature slots; Paired244 adds 67 genuinely collected Browser Web slots. The sources are a controlled App benchmark (378 observations), memory (72), timezone (36) and Host geometry (72) specialist studies, a linked Browser development study (60), and historical MTC representatives (891).

Labels for 618 observations were checked against saved experimental evidence: 170 modified observations, 442 normal controls and six no-effect operations. All 891 MTC observations remain unlabeled. Three MTC observations each lack five original feature fields; missingness is preserved. The data retain random release identifiers, source grouping, 206 three-phase experiment groups and 951 App–Browser endpoint associations. Observation counts do not establish independent physical-device counts, and historical cohort assignments do not constitute a new independent benchmark split.

The package contains JSONL features, metadata, annotations and relationships; machine-readable schema and field documentation; computed statistics; dataset documentation; and standalone Python loading and validation scripts. It requires no original research checkout or network access to load all observations and recompute released-data statistics. Sensitive identifiers, high-entropy fingerprint strings and precise times are suppressed. Consequently, this projection cannot fully reproduce original detector inputs or all manuscript scores. Retained feature combinations may still support linkage. The project lead has confirmed public authorization for all included sources. The data and designated accompanying resources are licensed under Creative Commons Attribution 4.0 International (CC BY 4.0; https://creativecommons.org/licenses/by/4.0/), as specified in LICENSE_DATA.md. The bundled validation and loading scripts are excluded from this data-license grant; their software-license status is NOT_SPECIFIED.

## Keywords

Android; WebView; browser fingerprinting; cross-view consistency; cross-endpoint consistency; device fingerprinting; controlled experiments; data availability; privacy-preserving data release; reproducibility

## Files

Upload the single completed `Cross_View_Consistency_Dataset_v1.0_Reviewer.zip`. The archive contains its own README, dataset card, schema, field catalog, statistics, manifest, four data sidecars and standalone loading/validation scripts. Do not add internal build inputs or an original research-source archive. The exact archive-member list is recorded in the release manifest.

## Sharing and remaining settings

Use a dataset item type and select **CC BY 4.0**. Retain the data-license scope and the explicit exclusion of the bundled scripts in the description. The anonymous attribution is the supplied neutral dataset title and version, the license link and an accurate indication of changes; retain further notices and source information if supplied. For anonymous review, use the platform's anonymous review-sharing mechanism and inspect the actual signed-out page and downloaded artifact. Do not add author-identifying details, related project links, affiliations or manuscript identifiers to reviewer-visible text. Retained recipe descriptions and feature values can still be searchable; hiding direct metadata does not guarantee unlinkability.

## Figshare workflow reference

Figshare documents private links for anonymous review of a draft: author metadata is removed from the private-link view, but identifying information inside files remains visible. Use the verified final archive, create the review link manually, and inspect that link while signed out before sharing it. A normal public item and a private review link should not be assumed to expose identical metadata. No platform item or link has been created by this task. See [Figshare: How to use Private Links](https://info.figshare.com/user-guide/how-to-use-private-links/).

The selected license is [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). Its [legal text](https://creativecommons.org/licenses/by/4.0/legalcode.en) requires retention of creator/attribution-party information when supplied and allows reasonable attribution arrangements. `LICENSE_DATA.md` provides the current anonymous form without adding restrictions. Software-license status remains `NOT_SPECIFIED`; the CC BY 4.0 choice covers only the designated data/documentation scope.
