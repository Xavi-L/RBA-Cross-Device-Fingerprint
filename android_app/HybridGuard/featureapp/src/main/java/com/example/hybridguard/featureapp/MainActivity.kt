package com.example.hybridguard.featureapp

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : AppCompatActivity(), ExpandedWebBridge.Listener {

    private val sessionId = UUID.randomUUID().toString()
    private val payloadAccepted = AtomicBoolean(false)
    private lateinit var collector: ExpandedFingerprintCollector
    private lateinit var nativeDataLayered: JSONObject
    private lateinit var sessionText: TextView
    private lateinit var uploadText: TextView
    private lateinit var statusText: TextView
    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sessionText = findViewById(R.id.sessionText)
        uploadText = findViewById(R.id.uploadText)
        statusText = findViewById(R.id.statusText)
        sessionText.text = "Session: $sessionId"

        collector = ExpandedFingerprintCollector(this)
        nativeDataLayered = collector.collectNativeLayered()
        statusText.text = "Expanded Native layer collected. Waiting for WebView and Web signals."

        webView = findViewById(R.id.webview)
        configureWebView(webView)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView(webView: WebView) {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()

        val settingsSnapshot = ExpandedFingerprintCollector.webViewSettingsSnapshot(webView)
        webView.addJavascriptInterface(
            ExpandedWebBridge(collector, sessionId, settingsSnapshot, this),
            "AndroidBridge"
        )
        webView.loadUrl("file:///android_asset/expanded_probe.html")
    }

    override fun onExpandedPayload(payloadJson: String) {
        if (!payloadAccepted.compareAndSet(false, true)) {
            return
        }

        runOnUiThread {
            uploadText.text = "Uploading"
            statusText.text = "Expanded three-layer payload collected. Uploading raw features."
            updateProbeUi(
                "Uploading expanded feature payload...",
                "This collector uploads raw expanded features for offline experiments.",
                "good"
            )
        }

        try {
            val webPayload = JSONObject(payloadJson)
            val featurePayload = JSONObject().apply {
                put("session_id", sessionId)
                put("timestamp", System.currentTimeMillis() / 1000)
                put("collector_app", "featureapp")
                put("schema_version", "expanded-v2")
                put("android_native_data", nativeDataLayered)
                put("webview_data", webPayload.optJSONObject("webview_data") ?: JSONObject())
                put("web_data", webPayload.optJSONObject("web_data") ?: JSONObject())
            }
            val featureCount = countLeafValues(featurePayload.optJSONObject("android_native_data")) +
                countLeafValues(featurePayload.optJSONObject("webview_data")) +
                countLeafValues(featurePayload.optJSONObject("web_data"))
            val serializedPayload = featurePayload.toString()

            try {
                ExpandedUploadWorker.persistAndEnqueue(
                    applicationContext,
                    sessionId,
                    serializedPayload
                )
            } catch (_: Exception) {
                // The immediate upload below remains available even if background scheduling fails.
            }

            thread {
                val uploadStatus = uploadExpandedFeatures(serializedPayload, featureCount)
                runOnUiThread {
                    uploadText.text = if (uploadStatus.uploaded) "Uploaded" else "Upload failed"
                    statusText.text = uploadStatus.message
                    updateProbeUi(
                        uploadStatus.message,
                        "Expanded feature count: $featureCount",
                        if (uploadStatus.uploaded) "good" else "bad"
                    )
                }
            }
        } catch (e: Exception) {
            payloadAccepted.set(false)
            runOnUiThread {
                uploadText.text = "Upload failed"
                statusText.text = e.message ?: "Expanded collection failed"
                updateProbeUi(
                    "Expanded collection failed",
                    e.message ?: "Collector did not produce a payload.",
                    "bad"
                )
            }
        }
    }

    private fun uploadExpandedFeatures(payloadJson: String, featureCount: Int): UploadStatus {
        var lastAttempt = ExpandedUploadTransport.Attempt(
            uploaded = false,
            retryable = true,
            detail = "not attempted"
        )
        for (attemptNumber in 1..IMMEDIATE_UPLOAD_ATTEMPTS) {
            lastAttempt = ExpandedUploadTransport.upload(payloadJson)
            if (lastAttempt.uploaded) {
                ExpandedUploadWorker.markUploaded(applicationContext, sessionId)
                return UploadStatus(
                    true,
                    "Expanded payload uploaded. Feature count: $featureCount."
                )
            }
            if (!lastAttempt.retryable) {
                break
            }
            if (attemptNumber < IMMEDIATE_UPLOAD_ATTEMPTS) {
                try {
                    Thread.sleep(IMMEDIATE_RETRY_DELAYS_MS[attemptNumber - 1])
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    break
                }
            }
        }

        return UploadStatus(
            false,
            "Upload deferred for background retry: ${lastAttempt.detail}."
        )
    }

    private fun updateProbeUi(status: String, detail: String, style: String) {
        val script = """
            window.HybridGuardProbe && window.HybridGuardProbe.updateResult(
                ${JSONObject.quote(status)},
                ${JSONObject.quote(detail)},
                ${JSONObject.quote(style)}
            );
        """.trimIndent()
        webView.evaluateJavascript(script, null)
    }

    private fun countLeafValues(value: Any?): Int {
        return when (value) {
            is JSONObject -> {
                var count = 0
                val keys = value.keys()
                while (keys.hasNext()) {
                    count += countLeafValues(value.opt(keys.next()))
                }
                count
            }
            is JSONArray -> value.length()
            null, JSONObject.NULL -> 0
            else -> 1
        }
    }

    private data class UploadStatus(val uploaded: Boolean, val message: String)

    companion object {
        private const val IMMEDIATE_UPLOAD_ATTEMPTS = 3
        private val IMMEDIATE_RETRY_DELAYS_MS = longArrayOf(250, 750)
    }
}
