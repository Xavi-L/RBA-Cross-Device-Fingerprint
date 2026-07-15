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
        val detail: String
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
                        val expectedSessionId = JSONObject(payloadJson).optString("session_id")
                        val responseJson = try {
                            JSONObject(responseText)
                        } catch (_: Exception) {
                            null
                        }
                        val receipt = responseJson?.optJSONObject("receipt")
                        val receiptValid =
                            responseJson != null &&
                                responseJson.optString("status") == "success" &&
                                responseJson.optString("session_id") == expectedSessionId &&
                                !receipt?.optString("receipt_id").isNullOrBlank() &&
                                !receipt?.optString("payload_sha256").isNullOrBlank()
                        if (receiptValid) {
                            val warningCount = receipt?.optJSONArray("validation_warnings")?.length() ?: 0
                            Attempt(
                                true,
                                false,
                                "HTTP ${response.code}; receipt=${receipt?.optString("receipt_id")}; warnings=$warningCount"
                            )
                        } else {
                            Attempt(false, true, "HTTP ${response.code}; collection receipt missing or invalid")
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
        val attempt = ExpandedUploadTransport.upload(payload, endpoint)

        return when {
            attempt.uploaded -> {
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
        private const val WORK_PREFIX = "expanded-upload-"
        private const val MAX_BACKGROUND_ATTEMPTS = 5

        fun persistAndEnqueue(
            context: Context,
            sessionId: String,
            payloadJson: String,
            endpoint: String
        ) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(sessionId, payloadJson)
                .putString(sessionId + ENDPOINT_SUFFIX, ExpandedUploadTransport.resolveEndpoint(endpoint))
                .commit()

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
        }

        fun markUploaded(context: Context, sessionId: String) {
            clearPending(context, sessionId)
            WorkManager.getInstance(context).cancelUniqueWork(workName(sessionId))
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

        private fun workName(sessionId: String): String = WORK_PREFIX + sessionId
    }
}
