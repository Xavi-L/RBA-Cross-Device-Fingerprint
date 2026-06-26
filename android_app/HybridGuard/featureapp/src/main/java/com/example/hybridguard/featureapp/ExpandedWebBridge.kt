package com.example.hybridguard.featureapp

import android.webkit.JavascriptInterface
import java.security.MessageDigest
import org.json.JSONObject

class ExpandedWebBridge(
    private val collector: ExpandedFingerprintCollector,
    private val sessionId: String,
    private val webViewSettings: JSONObject,
    private val listener: Listener
) {
    interface Listener {
        fun onExpandedPayload(payloadJson: String)
    }

    @JavascriptInterface
    fun getSessionId(): String = sessionId

    @JavascriptInterface
    fun getWebViewHostFeatures(): String {
        return collector.collectWebViewHostFlat(webViewSettings).toString()
    }

    @JavascriptInterface
    fun sha256(value: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return digest.joinToString(separator = "") { "%02x".format(it.toInt() and 0xff) }
    }

    @JavascriptInterface
    fun submitExpandedPayload(payloadJson: String) {
        listener.onExpandedPayload(payloadJson)
    }
}

