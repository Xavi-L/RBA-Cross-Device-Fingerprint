package com.example.hybridguard.featureapp

import android.util.Log
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONArray
import org.json.JSONObject

internal object BrowserPairTransport {
    private const val TAG = "HG-BrowserPair"
    private const val NGROK_SKIP_HEADER = "ngrok-skip-browser-warning"
    private const val NGROK_SKIP_VALUE = "true"
    private const val TICKET_ATTEMPTS = 3
    internal const val BINDING_MODE_PROVISIONAL = "provisional_session"
    internal const val BINDING_MODE_RECEIPT = "receipt_bound"
    private val ticketRetryDelaysMs = longArrayOf(300L, 900L)
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .writeTimeout(7, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .callTimeout(10, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    sealed class TicketResult {
        data class Issued(val ticket: BrowserTicket) : TicketResult()
        data class Failed(val retryable: Boolean, val detail: String) : TicketResult()
    }

    sealed class PollResult {
        data class Received(val result: BrowserPairPollResult) : PollResult()
        data class Failed(val retryable: Boolean, val detail: String) : PollResult()
    }

    fun requestProvisionalTicket(
        appSessionId: String,
        ticketRequestId: String,
        resolution: BrowserLaunchResolution,
        ticketEndpoint: String,
        browserProbeBaseUrl: String,
        webProbeRevision: String
    ): TicketResult = requestTicket(
        appSessionId = appSessionId,
        ticketRequestId = ticketRequestId,
        receipt = null,
        expectedBindingMode = BINDING_MODE_PROVISIONAL,
        resolution = resolution,
        ticketEndpoint = ticketEndpoint,
        browserProbeBaseUrl = browserProbeBaseUrl,
        webProbeRevision = webProbeRevision
    )

    fun requestReceiptBoundTicket(
        receipt: VerifiedCollectionReceipt,
        ticketRequestId: String,
        resolution: BrowserLaunchResolution,
        ticketEndpoint: String,
        browserProbeBaseUrl: String,
        webProbeRevision: String
    ): TicketResult = requestTicket(
        appSessionId = receipt.sessionId,
        ticketRequestId = ticketRequestId,
        receipt = receipt,
        expectedBindingMode = BINDING_MODE_RECEIPT,
        resolution = resolution,
        ticketEndpoint = ticketEndpoint,
        browserProbeBaseUrl = browserProbeBaseUrl,
        webProbeRevision = webProbeRevision
    )

    private fun requestTicket(
        appSessionId: String,
        ticketRequestId: String,
        receipt: VerifiedCollectionReceipt?,
        expectedBindingMode: String,
        resolution: BrowserLaunchResolution,
        ticketEndpoint: String,
        browserProbeBaseUrl: String,
        webProbeRevision: String
    ): TicketResult {
        val requestJson = buildTicketRequestJson(
            appSessionId = appSessionId,
            ticketRequestId = ticketRequestId,
            receipt = receipt,
            resolution = resolution,
            browserProbeBaseUrl = browserProbeBaseUrl,
            webProbeRevision = webProbeRevision
        )
        var lastFailure = TicketResult.Failed(true, "ticket request not attempted")
        for (attemptNumber in 1..TICKET_ATTEMPTS) {
            when (
                val attempt = executeTicketRequest(
                    requestJson,
                    appSessionId,
                    ticketRequestId,
                    receipt,
                    expectedBindingMode,
                    ticketEndpoint,
                    browserProbeBaseUrl
                )
            ) {
                is TicketResult.Issued -> return attempt
                is TicketResult.Failed -> {
                    lastFailure = attempt
                    if (!attempt.retryable || attemptNumber == TICKET_ATTEMPTS) {
                        break
                    }
                }
            }
            try {
                Thread.sleep(ticketRetryDelaysMs[attemptNumber - 1])
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                return TicketResult.Failed(true, "ticket request interrupted")
            }
        }
        return lastFailure
    }

    private fun executeTicketRequest(
        requestJson: JSONObject,
        appSessionId: String,
        ticketRequestId: String,
        receipt: VerifiedCollectionReceipt?,
        expectedBindingMode: String,
        ticketEndpoint: String,
        browserProbeBaseUrl: String
    ): TicketResult {
        val request = try {
            Request.Builder()
                .url(ticketEndpoint)
                .addHeader(NGROK_SKIP_HEADER, NGROK_SKIP_VALUE)
                .post(requestJson.toString().toRequestBody(jsonMediaType))
                .build()
        } catch (error: Exception) {
            return TicketResult.Failed(false, "invalid ticket endpoint: ${error.javaClass.simpleName}")
        }
        return try {
            httpClient.newCall(request).execute().use { response ->
                val responseText = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    val retryable = response.code == 408 || response.code == 429 || response.code >= 500
                    return TicketResult.Failed(retryable, "ticket HTTP ${response.code}")
                }
                val responseJson = try {
                    JSONObject(responseText)
                } catch (_: Exception) {
                    return TicketResult.Failed(true, "ticket response is not JSON")
                }
                val ticket = parseAndVerifyTicket(
                    responseJson,
                    appSessionId,
                    ticketRequestId,
                    receipt,
                    expectedBindingMode,
                    browserProbeBaseUrl
                ) ?: return TicketResult.Failed(
                    true,
                    "ticket response failed receipt/hash/origin verification"
                )
                Log.i(
                    TAG,
                    "ticket_issued pair_id=${ticket.pairId}; session=${ticket.appSessionId}; " +
                        "batch=${ticket.collectionBatchId}; duplicate=${ticket.duplicateTicketRequest}"
                )
                TicketResult.Issued(ticket)
            }
        } catch (error: Exception) {
            TicketResult.Failed(true, "ticket request failed: ${error.message ?: error.javaClass.simpleName}")
        }
    }

    internal fun parseAndVerifyTicket(
        responseJson: JSONObject,
        receipt: VerifiedCollectionReceipt,
        ticketRequestId: String,
        browserProbeBaseUrl: String
    ): BrowserTicket? = parseAndVerifyTicket(
        responseJson = responseJson,
        expectedAppSessionId = receipt.sessionId,
        expectedTicketRequestId = ticketRequestId,
        expectedReceipt = receipt,
        expectedBindingMode = BINDING_MODE_RECEIPT,
        browserProbeBaseUrl = browserProbeBaseUrl
    )

    internal fun parseAndVerifyProvisionalTicket(
        responseJson: JSONObject,
        appSessionId: String,
        ticketRequestId: String,
        browserProbeBaseUrl: String
    ): BrowserTicket? = parseAndVerifyTicket(
        responseJson = responseJson,
        expectedAppSessionId = appSessionId,
        expectedTicketRequestId = ticketRequestId,
        expectedReceipt = null,
        expectedBindingMode = BINDING_MODE_PROVISIONAL,
        browserProbeBaseUrl = browserProbeBaseUrl
    )

    private fun parseAndVerifyTicket(
        responseJson: JSONObject,
        expectedAppSessionId: String,
        expectedTicketRequestId: String,
        expectedReceipt: VerifiedCollectionReceipt?,
        expectedBindingMode: String,
        browserProbeBaseUrl: String
    ): BrowserTicket? {
        return try {
            require(responseJson.requiredText("status") == "issued")
            val pairStatus = responseJson.requiredText("pair_status")
            require(pairStatus in PENDING_PAIR_STATUSES)
            val appReceiptId = responseJson.optionalText("app_receipt_id")
            val appPayloadSha256 = responseJson.optionalText("app_payload_sha256")
            require((appReceiptId == null) == (appPayloadSha256 == null))
            val ticket = BrowserTicket(
                pairId = responseJson.requiredText("pair_id"),
                ticketRequestId = responseJson.requiredText("ticket_request_id"),
                browserTicket = responseJson.requiredText("browser_ticket"),
                pollToken = responseJson.requiredText("poll_token"),
                probeUrl = responseJson.requiredText("probe_url"),
                browserUploadUrl = responseJson.requiredText("browser_upload_url"),
                browserStageUrl = responseJson.requiredText("browser_stage_url"),
                expiresAt = responseJson.requiredText("expires_at"),
                collectionBatchId = responseJson.requiredText("collection_batch_id"),
                appSessionId = responseJson.requiredText("app_session_id"),
                appReceiptId = appReceiptId,
                appPayloadSha256 = appPayloadSha256,
                ticketBindingMode = responseJson.requiredText("ticket_binding_mode"),
                duplicateTicketRequest = responseJson.optBoolean("duplicate_ticket_request", false)
            )
            require(ticket.appSessionId == expectedAppSessionId)
            require(ticket.ticketRequestId == expectedTicketRequestId)
            require(ticket.ticketBindingMode == expectedBindingMode)
            if (expectedReceipt != null) {
                require(ticket.appReceiptId == expectedReceipt.receiptId)
                require(ticket.appPayloadSha256 == expectedReceipt.payloadSha256)
                require(ticket.collectionBatchId == expectedReceipt.collectionBatchId)
            } else if (ticket.appReceiptId != null) {
                require(ticket.appReceiptId.matches(RECEIPT_ID_PATTERN))
                require(ticket.appPayloadSha256?.matches(SHA256_PATTERN) == true)
            }
            require(ticket.pairId.matches(Regex("[A-Za-z0-9._:-]{8,160}")))
            require(ticket.browserTicket.length >= 24)
            require(ticket.pollToken.length >= 24)
            require(sameWebOrigin(ticket.probeUrl, browserProbeBaseUrl))
            require(validWebUrl(ticket.browserUploadUrl))
            require(validWebUrl(ticket.browserStageUrl))
            require(sameWebOrigin(ticket.browserStageUrl, ticket.browserUploadUrl))
            require(probeFragmentMatchesTicket(ticket))
            ticket
        } catch (_: Exception) {
            null
        }
    }

    fun poll(state: BrowserPairPollState): PollResult {
        val pollUrl = state.pollBaseUrl.toHttpUrlOrNull()
            ?.newBuilder()
            ?.addPathSegment(state.pairId)
            ?.build()
            ?: return PollResult.Failed(false, "invalid poll endpoint")
        val request = try {
            Request.Builder()
                .url(pollUrl)
                .addHeader("Authorization", "Bearer ${state.pollToken}")
                .addHeader(NGROK_SKIP_HEADER, NGROK_SKIP_VALUE)
                .get()
                .build()
        } catch (error: Exception) {
            return PollResult.Failed(false, "invalid poll endpoint: ${error.javaClass.simpleName}")
        }
        return try {
            httpClient.newCall(request).execute().use { response ->
                val responseText = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    val retryable = response.code == 408 || response.code == 429 || response.code >= 500
                    return PollResult.Failed(
                        retryable,
                        "poll HTTP ${response.code}"
                    )
                }
                val json = try {
                    JSONObject(responseText)
                } catch (_: Exception) {
                    return PollResult.Failed(true, "poll response is not JSON")
                }
                parseAndVerifyPoll(json, state)?.let(PollResult::Received)
                    ?: PollResult.Failed(true, "poll response failed pair/receipt/hash verification")
            }
        } catch (error: Exception) {
            PollResult.Failed(true, "poll request failed: ${error.message ?: error.javaClass.simpleName}")
        }
    }

    fun reportLaunchAttempt(
        state: BrowserPairPollState,
        launchAttempt: Int
    ): Boolean {
        val payload = JSONObject().apply {
            put("pair_id", state.pairId)
            put("stage", "launch_attempted")
            put("launch_attempt", launchAttempt.coerceIn(1, 2))
            put("client_stage_at_ms", System.currentTimeMillis())
        }
        val request = try {
            Request.Builder()
                .url(state.browserStageUrl)
                .addHeader("Authorization", "Bearer ${state.pollToken}")
                .addHeader(NGROK_SKIP_HEADER, NGROK_SKIP_VALUE)
                .post(payload.toString().toRequestBody(jsonMediaType))
                .build()
        } catch (error: Exception) {
            Log.w(TAG, "Invalid browser-stage endpoint", error)
            return false
        }
        return try {
            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w(
                        TAG,
                        "launch_stage_http pair_id=${state.pairId}; " +
                            "attempt=$launchAttempt; code=${response.code}"
                    )
                }
                response.isSuccessful
            }
        } catch (error: Exception) {
            Log.w(
                TAG,
                "launch_stage_failed pair_id=${state.pairId}; attempt=$launchAttempt",
                error
            )
            false
        }
    }

    internal fun parseAndVerifyPoll(
        responseJson: JSONObject,
        state: BrowserPairPollState
    ): BrowserPairPollResult? {
        return try {
            val rootStatus = responseJson.requiredText("status")
            require(rootStatus == "success" || rootStatus in TERMINAL_PAIR_STATUSES + PENDING_PAIR_STATUSES)
            val pairStatus = responseJson.optString("pair_status")
                .trim()
                .ifEmpty { rootStatus }
            require(pairStatus in TERMINAL_PAIR_STATUSES + PENDING_PAIR_STATUSES)
            require(responseJson.requiredText("pair_id") == state.pairId)
            require(
                responseJson.requiredText("ticket_request_id") ==
                    state.ticketRequestId
            )
            require(responseJson.requiredText("collection_batch_id") == state.collectionBatchId)
            require(responseJson.requiredText("app_session_id") == state.appSessionId)
            require(responseJson.requiredText("ticket_binding_mode") == state.ticketBindingMode)
            val appReceiptId = responseJson.optionalText("app_receipt_id")
            val appPayloadSha256 = responseJson.optionalText("app_payload_sha256")
            require((appReceiptId == null) == (appPayloadSha256 == null))
            if (state.appReceiptId != null) {
                require(appReceiptId == state.appReceiptId)
                require(appPayloadSha256 == state.appPayloadSha256)
            } else if (appReceiptId != null) {
                require(appReceiptId.matches(RECEIPT_ID_PATTERN))
                require(appPayloadSha256?.matches(SHA256_PATTERN) == true)
            }

            val terminal = pairStatus in TERMINAL_PAIR_STATUSES
            if (pairStatus in TERMINAL_REQUIRING_COMPLETE_BINDING) {
                require(appReceiptId != null)
                require(appPayloadSha256 != null)
            }
            if (terminal && pairStatus !in TERMINAL_WITHOUT_BROWSER_PAYLOAD) {
                require(responseJson.requiredText("browser_session_id").isNotEmpty())
                require(responseJson.requiredText("browser_receipt_id").isNotEmpty())
                require(
                    responseJson.requiredText("browser_payload_sha256")
                        .matches(Regex("[0-9a-f]{64}"))
                )
            }
            BrowserPairPollResult(
                pairStatus = pairStatus,
                terminal = terminal,
                detail = if (terminal) {
                    "Browser pair reached terminal status $pairStatus."
                } else {
                    "Browser pair is still $pairStatus."
                },
                appReceiptId = appReceiptId,
                appPayloadSha256 = appPayloadSha256,
                latestBrowserStage = responseJson.optionalText("latest_browser_stage"),
                latestLaunchAttempt = responseJson.optInt("latest_launch_attempt", 0),
                browserStageCount = responseJson.optInt("browser_stage_count", 0)
            )
        } catch (_: Exception) {
            null
        }
    }

    internal fun validWebUrl(value: String): Boolean {
        val parsed = value.toHttpUrlOrNull() ?: return false
        return parsed.scheme in setOf("http", "https") &&
            parsed.host.isNotBlank() &&
            parsed.username.isEmpty() &&
            parsed.password.isEmpty()
    }

    internal fun sameWebOrigin(left: String, right: String): Boolean {
        val leftUrl = left.toHttpUrlOrNull() ?: return false
        val rightUrl = right.toHttpUrlOrNull() ?: return false
        return leftUrl.scheme.equals(rightUrl.scheme, ignoreCase = true) &&
            leftUrl.host.equals(rightUrl.host, ignoreCase = true) &&
            leftUrl.port == rightUrl.port
    }

    private fun probeFragmentMatchesTicket(ticket: BrowserTicket): Boolean {
        val fragment = ticket.probeUrl.toHttpUrlOrNull()?.fragment ?: return false
        val fragmentAsQuery = "https://fragment.invalid/?$fragment".toHttpUrlOrNull()
            ?: return false
        return fragmentAsQuery.queryParameter("pair_id") == ticket.pairId &&
            fragmentAsQuery.queryParameter("browser_ticket") == ticket.browserTicket &&
            fragmentAsQuery.queryParameter("browser_upload_url") == ticket.browserUploadUrl &&
            fragmentAsQuery.queryParameter("browser_stage_url") == ticket.browserStageUrl &&
            fragmentAsQuery.queryParameter("launch_attempt") == "1"
    }

    internal fun buildTicketRequestJson(
        appSessionId: String,
        ticketRequestId: String,
        receipt: VerifiedCollectionReceipt?,
        resolution: BrowserLaunchResolution,
        browserProbeBaseUrl: String,
        webProbeRevision: String
    ): JSONObject = JSONObject().apply {
        put("ticket_request_id", ticketRequestId)
        put("app_session_id", appSessionId)
        if (receipt != null) {
            put("app_receipt_id", receipt.receiptId)
            put("app_payload_sha256", receipt.payloadSha256)
        }
        // Keep the legacy field for older collectors while recording the
        // clarified available-browser semantics explicitly.
        put("resolved_browser_package", resolution.packageName ?: JSONObject.NULL)
        put("selected_browser_package", resolution.packageName ?: JSONObject.NULL)
        put("launch_resolution_status", resolution.status)
        put("selected_browser_activity", resolution.activityName ?: JSONObject.NULL)
        put(
            "browser_candidate_packages",
            JSONArray(resolution.visibleHandlerPackageNames)
        )
        put(
            "browser_selection_policy_revision",
            resolution.selectionPolicyRevision
        )
        put("web_probe_revision", webProbeRevision)
        put("browser_probe_base_url", browserProbeBaseUrl)
    }

    private val RECEIPT_ID_PATTERN = Regex("[0-9a-f]{24}")
    private val SHA256_PATTERN = Regex("[0-9a-f]{64}")
    private val PENDING_PAIR_STATUSES = setOf(
        "pending",
        "awaiting_app_and_browser",
        "awaiting_app",
        "awaiting_browser"
    )
    private val TERMINAL_PAIR_STATUSES = setOf(
        "browser_received",
        "completed",
        "complete",
        "complete_partial",
        "expired"
    )
    private val TERMINAL_WITHOUT_BROWSER_PAYLOAD = setOf("complete_partial", "expired")
    private val TERMINAL_REQUIRING_COMPLETE_BINDING = setOf(
        "browser_received",
        "completed",
        "complete"
    )
}
