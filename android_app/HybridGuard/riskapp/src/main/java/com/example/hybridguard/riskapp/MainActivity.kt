package com.example.hybridguard.riskapp

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale
import java.util.UUID
import kotlin.concurrent.thread
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class MainActivity : AppCompatActivity(), ScoringWebBridge.Listener {

    private val sessionId = UUID.randomUUID().toString()
    private val httpClient = OkHttpClient()
    private lateinit var collector: FingerprintCollector
    private lateinit var nativeDataFlat: JSONObject
    private lateinit var sessionText: TextView
    private lateinit var scoreText: TextView
    private lateinit var statusText: TextView
    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sessionText = findViewById(R.id.sessionText)
        scoreText = findViewById(R.id.scoreText)
        statusText = findViewById(R.id.statusText)
        sessionText.text = "Session: $sessionId"

        collector = FingerprintCollector(this)
        nativeDataFlat = collector.collectNativeFlat()
        statusText.text = "Native layer collected. Waiting for WebView and Web signals."

        webView = findViewById(R.id.webview)
        configureWebView(webView)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView(webView: WebView) {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()
        webView.addJavascriptInterface(
            ScoringWebBridge(collector, sessionId, this),
            "AndroidBridge"
        )
        webView.loadUrl("file:///android_asset/local_probe.html")
    }

    override fun onWebPayload(payloadJson: String) {
        runOnUiThread {
            statusText.text = "All three layers collected. Running local RandomForest scorer."
            updateProbeUi(
                "Running local RandomForest scorer...",
                "Three-layer fingerprint is complete. Scoring stays on device.",
                "good"
            )
        }

        thread {
            try {
                val webPayload = JSONObject(payloadJson)
                val scoringSession = JSONObject().apply {
                    put("session_id", sessionId)
                    put("timestamp", System.currentTimeMillis() / 1000)
                    put("android_native_data", nativeDataFlat)
                    put(
                        "webview_data",
                        FingerprintCollector.flattenLayers(webPayload.optJSONObject("webview_data"))
                    )
                    put(
                        "web_data",
                        FingerprintCollector.flattenLayers(webPayload.optJSONObject("web_data"))
                    )
                }

                val features = RiskFeatureEncoder.encode(scoringSession)
                val score = DeviceRiskScorer.score(features).coerceIn(0.0, 100.0)
                val level = riskLevel(score)
                val reason = "Local random forest score from ${features.size} encoded cross-layer features."

                runOnUiThread {
                    scoreText.text = "Score ${String.format(Locale.US, "%.1f", score)} / 100"
                    statusText.text = "Local score ready. Uploading score result only."
                    updateProbeUi(
                        "Local score ${String.format(Locale.US, "%.1f", score)} / 100 (${level.uppercase(Locale.US)})",
                        "Only the score result is being uploaded to the server.",
                        "good"
                    )
                }

                val uploadStatus = uploadScore(score, level, reason, features.size)
                runOnUiThread {
                    statusText.text = uploadStatus
                    updateProbeUi(
                        uploadStatus,
                        "Final score sent. Raw device signals stayed on this phone.",
                        if (uploadStatus.contains("uploaded")) "good" else "bad"
                    )
                }
            } catch (e: Exception) {
                runOnUiThread {
                    scoreText.text = "Score failed"
                    statusText.text = e.message ?: "Local scoring failed"
                    updateProbeUi(
                        "Local scoring failed",
                        e.message ?: "Android scorer did not produce a result.",
                        "bad"
                    )
                }
            }
        }
    }

    private fun uploadScore(score: Double, level: String, reason: String, featureCount: Int): String {
        val payload = JSONObject().apply {
            put("session_id", sessionId)
            put("timestamp", System.currentTimeMillis() / 1000)
            put("risk_score", score)
            put("risk_level", level)
            put("risk_reason", reason)
            put("scoring_engine", "random_forest_m2cgen")
            put("feature_count", featureCount)
        }

        val body = payload
            .toString()
            .toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(SCORE_ENDPOINT)
            .addHeader("ngrok-skip-browser-warning", "true")
            .post(body)
            .build()

        return try {
            httpClient.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    "Score uploaded to server. Risk level: $level."
                } else {
                    "Local score ready, but upload failed with HTTP ${response.code}."
                }
            }
        } catch (e: Exception) {
            "Local score ready, but upload failed: ${e.message}"
        }
    }

    private fun riskLevel(score: Double): String {
        return when {
            score >= 80.0 -> "high"
            score >= 50.0 -> "medium"
            else -> "low"
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

    companion object {
        private const val SCORE_ENDPOINT =
            "https://hemispheric-overmoist-candance.ngrok-free.dev/api/risk/local-score"
    }
}
