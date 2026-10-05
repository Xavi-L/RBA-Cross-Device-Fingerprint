package com.example.hybridguard.featureapp

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.net.toUri

internal object BrowserCollectionCoordinator {
    private const val TAG = "HG-BrowserFlow"

    sealed class Preparation {
        data class Ready(
            val ticket: BrowserTicket,
            val resolution: BrowserLaunchResolution,
            val pollState: BrowserPairPollState
        ) : Preparation()

        data class Skipped(val detail: String) : Preparation()
        data class Failed(val detail: String) : Preparation()
    }

    fun prepareProvisional(
        context: Context,
        appSessionId: String,
        ticketRequestId: String,
        collectEndpoint: String = BuildConfig.COLLECT_ENDPOINT
    ): Preparation = prepare(
        context = context,
        appSessionId = appSessionId,
        ticketRequestId = ticketRequestId,
        receipt = null,
        collectEndpoint = collectEndpoint
    )

    fun prepareReceiptBound(
        context: Context,
        receipt: VerifiedCollectionReceipt,
        ticketRequestId: String,
        collectEndpoint: String = BuildConfig.COLLECT_ENDPOINT
    ): Preparation = prepare(
        context = context,
        appSessionId = receipt.sessionId,
        ticketRequestId = ticketRequestId,
        receipt = receipt,
        collectEndpoint = collectEndpoint
    )

    private fun prepare(
        context: Context,
        appSessionId: String,
        ticketRequestId: String,
        receipt: VerifiedCollectionReceipt?,
        collectEndpoint: String
    ): Preparation {
        val probeBaseUrl = BuildConfig.BROWSER_PROBE_BASE_URL.trim()
        val ticketEndpoint = endpointForActiveCollector(
            BuildConfig.BROWSER_TICKET_ENDPOINT,
            "/api/collect/browser-ticket",
            collectEndpoint
        )
        val pollBaseUrl = endpointForActiveCollector(
            BuildConfig.BROWSER_PAIR_POLL_BASE_URL,
            "/api/collect/browser-pairs",
            collectEndpoint
        )
        val webProbeRevision = BuildConfig.WEB_PROBE_REVISION.trim()

        if (probeBaseUrl.isEmpty()) {
            val detail =
                "Browser companion collection disabled: hybridguardBrowserProbeBaseUrl is blank."
            Log.i(TAG, detail)
            return Preparation.Skipped(detail)
        }
        if (
            !BrowserPairTransport.validWebUrl(probeBaseUrl) ||
            !BrowserPairTransport.validWebUrl(ticketEndpoint) ||
            !BrowserPairTransport.validWebUrl(pollBaseUrl) ||
            webProbeRevision.isEmpty()
        ) {
            val detail = "Browser companion collection skipped because BuildConfig URLs/revision are invalid."
            Log.e(TAG, detail)
            return Preparation.Failed(detail)
        }

        val resolution = AvailableBrowserResolver.resolve(context, probeBaseUrl)
        Log.i(
            TAG,
            "requesting_ticket session=$appSessionId; request=$ticketRequestId; " +
                "receipt=${receipt?.receiptId ?: "provisional"}; " +
                "resolution=${resolution.status}; package=${resolution.packageName ?: "none"}; " +
                "activity=${resolution.activityName ?: "none"}; " +
                "policy=${resolution.selectionPolicyRevision}"
        )
        val result = if (receipt == null) {
            BrowserPairTransport.requestProvisionalTicket(
                appSessionId = appSessionId,
                ticketRequestId = ticketRequestId,
                resolution = resolution,
                ticketEndpoint = ticketEndpoint,
                browserProbeBaseUrl = probeBaseUrl,
                webProbeRevision = webProbeRevision
            )
        } else {
            BrowserPairTransport.requestReceiptBoundTicket(
                receipt = receipt,
                ticketRequestId = ticketRequestId,
                resolution = resolution,
                ticketEndpoint = ticketEndpoint,
                browserProbeBaseUrl = probeBaseUrl,
                webProbeRevision = webProbeRevision
            )
        }
        return when (result) {
            is BrowserPairTransport.TicketResult.Failed -> {
                val detail =
                    "Browser ticket failed: ${result.detail}"
                Log.w(TAG, detail)
                Preparation.Failed(detail)
            }
            is BrowserPairTransport.TicketResult.Issued -> {
                val ticket = result.ticket
                val pollState = BrowserPairPollState(
                    pairId = ticket.pairId,
                    ticketRequestId = ticket.ticketRequestId,
                    pollToken = ticket.pollToken,
                    pollBaseUrl = pollBaseUrl,
                    browserStageUrl = ticket.browserStageUrl,
                    collectionBatchId = ticket.collectionBatchId,
                    appSessionId = ticket.appSessionId,
                    appReceiptId = ticket.appReceiptId,
                    appPayloadSha256 = ticket.appPayloadSha256,
                    ticketBindingMode = ticket.ticketBindingMode,
                    expiresAt = ticket.expiresAt
                )
                try {
                    BrowserPairPollWorker.persistAndEnqueue(
                        context.applicationContext,
                        pollState
                    )
                } catch (error: Exception) {
                    val detail =
                        "Ticket issued but durable poll scheduling failed: " +
                            (error.message ?: error.javaClass.simpleName)
                    Log.e(TAG, detail, error)
                    return Preparation.Failed(detail)
                }
                Preparation.Ready(ticket, resolution, pollState)
            }
        }
    }

    fun explicitLaunchIntent(
        preparation: Preparation.Ready,
        launchAttempt: Int = 1
    ): Intent? {
        if (!preparation.resolution.canLaunch) {
            return null
        }
        val browserPackage = preparation.resolution.packageName ?: return null
        val originalUri = preparation.ticket.probeUrl.toUri()
        val retainedFragment = originalUri.encodedFragment
            .orEmpty()
            .split("&")
            .filterNot { it.startsWith("launch_attempt=") }
            .filter(String::isNotBlank)
            .plus("launch_attempt=${launchAttempt.coerceIn(1, 2)}")
            .joinToString("&")
        val launchUri = originalUri.buildUpon()
            .encodedFragment(retainedFragment)
            .build()
        return Intent(Intent.ACTION_VIEW, launchUri).apply {
            addCategory(Intent.CATEGORY_BROWSABLE)
            setPackage(browserPackage)
        }
    }

    /**
     * A debug launch may override only COLLECT_ENDPOINT through its Intent.
     * If ticket/poll still equal their generated defaults, keep all requests on
     * the backend that owns the receipt. Explicit Gradle overrides remain
     * authoritative.
     */
    private fun endpointForActiveCollector(
        configuredEndpoint: String,
        defaultPath: String,
        activeCollectEndpoint: String
    ): String {
        val configuredCollectOrigin =
            ExpandedUploadTransport.endpointOrigin(BuildConfig.COLLECT_ENDPOINT)
        val configuredDefault = configuredCollectOrigin + defaultPath
        return if (configuredEndpoint.trim() == configuredDefault) {
            ExpandedUploadTransport.endpointOrigin(activeCollectEndpoint) + defaultPath
        } else {
            configuredEndpoint.trim()
        }
    }
}
