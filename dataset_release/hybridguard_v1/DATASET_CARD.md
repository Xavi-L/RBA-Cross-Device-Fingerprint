# Dataset card

## Status and purpose

Version: `1.0-reviewer-release`. Public authorization: `CONFIRMED_BY_PROJECT_LEAD`, explicitly reported by the user on 2026-10-25 for all selected sources, including MTC. Authorized release records: 1,509. License: `PENDING_SELECTION`; no open license is applied. The separately built reviewer archive contains all 1,509 observations; the tracked repository data directory contains zero samples and no platform upload is performed. Intended purpose: inspect cross-view consistency and evidence availability using existing controlled and historical observations corresponding to an anonymous WWW 2027 manuscript.

## Collection and population

Controlled App and three specialist studies use repeated observations from API 29, 30 and 36 emulator environments. The linked Browser development study uses two recorded emulator/Browser contexts. MTC is a historical cloud collection selected through frozen manufacturer/model/Android-release representatives; its transitive grouping uses model, installation and session evidence. Group identities are not verified physical-device identities. Selection favors available paired observations and is not a probability sample of Android users or devices.

The frozen MTC archive routes 1,699 App records to 1,028 paired, 654 App-only, 11 partial and six repeated observations. Its paper cohort selects 891 of the paired observations. The 137 other paired rows, all 654 App-only rows and other routing classes are not added to this paper-linked release. Alternate snapshots and saved prediction rows are not independent observations.

## Annotation process

The exporter rechecks saved experimental membership against original App/Browser records, collection associations, target field values and restoration evidence. Controlled recipes require the saved effect audit, execution receipt and raw pre/active/post values to agree. Specialists retain the six memory no-effect operations and distinguish legitimate timezone/layout changes from target manipulations. Linked observations require completed endpoint bindings and recorded target changes; execution outcomes come independently from control/command evidence. Detector outputs are saved evidence and never used as target-effect ground truth.

There are 618 controlled/specialist/linked observations with labels verified against recorded evidence: 170 modified, 442 normal controls and six no-effect observations. The 891 MTC observations have unverified intervention labels and remain unlabeled. This verification reconciles existing records; it is not independent replication, forensic proof of every effect, or a guarantee of broader benignness.

## Observation quality

The original slot count is complete for 1,506 observations. Three selected MTC App payloads each lack five original field slots. The export represents their absences explicitly while retaining original unavailability statuses. A Browser is represented only when an original linked record exists. `observed`, unsupported, runtime error, timeout, permission denied, not applicable and missing are separate from privacy redaction. Known legacy sentinel values are retained as recorded rather than recoded as new observations.

The existing App177 normalizer and frozen field registry are reused. The legacy integer-only `visual_viewport_scale` declaration conflicts with original fractional scale measurements and the collector catalog's numeric type; only this field is widened to number in App Web and Browser Web. Values are unchanged. Other integer fields remain integer-typed.

## Distribution, dependence and splits

Actual distributions and field availability/redaction counts are in `statistics.json`. Historical MTC cohorts contain 630 discovery, 144 development and 117 reserved observations; their group counts are 610, 142 and 116. Group-disjoint historical assignments do not remove earlier global QC, diagnostics or development exposure. Controlled triplets, repeated environments, replacement attempts and cross-study configuration reuse create dependence. There is no new leakage-safe benchmark split, and no independent physical-device count is claimed.

## Ethics, access and residual risk

The project lead has confirmed public authorization for controlled experiments, specialist experiments, Linked Browser and MTC. This explicit user-provided confirmation supersedes earlier pending-authorization statements; source ownership and third-party publication permission are not reopened here. No new collection is performed. The packaging task does not independently establish institutional-review or exemption details and makes no affirmative claim about them.

A release-specific random identity mapping is private. High-entropy/free-text fingerprints, persistent IDs, precise times, sensitive paths and infrastructure are omitted or suppressed. Remaining hardware, geometry, language/timezone and grouping combinations can still support linking or reidentification, including linkage to already available source records. Original source paths, file-level hashes and row provenance are excluded from the Reviewer Release. Their removal reduces direct provenance linkage but does not prove unlinkability to other available records. The existing field projection and all authorized source subsets are retained. The remaining decisions are license selection and review-safe hosting metadata, as detailed in `RELEASE_REVIEW.md`.

## Recommended and unsupported use

Use the release to inspect controlled mechanisms and missingness within its recorded context. Do not use it to claim unseen-device/tool generalization, broad real-world attack prevalence, independent replication across repeated experiments, or complete reproduction of original unredacted detector scores. Do not merge unlabeled historical records into supervised negatives without a separate defensible labeling protocol. Do not infer missing Browser values or multiply saved model/fold outputs into observation counts.
