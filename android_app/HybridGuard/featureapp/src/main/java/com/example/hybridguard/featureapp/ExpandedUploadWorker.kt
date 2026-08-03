package com.example.hybridguard.featureapp

import android.content.Context
import android.net.Uri
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import android.util.Log
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

internal object ExpandedUploadTransport {
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .writeTimeout(6, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .callTimeout(8, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()
    private val readinessVerifiedEndpoints = mutableSetOf<String>()

    data class Attempt(
        val uploaded: Boolean,
        val retryable: Boolean,
        val detail: String,
        val receipt: VerifiedCollectionReceipt? = null
    )

    fun upload(payloadJson: String, endpoint: String): Attempt {
        val resolvedEndpoint = resolveEndpoint(endpoint)
        val readiness = ensureReadiness(resolvedEndpoint)
        if (!readiness.uploaded) {
            return readiness
        }
        val body = payloadJson.toRequestBody(JSON_MEDIA_TYPE)
        val request = Request.Builder()
            .url(resolvedEndpoint)
            .addHeader("ngrok-skip-browser-warning", "true")
            .post(body)
            .build()

        return try {
            httpClient.newCall(request).execute().use { response ->
                when {
                    response.isSuccessful -> {
                        val responseText = response.body?.string().orEmpty()
                        val verifiedReceipt = parseAndVerifyReceipt(payloadJson, responseText)
                        if (verifiedReceipt != null) {
                            Attempt(
                                true,
                                false,
                                "HTTP ${response.code}; receipt=${verifiedReceipt.receiptId}; " +
                                    "sha256=${verifiedReceipt.payloadSha256}; " +
                                    "batch=${verifiedReceipt.collectionBatchId}; " +
                                    "warnings=${verifiedReceipt.warningCount}",
                                verifiedReceipt
                            )
                        } else {
                            Log.w(
                                "HG-ExpandedUpload",
                                "Rejecting HTTP ${response.code}: receipt/session/hash contract invalid"
                            )
                            Attempt(
                                false,
                                true,
                                "HTTP ${response.code}; collection receipt/session/hash contract invalid"
                            )
                        }
                    }
                    response.code == 408 || response.code == 429 || response.code >= 500 ->
                        Attempt(false, true, "HTTP ${response.code}")
                    else -> Attempt(false, false, "HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            Attempt(false, true, e.message ?: e.javaClass.simpleName)
        }
    }

    private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    private val RECEIPT_ID_PATTERN = Regex("[0-9a-f]{24}")
    private val SHA256_PATTERN = Regex("[0-9a-f]{64}")

    const val EXTRA_COLLECT_ENDPOINT =
        "com.example.hybridguard.featureapp.COLLECT_ENDPOINT"

    fun resolveEndpoint(override: String?): String {
        val candidate = override?.trim()?.takeIf { BuildConfig.DEBUG } ?: BuildConfig.COLLECT_ENDPOINT
        return try {
            val parsed = Uri.parse(candidate)
            if (
                parsed.scheme in setOf("http", "https") &&
                !parsed.host.isNullOrBlank() &&
                parsed.userInfo.isNullOrBlank()
            ) {
                candidate
            } else {
                BuildConfig.COLLECT_ENDPOINT
            }
        } catch (_: Exception) {
            BuildConfig.COLLECT_ENDPOINT
        }
    }

    fun endpointOrigin(endpoint: String): String {
        val parsed = Uri.parse(resolveEndpoint(endpoint))
        val defaultPort = if (parsed.scheme == "https") 443 else 80
        val port = parsed.port.takeIf { it > 0 && it != defaultPort }
        return "${parsed.scheme}://${parsed.host}${port?.let { ":$it" }.orEmpty()}"
    }

    internal fun parseAndVerifyReceipt(
        payloadJson: String,
        responseText: String
    ): VerifiedCollectionReceipt? {
        return try {
            val payload = JSONObject(payloadJson)
            val expectedSessionId = payload.requiredText("session_id")
            val expectedCollector = payload.requiredText("collector_app")
            val expectedSchema = payload.requiredText("schema_version")
            val responseJson = JSONObject(responseText)
            require(responseJson.requiredText("status") == "success")
            require(responseJson.requiredText("session_id") == expectedSessionId)
            val receipt = responseJson.getJSONObject("receipt")
            val receiptId = receipt.requiredText("receipt_id")
            val receiptSessionId = receipt.requiredText("session_id")
            val payloadSha256 = receipt.requiredText("payload_sha256")
            val collectionBatchId = receipt.requiredText("collection_batch_id")
            val validationStatus = receipt.requiredText("validation_status")
            val warnings = receipt.getJSONArray("validation_warnings")

            require(receipt.requiredText("receipt_schema_version") == "collection-receipt-v1")
            require(receiptId.matches(RECEIPT_ID_PATTERN))
            require(receiptSessionId == expectedSessionId)
            require(payloadSha256.matches(SHA256_PATTERN))
            require(receipt.requiredText("collector_app") == expectedCollector)
            require(receipt.requiredText("schema_version") == expectedSchema)
            require(receipt.requiredText("storage_target") == "expanded_collected_data.jsonl")
            require(validationStatus in setOf("accepted", "accepted_with_warnings"))

            VerifiedCollectionReceipt(
                receiptId = receiptId,
                sessionId = receiptSessionId,
                payloadSha256 = payloadSha256,
                collectionBatchId = collectionBatchId,
                validationStatus = validationStatus,
                warningCount = warnings.length()
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun ensureReadiness(endpoint: String): Attempt {
        synchronized(readinessVerifiedEndpoints) {
            if (endpoint in readinessVerifiedEndpoints) {
                return Attempt(true, false, "readiness cached")
            }
        }
        val endpointUri = Uri.parse(endpoint)
        val readinessUrl = endpointUri.buildUpon()
            .path("/api/collect/readiness")
            .clearQuery()
            .fragment(null)
            .build()
            .toString()
        val request = Request.Builder()
            .url(readinessUrl)
            .addHeader("ngrok-skip-browser-warning", "true")
            .get()
            .build()
        return try {
            httpClient.newCall(request).execute().use { response ->
                val responseJson = try {
                    JSONObject(response.body?.string().orEmpty())
                } catch (_: Exception) {
                    null
                }
                val schemas = responseJson?.optJSONArray("supported_expanded_schema_versions")
                var schemaSupported = false
                if (schemas != null) {
                    for (index in 0 until schemas.length()) {
                        if (schemas.optString(index) == CollectionManifestBuilder.FEATURE_SCHEMA_VERSION) {
                            schemaSupported = true
                            break
                        }
                    }
                }
                val ready = response.isSuccessful &&
                    responseJson != null &&
                    responseJson.optString("status") == "ready" &&
                    responseJson.optBoolean("accepts_partial_expanded_payloads") &&
                    responseJson.optBoolean("collection_receipts_enabled") &&
                    schemaSupported
                if (ready) {
                    synchronized(readinessVerifiedEndpoints) {
                        readinessVerifiedEndpoints.add(endpoint)
                    }
                    Attempt(true, false, "readiness verified")
                } else {
                    Attempt(false, true, "readiness contract unavailable at HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            Attempt(false, true, "readiness failed: ${e.message ?: e.javaClass.simpleName}")
        }
    }
}

class ExpandedUploadWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : Worker(appContext, workerParams) {

    override fun doWork(): Result {
        val sessionId = inputData.getString(INPUT_SESSION_ID) ?: return Result.failure()
        val payload = pendingPayload(applicationContext, sessionId) ?: return Result.success()
        val endpoint = pendingEndpoint(applicationContext, sessionId)
            ?: inputData.getString(INPUT_ENDPOINT)
            ?: BuildConfig.COLLECT_ENDPOINT
        val browserTicketRequestId = try {
            JSONObject(payload).optionalText("browser_ticket_request_id")
        } catch (_: Exception) {
            null
        }
        val attempt = ExpandedUploadTransport.upload(payload, endpoint)

        return when {
            attempt.uploaded -> {
                if (attempt.receipt != null && browserTicketRequestId != null) {
                    persistBrowserHandoffIfUnhandled(
                        applicationContext,
                        PendingBrowserHandoff(
                            attempt.receipt,
                            endpoint,
                            browserTicketRequestId
                        )
                    )
                }
                Log.i(
                    "HG-ExpandedUpload",
                    "background_receipt_verified session=$sessionId; " +
                        "receipt=${attempt.receipt?.receiptId}; " +
                        "browser_request=${browserTicketRequestId ?: "missing"}; " +
                        "browser_handoff=persisted_only_if_unhandled"
                )
                clearPending(applicationContext, sessionId)
                Result.success()
            }
            attempt.retryable && runAttemptCount < MAX_BACKGROUND_ATTEMPTS -> Result.retry()
            else -> Result.failure()
        }
    }

    companion object {
        private const val PREFS_NAME = "expanded_pending_uploads"
        private const val INPUT_SESSION_ID = "session_id"
        private const val INPUT_ENDPOINT = "endpoint"
        private const val ENDPOINT_SUFFIX = ":endpoint"
        private const val BROWSER_HANDOFF_SUFFIX = ":browser_handoff"
        private const val BROWSER_TICKET_HANDLED_SUFFIX = ":browser_ticket_handled"
        private const val WORK_PREFIX = "expanded-upload-"
        private const val MAX_BACKGROUND_ATTEMPTS = 5
        private val browserHandoffLock = Any()

        fun persistAndEnqueue(
            context: Context,
            sessionId: String,
            payloadJson: String,
            endpoint: String
        ): Boolean {
            val persisted = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(sessionId, payloadJson)
                .putString(sessionId + ENDPOINT_SUFFIX, ExpandedUploadTransport.resolveEndpoint(endpoint))
                .commit()
            check(persisted) { "Unable to persist expanded payload before upload scheduling" }

            try {
                val constraints = Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
                val request = OneTimeWorkRequestBuilder<ExpandedUploadWorker>()
                    .setInputData(
                        androidx.work.workDataOf(
                            INPUT_SESSION_ID to sessionId,
                            INPUT_ENDPOINT to ExpandedUploadTransport.resolveEndpoint(endpoint)
                        )
                    )
                    .setConstraints(constraints)
                    .setInitialDelay(10, TimeUnit.SECONDS)
                    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
                    .build()

                WorkManager.getInstance(context).enqueueUniqueWork(
                    workName(sessionId),
                    ExistingWorkPolicy.KEEP,
                    request
                )
            } catch (error: Exception) {
                Log.w(
                    "HG-ExpandedUpload",
                    "Payload persisted but background scheduling failed for session=$sessionId",
                    error
                )
            }
            return true
        }

        fun markUploaded(context: Context, sessionId: String) {
            clearPending(context, sessionId)
            WorkManager.getInstance(context).cancelUniqueWork(workName(sessionId))
        }

        fun markBrowserTicketHandled(
            context: Context,
            sessionId: String,
            browserTicketRequestId: String,
            pairId: String
        ): Boolean = synchronized(browserHandoffLock) {
            val marker = JSONObject().apply {
                put("browser_ticket_request_id", browserTicketRequestId)
                put("pair_id", pairId)
            }.toString()
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(sessionId + BROWSER_TICKET_HANDLED_SUFFIX, marker)
                .remove(sessionId + BROWSER_HANDOFF_SUFFIX)
                .commit()
        }

        internal fun matchesBrowserTicketHandledMarker(
            serializedMarker: String?,
            browserTicketRequestId: String
        ): Boolean {
            return try {
                serializedMarker != null &&
                    JSONObject(serializedMarker)
                        .requiredText("browser_ticket_request_id") == browserTicketRequestId
            } catch (_: Exception) {
                false
            }
        }

        internal fun peekPendingBrowserHandoff(
            context: Context
        ): PendingBrowserHandoffClaim? {
            val preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            return selectPendingBrowserHandoff(preferences.all)
        }

        internal fun acknowledgePendingBrowserHandoff(
            context: Context,
            claim: PendingBrowserHandoffClaim
        ): Boolean {
            val preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val currentValue = preferences.getString(claim.storageKey, null)
            if (!matchesPendingBrowserHandoffClaim(currentValue, claim)) {
                return false
            }
            return preferences.edit().remove(claim.storageKey).commit()
        }

        /**
         * Finds a valid handoff independently of the newly-created Activity
         * session id. The receipt binding inside the serialized record remains
         * authoritative, and the preference key must agree with that binding.
         */
        internal fun selectPendingBrowserHandoff(
            entries: Map<String, *>
        ): PendingBrowserHandoffClaim? {
            return entries.entries
                .asSequence()
                .filter { (key, value) ->
                    key.endsWith(BROWSER_HANDOFF_SUFFIX) && value is String
                }
                .sortedBy { it.key }
                .mapNotNull { (key, value) ->
                    val serialized = value as? String ?: return@mapNotNull null
                    val handoff = PendingBrowserHandoff.fromJson(serialized)
                        ?: return@mapNotNull null
                    val expectedKey = handoff.receipt.sessionId + BROWSER_HANDOFF_SUFFIX
                    if (key != expectedKey) {
                        return@mapNotNull null
                    }
                    PendingBrowserHandoffClaim(
                        storageKey = key,
                        serializedValue = serialized,
                        handoff = handoff
                    )
                }
                .firstOrNull()
        }

        internal fun matchesPendingBrowserHandoffClaim(
            currentValue: String?,
            claim: PendingBrowserHandoffClaim
        ): Boolean {
            return currentValue != null && currentValue == claim.serializedValue
        }

        private fun pendingPayload(context: Context, sessionId: String): String? {
            return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(sessionId, null)
        }

        private fun pendingEndpoint(context: Context, sessionId: String): String? {
            return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(sessionId + ENDPOINT_SUFFIX, null)
        }

        private fun clearPending(context: Context, sessionId: String) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .remove(sessionId)
                .remove(sessionId + ENDPOINT_SUFFIX)
                .apply()
        }

        private fun persistBrowserHandoffIfUnhandled(
            context: Context,
            handoff: PendingBrowserHandoff
        ): Boolean = synchronized(browserHandoffLock) {
            val preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val handledMarker = preferences.getString(
                handoff.receipt.sessionId + BROWSER_TICKET_HANDLED_SUFFIX,
                null
            )
            if (
                matchesBrowserTicketHandledMarker(
                    handledMarker,
                    handoff.browserTicketRequestId
                )
            ) {
                return@synchronized false
            }
            preferences
                .edit()
                .putString(
                    handoff.receipt.sessionId + BROWSER_HANDOFF_SUFFIX,
                    handoff.toJson().toString()
                )
                .commit()
        }

        private fun workName(sessionId: String): String = WORK_PREFIX + sessionId
    }
}
