package com.example.hybridguard.featureapp

import org.json.JSONObject
import java.util.Locale

internal const val BROWSER_SELECTION_POLICY_REVISION =
    "available-browser-v2-package-scoped"

/**
 * A receipt is considered verified only after the upload transport has checked
 * the complete collection-receipt-v1 envelope. The browser ticket request sends
 * all three binding values back to the server, which then verifies them against
 * its durable receipt ledger before issuing a browser ticket.
 */
internal data class VerifiedCollectionReceipt(
    val receiptId: String,
    val sessionId: String,
    val payloadSha256: String,
    val collectionBatchId: String,
    val validationStatus: String,
    val warningCount: Int
)

/**
 * Durable bridge between a WorkManager upload receipt and the next foreground
 * Activity opportunity. Android background-start restrictions mean the Worker
 * must never launch the browser directly.
 */
internal data class PendingBrowserHandoff(
    val receipt: VerifiedCollectionReceipt,
    val collectEndpoint: String,
    val browserTicketRequestId: String
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("receipt_id", receipt.receiptId)
        put("session_id", receipt.sessionId)
        put("payload_sha256", receipt.payloadSha256)
        put("collection_batch_id", receipt.collectionBatchId)
        put("validation_status", receipt.validationStatus)
        put("warning_count", receipt.warningCount)
        put("collect_endpoint", collectEndpoint)
        put("browser_ticket_request_id", browserTicketRequestId)
    }

    companion object {
        fun fromJson(value: String): PendingBrowserHandoff? {
            return try {
                val json = JSONObject(value)
                PendingBrowserHandoff(
                    receipt = VerifiedCollectionReceipt(
                        receiptId = json.requiredText("receipt_id"),
                        sessionId = json.requiredText("session_id"),
                        payloadSha256 = json.requiredText("payload_sha256"),
                        collectionBatchId = json.requiredText("collection_batch_id"),
                        validationStatus = json.requiredText("validation_status"),
                        warningCount = json.getInt("warning_count")
                    ),
                    collectEndpoint = json.requiredText("collect_endpoint"),
                    browserTicketRequestId = json.requiredText("browser_ticket_request_id")
                )
            } catch (_: Exception) {
                null
            }
        }
    }
}

/**
 * Non-destructive lease over one persisted background-upload handoff.
 *
 * The serialized value is retained so acknowledgement can remove only the
 * exact record that was prepared. If another writer replaces the handoff in
 * the meantime, the newer value remains available for a later retry.
 */
internal data class PendingBrowserHandoffClaim(
    val storageKey: String,
    val serializedValue: String,
    val handoff: PendingBrowserHandoff
)

internal data class BrowserLaunchResolution(
    val status: String,
    val packageName: String?,
    val detail: String,
    val activityName: String? = null,
    val visibleHandlerPackageNames: List<String> = emptyList(),
    val selectionPolicyRevision: String = BROWSER_SELECTION_POLICY_REVISION
) {
    val canLaunch: Boolean
        get() = (
            status == STATUS_AVAILABLE_BROWSER_RESOLVED ||
                status == STATUS_AVAILABLE_BROWSER_RANKED
            ) &&
            !packageName.isNullOrBlank()

    companion object {
        const val STATUS_AVAILABLE_BROWSER_RESOLVED = "available_browser_resolved"
        const val STATUS_AVAILABLE_BROWSER_RANKED = "available_browser_ranked"
        const val STATUS_NO_TRUSTED_BROWSER = "no_trusted_browser_candidate"
        const val STATUS_NO_HANDLER = "no_handler"
        const val STATUS_RESOLUTION_ERROR = "resolution_error"
    }
}

internal data class BrowserHandlerCandidate(
    val packageName: String,
    val activityName: String,
    val declaredBrowserApp: Boolean = false
)

/**
 * Pure selection function kept separate from PackageManager calls so candidate
 * filtering and ranking remain deterministic and unit-testable on API 21+.
 *
 * Android 5-9 has no reliable public API that identifies every "real browser".
 * An arbitrary HTTPS handler can be a social/search app backed by an embedded
 * WebView, so unattended tests select only CATEGORY_APP_BROWSER declarations
 * or exact package IDs reviewed as standalone browsers.
 */
internal object BrowserLaunchDecision {
    private val preferredBrowserPackages = listOf(
        "com.android.browser",
        "com.sec.android.app.sbrowser",
        "com.huawei.browser",
        "com.hihonor.browser",
        "com.vivo.browser",
        "com.heytap.browser",
        "com.coloros.browser",
        "com.oppo.browser",
        "com.mi.globalbrowser",
        "com.miui.browser",
        "cn.nubia.browser",
        "com.oneplus.browser",
        "com.lenovo.browser",
        "com.zte.browser",
        "com.meizu.flyme.browser",
        "com.android.chrome",
        "org.chromium.chrome",
        "com.microsoft.emmx",
        "org.mozilla.firefox",
        "org.mozilla.fenix",
        "com.brave.browser",
        "com.vivaldi.browser",
        "com.kiwibrowser.browser",
        "com.duckduckgo.mobile.android",
        "com.opera.browser",
        "com.opera.mini.native",
        "com.opera.touch",
        "com.yandex.browser",
        "com.tencent.mtt",
        "com.ucmobile",
        "com.baidu.browser",
        "sogou.mobile.explorer",
        "com.qihoo.browser"
    )
    private val preferredPackageRanks = preferredBrowserPackages
        .mapIndexed { index, packageName -> packageName to index }
        .toMap()
    fun select(
        resolvedPackageName: String?,
        resolvedActivityName: String?,
        handlers: Collection<BrowserHandlerCandidate>
    ): BrowserLaunchResolution {
        val candidates = handlers
            .mapNotNull(::normalize)
            .distinctBy {
                normalizedText(it.packageName) to normalizedText(it.activityName)
            }
            .sortedWith(
                compareBy(
                    { normalizedText(it.packageName) },
                    { normalizedText(it.activityName) }
                )
            )
        val visiblePackages = candidates
            .map(BrowserHandlerCandidate::packageName)
            .distinct()
            .sorted()

        if (candidates.isEmpty()) {
            return BrowserLaunchResolution(
                status = BrowserLaunchResolution.STATUS_NO_HANDLER,
                packageName = null,
                detail = "No enabled, exported HTTPS handler is visible to PackageManager.",
                visibleHandlerPackageNames = visiblePackages
            )
        }

        val resolvedPackage = resolvedPackageName?.trim().orEmpty()
        val resolvedActivity = resolvedActivityName?.trim().orEmpty()
        val resolvedCandidate = candidates.firstOrNull {
            it.packageName == resolvedPackage &&
                (resolvedActivity.isEmpty() || it.activityName == resolvedActivity) &&
                trustRank(it) != null
        } ?: candidates.firstOrNull {
            it.packageName == resolvedPackage && trustRank(it) != null
        }
        if (resolvedCandidate != null) {
            return BrowserLaunchResolution(
                status = BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RESOLVED,
                packageName = resolvedCandidate.packageName,
                activityName = resolvedCandidate.activityName,
                detail =
                    "PackageManager resolved a trusted available browser; " +
                        "the package-scoped web Intent will be launched without " +
                        "a cross-app chooser.",
                visibleHandlerPackageNames = visiblePackages
            )
        }

        val rankedCandidate = candidates
            .mapNotNull { candidate ->
                trustRank(candidate)?.let { rank -> candidate to rank }
            }
            .sortedWith(
                compareBy<Pair<BrowserHandlerCandidate, Int>>(
                    { it.second },
                    { normalizedText(it.first.packageName) },
                    { normalizedText(it.first.activityName) }
                )
            )
            .firstOrNull()
            ?.first
        if (rankedCandidate == null) {
            return BrowserLaunchResolution(
                status = BrowserLaunchResolution.STATUS_NO_TRUSTED_BROWSER,
                packageName = null,
                detail =
                    "HTTPS handlers are visible, but none is trusted as a standalone browser.",
                visibleHandlerPackageNames = visiblePackages
            )
        }

        return BrowserLaunchResolution(
            status = BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RANKED,
            packageName = rankedCandidate.packageName,
            activityName = rankedCandidate.activityName,
            detail =
                "No trusted browser was uniquely resolved; policy " +
                    "$BROWSER_SELECTION_POLICY_REVISION selected a ranked browser candidate.",
            visibleHandlerPackageNames = visiblePackages
        )
    }

    private fun normalize(candidate: BrowserHandlerCandidate): BrowserHandlerCandidate? {
        val packageName = candidate.packageName.trim()
        val activityName = candidate.activityName.trim()
        if (packageName.isEmpty() || activityName.isEmpty()) {
            return null
        }
        return candidate.copy(
            packageName = packageName,
            activityName = activityName
        )
    }

    private fun trustRank(candidate: BrowserHandlerCandidate): Int? {
        val packageName = normalizedText(candidate.packageName)
        preferredPackageRanks[packageName]?.let { return it }
        if (candidate.declaredBrowserApp) {
            return 1_000
        }
        return null
    }

    private fun normalizedText(value: String): String {
        return value.trim().lowercase(Locale.ROOT)
    }
}

internal data class BrowserTicket(
    val pairId: String,
    val ticketRequestId: String,
    val browserTicket: String,
    val pollToken: String,
    val probeUrl: String,
    val browserUploadUrl: String,
    val browserStageUrl: String,
    val expiresAt: String,
    val collectionBatchId: String,
    val appSessionId: String,
    val appReceiptId: String?,
    val appPayloadSha256: String?,
    val ticketBindingMode: String,
    val duplicateTicketRequest: Boolean
)

internal data class BrowserPairPollState(
    val pairId: String,
    val ticketRequestId: String,
    val pollToken: String,
    val pollBaseUrl: String,
    val browserStageUrl: String,
    val collectionBatchId: String,
    val appSessionId: String,
    val appReceiptId: String?,
    val appPayloadSha256: String?,
    val ticketBindingMode: String,
    val expiresAt: String
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("pair_id", pairId)
        put("ticket_request_id", ticketRequestId)
        put("poll_token", pollToken)
        put("poll_base_url", pollBaseUrl)
        put("browser_stage_url", browserStageUrl)
        put("collection_batch_id", collectionBatchId)
        put("app_session_id", appSessionId)
        put("app_receipt_id", appReceiptId ?: JSONObject.NULL)
        put("app_payload_sha256", appPayloadSha256 ?: JSONObject.NULL)
        put("ticket_binding_mode", ticketBindingMode)
        put("expires_at", expiresAt)
    }

    companion object {
        fun fromJson(value: String): BrowserPairPollState? {
            return try {
                val json = JSONObject(value)
                BrowserPairPollState(
                    pairId = json.requiredText("pair_id"),
                    ticketRequestId = json.requiredText("ticket_request_id"),
                    pollToken = json.requiredText("poll_token"),
                    pollBaseUrl = json.requiredText("poll_base_url"),
                    browserStageUrl = json.requiredText("browser_stage_url"),
                    collectionBatchId = json.requiredText("collection_batch_id"),
                    appSessionId = json.requiredText("app_session_id"),
                    appReceiptId = json.optionalText("app_receipt_id"),
                    appPayloadSha256 = json.optionalText("app_payload_sha256"),
                    ticketBindingMode = json.requiredText("ticket_binding_mode"),
                    expiresAt = json.requiredText("expires_at")
                ).takeIf {
                    (it.appReceiptId == null) == (it.appPayloadSha256 == null)
                }
            } catch (_: Exception) {
                null
            }
        }
    }
}

internal data class BrowserPairPollResult(
    val pairStatus: String,
    val terminal: Boolean,
    val detail: String,
    val appReceiptId: String?,
    val appPayloadSha256: String?,
    val latestBrowserStage: String?,
    val latestLaunchAttempt: Int,
    val browserStageCount: Int
)

internal fun JSONObject.requiredText(key: String): String {
    val value = optString(key).trim()
    require(value.isNotEmpty() && value != "null") { "$key is missing" }
    return value
}

internal fun JSONObject.optionalText(key: String): String? {
    if (!has(key) || isNull(key)) {
        return null
    }
    return optString(key).trim().takeIf { it.isNotEmpty() && it != "null" }
}
