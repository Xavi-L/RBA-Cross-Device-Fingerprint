package com.example.hybridguard.featureapp

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.UUID
import kotlin.concurrent.thread
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : AppCompatActivity(), ExpandedWebBridge.Listener {

    private val sessionId = UUID.randomUUID().toString()
    private val httpClient = OkHttpClient()
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
        runOnUiThread {
            uploadText.text = "Uploading"
            statusText.text = "Expanded three-layer payload collected. Uploading raw features."
            updateProbeUi(
                "Uploading expanded feature payload...",
                "This collector uploads raw expanded features for offline experiments.",
                "good"
            )
        }

        thread {
            try {
                val webPayload = JSONObject(payloadJson)
                val featurePayload = JSONObject().apply {
                    put("session_id", sessionId)
                    put("timestamp", System.currentTimeMillis() / 1000)
                    put("collector_app", "featureapp")
                    put("schema_version", "expanded-v1")
                    put("android_native_data", nativeDataLayered)
                    put("webview_data", webPayload.optJSONObject("webview_data") ?: JSONObject())
                    put("web_data", webPayload.optJSONObject("web_data") ?: JSONObject())
                }

                val featureCount = countLeafValues(featurePayload.optJSONObject("android_native_data")) +
                    countLeafValues(featurePayload.optJSONObject("webview_data")) +
                    countLeafValues(featurePayload.optJSONObject("web_data"))

                val uploadStatus = uploadExpandedFeatures(featurePayload, featureCount)
                runOnUiThread {
                    uploadText.text = if (uploadStatus.uploaded) "Uploaded" else "Upload failed"
                    statusText.text = uploadStatus.message
                    updateProbeUi(
                        uploadStatus.message,
                        "Expanded feature count: $featureCount",
                        if (uploadStatus.uploaded) "good" else "bad"
                    )
                }
            } catch (e: Exception) {
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
    }

    private fun uploadExpandedFeatures(payload: JSONObject, featureCount: Int): UploadStatus {
        val body = payload
            .toString()
            .toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(COLLECT_ENDPOINT)
            .addHeader("ngrok-skip-browser-warning", "true")
            .post(body)
            .build()

        return try {
            httpClient.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    UploadStatus(true, "Expanded payload uploaded. Feature count: $featureCount.")
                } else {
                    UploadStatus(false, "Upload failed with HTTP ${response.code}.")
                }
            }
        } catch (e: Exception) {
            UploadStatus(false, "Upload failed: ${e.message}")
        }
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
        private const val COLLECT_ENDPOINT =
            "http://10.0.2.2:8000/api/collect/fingerprint"
    }
}
