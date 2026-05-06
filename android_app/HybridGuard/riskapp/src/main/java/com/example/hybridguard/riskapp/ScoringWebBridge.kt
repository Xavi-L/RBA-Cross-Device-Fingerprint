package com.example.hybridguard.riskapp

import android.webkit.JavascriptInterface
import java.security.MessageDigest

class ScoringWebBridge(
    private val collector: FingerprintCollector,
    private val sessionId: String,
    private val listener: Listener
) {
    interface Listener {
        fun onWebPayload(payloadJson: String)
    }

    @JavascriptInterface
    fun getSessionId(): String = sessionId

    @JavascriptInterface
    fun getWebViewSecurityFeatures(): String {
        return collector.collectWebViewSecurityFlat().toString()
    }

    @JavascriptInterface
    fun sha256(value: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return digest.joinToString(separator = "") { "%02x".format(it.toInt() and 0xff) }
    }

    @JavascriptInterface
    fun submitWebPayload(payloadJson: String) {
        listener.onWebPayload(payloadJson)
    }
}
