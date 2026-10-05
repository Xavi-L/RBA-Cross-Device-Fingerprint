package com.example.hybridguard.featureapp

/** Lifecycle policy is independent of Android and of all Host/Web comparison values. */
internal class GeometrySamplingPolicy {
    var generation: Long = 0
        private set
    var destroyed = false
        private set
    private var accepted = false
    private var completed = false

    fun navigate(): Long { generation += 1; return generation }
    fun acceptPayload(): Boolean {
        if (accepted || destroyed) return false
        accepted = true
        return true
    }
    fun callbackIsCurrent(expectedGeneration: Long): Boolean =
        !destroyed && !completed && generation == expectedGeneration
    fun finishOnce(): Boolean {
        if (completed) return false
        completed = true
        return true
    }
    fun destroy() { destroyed = true; generation += 1 }

    companion object {
        const val MAX_ATTEMPTS = 2
        const val QUIET_MS = 250L
        const val ATTEMPT_TIMEOUT_MS = 1_800L
        const val TOTAL_TIMEOUT_MS = 5_000L
        fun hostStable(
            beforeSequence: String, afterSequence: String,
            beforeGeometry: String, afterGeometry: String,
            beforeElapsed: Long, afterElapsed: Long
        ): Boolean = beforeSequence == afterSequence &&
            beforeGeometry == afterGeometry && afterElapsed >= beforeElapsed &&
            afterElapsed - beforeElapsed <= ATTEMPT_TIMEOUT_MS
    }
}

internal object GeometryExperimentControl {
    const val EXTRA_HIDE_HEADER = "com.example.hybridguard.featureapp.GEOMETRY_HIDE_HEADER"
    const val EXTRA_ENABLE_ZOOM = "com.example.hybridguard.featureapp.GEOMETRY_ENABLE_ZOOM"
    const val EXTRA_ZOOM_FACTOR = "com.example.hybridguard.featureapp.GEOMETRY_ZOOM_FACTOR"
    const val SETTLE_MS = 400L
    // This local experiment has one fixed magnification; arbitrary values are rejected.
    fun validZoom(factor: Float): Boolean = factor == 1f || factor == 1.25f
}

internal object GeometrySnapshotBinding {
    fun matches(
        web: org.json.JSONObject?, expectedDocumentId: String?, sessionId: String,
        instanceId: String, generation: Long, observationId: String, attemptId: Int
    ): Boolean {
        if (expectedDocumentId.isNullOrBlank() || web == null) return false
        val binding = web.optJSONObject("binding") ?: return false
        return web.optString("document_id") == expectedDocumentId &&
            binding.optString("session_id") == sessionId &&
            binding.optString("webview_instance_id") == instanceId &&
            binding.optLong("document_generation", -1L) == generation &&
            binding.optString("observation_id") == observationId &&
            binding.optInt("attempt_id", -1) == attemptId
    }
}

/** The guard is inside each async callback, not merely around evaluateJavascript dispatch. */
internal object GeometryReadBoundary {
    fun <T : Any> readIfCurrent(
        isCurrent: () -> Boolean,
        stage: String,
        read: () -> T,
        onFailure: (String) -> Unit
    ): T? {
        if (!isCurrent()) return null
        return try { read() }
        catch (error: Exception) {
            onFailure("${stage}_${error.javaClass.simpleName}")
            null
        }
    }
}
