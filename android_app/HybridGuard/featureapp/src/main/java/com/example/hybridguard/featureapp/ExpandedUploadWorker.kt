package com.example.hybridguard.featureapp

import android.content.Context
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

internal object ExpandedUploadTransport {
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .writeTimeout(6, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .callTimeout(8, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    data class Attempt(
        val uploaded: Boolean,
        val retryable: Boolean,
        val detail: String
    )

    fun upload(payloadJson: String): Attempt {
        val body = payloadJson.toRequestBody(JSON_MEDIA_TYPE)
        val request = Request.Builder()
            .url(COLLECT_ENDPOINT)
            .addHeader("ngrok-skip-browser-warning", "true")
            .post(body)
            .build()

        return try {
            httpClient.newCall(request).execute().use { response ->
                when {
                    response.isSuccessful -> Attempt(true, false, "HTTP ${response.code}")
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

    private const val COLLECT_ENDPOINT =
        "https://hemispheric-overmoist-candance.ngrok-free.dev/api/collect/fingerprint"
}

class ExpandedUploadWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : Worker(appContext, workerParams) {

    override fun doWork(): Result {
        val sessionId = inputData.getString(INPUT_SESSION_ID) ?: return Result.failure()
        val payload = pendingPayload(applicationContext, sessionId) ?: return Result.success()
        val attempt = ExpandedUploadTransport.upload(payload)

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
        private const val WORK_PREFIX = "expanded-upload-"
        private const val MAX_BACKGROUND_ATTEMPTS = 5

        fun persistAndEnqueue(context: Context, sessionId: String, payloadJson: String) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(sessionId, payloadJson)
                .commit()

            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = OneTimeWorkRequestBuilder<ExpandedUploadWorker>()
                .setInputData(androidx.work.workDataOf(INPUT_SESSION_ID to sessionId))
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

        private fun clearPending(context: Context, sessionId: String) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .remove(sessionId)
                .apply()
        }

        private fun workName(sessionId: String): String = WORK_PREFIX + sessionId
    }
}
