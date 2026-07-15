package com.example.hybridguard.featureapp

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import org.json.JSONObject

class MainActivity : AppCompatActivity(), ExpandedWebBridge.Listener {

    private val sessionId = UUID.randomUUID().toString()
    private val payloadAccepted = AtomicBoolean(false)
    private val mainHandler = Handler(Looper.getMainLooper())
    private val nativeLayerFailures = mutableMapOf<String, String>()
    private lateinit var collector: ExpandedFingerprintCollector
    private lateinit var nativeDataLayered: JSONObject
    private lateinit var collectionManifest: JSONObject
    private lateinit var fieldStatusReporter: FieldStatusReporter
    private lateinit var sessionText: TextView
    private lateinit var uploadText: TextView
    private lateinit var statusText: TextView
    private lateinit var webView: WebView
    private lateinit var collectEndpoint: String
    private val webProbeTimeout = Runnable {
        acceptAndUpload(
            webPayload = JSONObject(),
            extraLayerFailures = mapOf(
                "webview_data" to "timeout",
                "web_data" to "timeout"
            ),
            fallbackReason = "web_probe_timeout"
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sessionText = findViewById(R.id.sessionText)
        uploadText = findViewById(R.id.uploadText)
        statusText = findViewById(R.id.statusText)
        sessionText.text = "Session: $sessionId"

        collector = ExpandedFingerprintCollector(this)
        collectEndpoint = ExpandedUploadTransport.resolveEndpoint(
            intent.getStringExtra(ExpandedUploadTransport.EXTRA_COLLECT_ENDPOINT)
        )
        collectionManifest = try {
            CollectionManifestBuilder(this).build(
                runtimeContext = intent.getStringExtra(CollectionManifestBuilder.EXTRA_RUNTIME_CONTEXT).orEmpty(),
                collectionRound = intent.getIntExtra(CollectionManifestBuilder.EXTRA_COLLECTION_ROUND, 1),
                deviceManifestIdOverride = intent.getStringExtra(
                    CollectionManifestBuilder.EXTRA_DEVICE_MANIFEST_ID
                )
            ).apply {
                put("upload_endpoint_origin", ExpandedUploadTransport.endpointOrigin(collectEndpoint))
            }
        } catch (e: Exception) {
            JSONObject().apply {
                put("manifest_schema_version", CollectionManifestBuilder.MANIFEST_SCHEMA_VERSION)
                put("collection_protocol_version", CollectionManifestBuilder.COLLECTION_PROTOCOL_VERSION)
                put("device_manifest_id", "manifest-error-$sessionId")
                put("runtime_context", "unspecified")
                put("collection_round", 1)
                put("android_api", android.os.Build.VERSION.SDK_INT)
                put("schema_version", CollectionManifestBuilder.FEATURE_SCHEMA_VERSION)
                put("manifest_build_status", "runtime_error")
                put("manifest_build_error", e.javaClass.simpleName)
                put("upload_endpoint_origin", ExpandedUploadTransport.endpointOrigin(collectEndpoint))
            }
        }
        fieldStatusReporter = FieldStatusReporter(this)
        nativeDataLayered = try {
            collector.collectNativeLayered()
        } catch (e: Exception) {
            nativeLayerFailures["android_native_data"] = "runtime_error"
            JSONObject().apply {
                put("collector_error", e.javaClass.simpleName)
            }
        }
        statusText.text = if (nativeLayerFailures.isEmpty()) {
            "Expanded Native layer collected. Waiting for WebView and Web signals."
        } else {
            "Native collection degraded. Waiting for Web signals; partial data will still upload."
        }

        webView = findViewById(R.id.webview)
        configureWebView(webView)
        mainHandler.postDelayed(webProbeTimeout, WEB_PROBE_DEADLINE_MS)
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
        try {
            acceptAndUpload(JSONObject(payloadJson), emptyMap(), "none")
        } catch (_: Exception) {
            acceptAndUpload(
                JSONObject(),
                mapOf("webview_data" to "runtime_error", "web_data" to "runtime_error"),
                "web_payload_parse_error"
            )
        }
    }

    private fun acceptAndUpload(
        webPayload: JSONObject,
        extraLayerFailures: Map<String, String>,
        fallbackReason: String
    ) {
        if (!payloadAccepted.compareAndSet(false, true)) {
            return
        }
        mainHandler.removeCallbacks(webProbeTimeout)

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
            val webviewData = webPayload.optJSONObject("webview_data") ?: JSONObject()
            val webData = webPayload.optJSONObject("web_data") ?: JSONObject()
            val layerFailures = linkedMapOf<String, String>().apply {
                putAll(nativeLayerFailures)
                putAll(extraLayerFailures)
                if (webviewData.length() == 0 && !containsKey("webview_data")) {
                    put("webview_data", "runtime_error")
                }
                if (webData.length() == 0 && !containsKey("web_data")) {
                    put("web_data", "runtime_error")
                }
            }
            val probeStatuses = webPayload
                .optJSONObject("collection_diagnostics")
                ?.optJSONObject("probe_statuses")
                ?: JSONObject()
            val featurePayload = JSONObject().apply {
                put("session_id", sessionId)
                put("timestamp", System.currentTimeMillis() / 1000)
                put("collector_app", "featureapp")
                put("schema_version", CollectionManifestBuilder.FEATURE_SCHEMA_VERSION)
                put("android_native_data", nativeDataLayered)
                put("webview_data", webviewData)
                put("web_data", webData)
                put("collection_manifest", collectionManifest)
                put(
                    "collection_diagnostics",
                    JSONObject().apply {
                        put("diagnostics_schema_version", "collection-diagnostics-v1")
                        put("fallback_reason", fallbackReason)
                        put("probe_statuses", probeStatuses)
                        put("collection_finished_at_ms", System.currentTimeMillis())
                    }
                )
            }
            val collectionStatus = fieldStatusReporter.build(
                featurePayload,
                layerFailures,
                probeStatuses
            )
            featurePayload.put("collection_status", collectionStatus)
            val fixedSignalCount = collectionStatus.optInt("fixed_signal_count")
            val observedSignalCount = collectionStatus
                .optJSONObject("counts")
                ?.optInt("observed")
                ?: 0
            val serializedPayload = featurePayload.toString()

            try {
                ExpandedUploadWorker.persistAndEnqueue(
                    applicationContext,
                    sessionId,
                    serializedPayload,
                    collectEndpoint
                )
            } catch (_: Exception) {
                // The immediate upload below remains available even if background scheduling fails.
            }

            thread {
                val uploadStatus = uploadExpandedFeatures(
                    serializedPayload,
                    collectEndpoint,
                    observedSignalCount,
                    fixedSignalCount
                )
                runOnUiThread {
                    uploadText.text = if (uploadStatus.uploaded) "Uploaded" else "Upload failed"
                    statusText.text = uploadStatus.message
                    updateProbeUi(
                        uploadStatus.message,
                        "Field status: $observedSignalCount/$fixedSignalCount observed",
                        if (uploadStatus.uploaded) "good" else "bad"
                    )
                }
            }
        } catch (e: Exception) {
            val emergencyPayload = JSONObject().apply {
                put("session_id", sessionId)
                put("timestamp", System.currentTimeMillis() / 1000)
                put("collector_app", "featureapp")
                put("schema_version", CollectionManifestBuilder.FEATURE_SCHEMA_VERSION)
                put("android_native_data", nativeDataLayered)
                put("webview_data", JSONObject())
                put("web_data", JSONObject())
                put("collection_manifest", collectionManifest)
                put(
                    "collection_diagnostics",
                    JSONObject().apply {
                        put("diagnostics_schema_version", "collection-diagnostics-v1")
                        put("fallback_reason", "android_payload_assembly_error")
                        put("assembly_error", e.javaClass.simpleName)
                        put("collection_finished_at_ms", System.currentTimeMillis())
                    }
                )
            }.toString()
            try {
                ExpandedUploadWorker.persistAndEnqueue(
                    applicationContext,
                    sessionId,
                    emergencyPayload,
                    collectEndpoint
                )
                thread {
                    val emergencyStatus = uploadExpandedFeatures(
                        emergencyPayload,
                        collectEndpoint,
                        0,
                        FieldStatusReporter.FIXED_SIGNAL_COUNT
                    )
                    if (emergencyStatus.uploaded) {
                        runOnUiThread {
                            uploadText.text = "Uploaded partial"
                            statusText.text = "Emergency partial payload uploaded with validation warnings."
                        }
                    }
                }
            } catch (_: Exception) {
                // Keep the original UI error below; no further in-process fallback remains.
            }
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

    private fun uploadExpandedFeatures(
        payloadJson: String,
        endpoint: String,
        observedSignalCount: Int,
        fixedSignalCount: Int
    ): UploadStatus {
        var lastAttempt = ExpandedUploadTransport.Attempt(
            uploaded = false,
            retryable = true,
            detail = "not attempted"
        )
        for (attemptNumber in 1..IMMEDIATE_UPLOAD_ATTEMPTS) {
            lastAttempt = ExpandedUploadTransport.upload(payloadJson, endpoint)
            if (lastAttempt.uploaded) {
                ExpandedUploadWorker.markUploaded(applicationContext, sessionId)
                return UploadStatus(
                    true,
                    "Expanded payload uploaded. Field status: " +
                        "$observedSignalCount/$fixedSignalCount observed."
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

    private data class UploadStatus(val uploaded: Boolean, val message: String)

    companion object {
        private const val WEB_PROBE_DEADLINE_MS = 15_000L
        private const val IMMEDIATE_UPLOAD_ATTEMPTS = 3
        private val IMMEDIATE_RETRY_DELAYS_MS = longArrayOf(250, 750)
    }
}
