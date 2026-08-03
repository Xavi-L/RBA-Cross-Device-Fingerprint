package com.example.hybridguard.featureapp

import android.annotation.SuppressLint
import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import androidx.core.content.edit
import java.util.concurrent.TimeUnit

/**
 * Polling is deliberately independent of any browser callback. Once the ticket
 * is persisted, WorkManager can observe the pair even while the browser owns
 * the foreground or the collector process is recreated.
 */
internal class BrowserPairPollWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : Worker(appContext, workerParams) {

    override fun doWork(): Result {
        val pairId = inputData.getString(INPUT_PAIR_ID) ?: return Result.failure()
        val state = loadState(applicationContext, pairId) ?: return Result.failure()
        Log.i(
            TAG,
            "poll_attempt pair_id=$pairId; session=${state.appSessionId}; attempt=$runAttemptCount"
        )

        return when (val poll = BrowserPairTransport.poll(state)) {
            is BrowserPairTransport.PollResult.Received -> {
                persistStatus(applicationContext, pairId, poll.result.pairStatus, poll.result.detail)
                if (poll.result.terminal) {
                    Log.i(
                        TAG,
                        "poll_terminal pair_id=$pairId; session=${state.appSessionId}; " +
                            "pair_status=${poll.result.pairStatus}"
                    )
                    Result.success()
                } else if (runAttemptCount < MAX_POLL_ATTEMPTS) {
                    Log.i(
                        TAG,
                        "poll_pending pair_id=$pairId; pair_status=${poll.result.pairStatus}"
                    )
                    Result.retry()
                } else {
                    persistStatus(
                        applicationContext,
                        pairId,
                        STATUS_POLL_EXHAUSTED,
                        "Pair remained pending after $MAX_POLL_ATTEMPTS WorkManager attempts."
                    )
                    Log.w(TAG, "poll_exhausted pair_id=$pairId")
                    Result.failure()
                }
            }
            is BrowserPairTransport.PollResult.Failed -> {
                Log.w(
                    TAG,
                    "poll_failed pair_id=$pairId; retryable=${poll.retryable}; detail=${poll.detail}"
                )
                if (poll.retryable && runAttemptCount < MAX_POLL_ATTEMPTS) {
                    Result.retry()
                } else {
                    persistStatus(
                        applicationContext,
                        pairId,
                        STATUS_POLL_FAILED,
                        poll.detail
                    )
                    Result.failure()
                }
            }
        }
    }

    companion object {
        private const val TAG = "HG-BrowserPoll"
        private const val PREFS_NAME = "browser_pair_poll_state"
        private const val INPUT_PAIR_ID = "pair_id"
        private const val STATE_SUFFIX = ":state"
        private const val STATUS_SUFFIX = ":status"
        private const val DETAIL_SUFFIX = ":detail"
        private const val WORK_PREFIX = "browser-pair-poll-"
        private const val MAX_POLL_ATTEMPTS = 18
        private const val STATUS_POLL_EXHAUSTED = "poll_retry_exhausted"
        private const val STATUS_POLL_FAILED = "poll_failed"

        @SuppressLint("ApplySharedPref")
        fun persistAndEnqueue(context: Context, state: BrowserPairPollState) {
            val preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val persisted = preferences.edit()
                .putString(state.pairId + STATE_SUFFIX, state.toJson().toString())
                .putString(state.pairId + STATUS_SUFFIX, "ticket_issued")
                .putString(
                    state.pairId + DETAIL_SUFFIX,
                    "Ticket persisted; browser callback is not required."
                )
                .commit()
            check(persisted) { "Unable to persist browser pair poll token" }

            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = OneTimeWorkRequestBuilder<BrowserPairPollWorker>()
                .setInputData(workDataOf(INPUT_PAIR_ID to state.pairId))
                .setConstraints(constraints)
                .setInitialDelay(2, TimeUnit.SECONDS)
                .setBackoffCriteria(BackoffPolicy.LINEAR, 10, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_PREFIX + state.pairId,
                ExistingWorkPolicy.KEEP,
                request
            )
            Log.i(
                TAG,
                "poll_enqueued pair_id=${state.pairId}; session=${state.appSessionId}; " +
                    "ticket_expires_at=${state.expiresAt}"
            )
        }

        private fun loadState(context: Context, pairId: String): BrowserPairPollState? {
            val value = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(pairId + STATE_SUFFIX, null)
                ?: return null
            return BrowserPairPollState.fromJson(value)
        }

        private fun persistStatus(
            context: Context,
            pairId: String,
            status: String,
            detail: String
        ) {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit {
                putString(pairId + STATUS_SUFFIX, status)
                putString(pairId + DETAIL_SUFFIX, detail)
            }
        }
    }
}
