package com.example.hybridguard.featureapp

/** Opt-in controls shared with the frozen WebView collection runner. */
internal data class WebViewProbeControl private constructor(
    val debuggingEnabled: Boolean,
    val waitForControl: Boolean,
    val deadlineMs: Long
) {
    val initialUrl: String
        get() = if (waitForControl) "about:blank" else PROBE_URL

    companion object {
        const val EXTRA_ENABLE_WEBVIEW_DEBUG =
            "com.example.hybridguard.featureapp.ENABLE_WEBVIEW_DEBUG"
        const val EXTRA_WAIT_FOR_WEBVIEW_CONTROL =
            "com.example.hybridguard.featureapp.WAIT_FOR_WEBVIEW_CONTROL"
        const val EXTRA_PROBE_DELAY_MS =
            "com.example.hybridguard.featureapp.PROBE_DELAY_MS"
        const val DEFAULT_DEADLINE_MS = 15_000L
        const val MAX_DEADLINE_MS = 120_000L
        private const val PROBE_URL = "file:///android_asset/expanded_probe.html"

        fun resolve(
            debuggingEnabled: Boolean = false,
            waitForControl: Boolean = false,
            requestedDeadlineMs: Long = DEFAULT_DEADLINE_MS
        ): WebViewProbeControl = WebViewProbeControl(
            debuggingEnabled = debuggingEnabled,
            waitForControl = waitForControl,
            deadlineMs = requestedDeadlineMs.coerceIn(DEFAULT_DEADLINE_MS, MAX_DEADLINE_MS)
        )
    }
}
