package com.example.hybridguard.featureapp

import android.annotation.SuppressLint
import android.os.Build
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.net.InetSocketAddress
import java.net.Proxy
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : AppCompatActivity(), ExpandedWebBridge.Listener {

    private val sessionId = UUID.randomUUID().toString()
    private val httpClient by lazy { buildHttpClient() }
    private val collectEndpoint by lazy { resolveCollectEndpoint() }
    private lateinit var collector: ExpandedFingerprintCollector
    private lateinit var fieldStatusReporter: FieldStatusReporter
    private lateinit var collectionManifest: JSONObject
    private lateinit var nativeDataLayered: JSONObject
    private lateinit var sessionText: TextView
    private lateinit var uploadText: TextView
    private lateinit var statusText: TextView
    private var webView: WebView? = null
    private val payloadAccepted = AtomicBoolean(false)
    private var nativeCollectionFailure: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sessionText = findViewById(R.id.sessionText)
        uploadText = findViewById(R.id.uploadText)
        statusText = findViewById(R.id.statusText)
        sessionText.text = "Session: $sessionId"

        collector = ExpandedFingerprintCollector(this)
        fieldStatusReporter = FieldStatusReporter(this)
        collectionManifest = CollectionManifestBuilder(this).build(
            runtimeContext = intent?.getStringExtra(INTENT_EXTRA_RUNTIME_CONTEXT).orEmpty(),
            collectionRound = intent?.getIntExtra(INTENT_EXTRA_COLLECTION_ROUND, 1) ?: 1,
            deviceManifestIdOverride = intent?.getStringExtra(INTENT_EXTRA_DEVICE_MANIFEST_ID)
        )
        nativeDataLayered = try {
            collector.collectNativeLayered()
        } catch (e: SecurityException) {
            nativeCollectionFailure = "permission_denied"
            JSONObject()
        } catch (e: Exception) {
            nativeCollectionFailure = "runtime_error:${e.javaClass.simpleName}"
            JSONObject()
        }
        statusText.text = "Expanded Native layer collected. Waiting for WebView and Web signals."

        val fallbackRuntime = detectFallbackRuntime()
        if (fallbackRuntime != null) {
            statusText.text =
                "${fallbackRuntime.containerName} detected. Using fallback collector without WebView."
            uploadFallbackPayload(fallbackRuntime)
        } else {
            if (intent?.getBooleanExtra(INTENT_EXTRA_ENABLE_WEBVIEW_DEBUG, false) == true) {
                WebView.setWebContentsDebuggingEnabled(true)
            }
            val container = findViewById<FrameLayout>(R.id.webContainer)
            webView = WebView(this).also { createdWebView ->
                container.addView(
                    createdWebView,
                    FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT
                    )
                )
                configureWebView(createdWebView)
            }
            webView?.postDelayed({ uploadTimedOutPartialPayload() }, WEBVIEW_COLLECTION_TIMEOUT_MS)
        }
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
        val delayMs = intent?.getLongExtra(INTENT_EXTRA_PROBE_DELAY_MS, 0L)
            ?.coerceIn(0L, 60_000L) ?: 0L
        if (delayMs > 0L) {
            webView.loadUrl("about:blank")
            webView.postDelayed(
                { webView.loadUrl("file:///android_asset/expanded_probe.html") },
                delayMs
            )
        } else {
            webView.loadUrl("file:///android_asset/expanded_probe.html")
        }
    }

    private fun uploadFallbackPayload(runtime: FallbackRuntime) {
        if (!payloadAccepted.compareAndSet(false, true)) return
        uploadText.text = "Uploading"

        thread {
            val webViewFallback = JSONObject().apply {
                put("fallback_reason", runtime.reason)
                put("runtime_container", runtime.containerName)
                put("app_package_name", packageName)
                put("webview_provider_package", JSONObject.NULL)
                put("webview_provider_version", JSONObject.NULL)
                put("java_script_enabled", JSONObject.NULL)
                put("dom_storage_enabled", JSONObject.NULL)
                put("settings_user_agent", JSONObject.NULL)
            }
            val webFallback = JSONObject().apply {
                put("fallback_reason", runtime.reason)
                put("web_runtime_collected", false)
                put("web_runtime_blocker", runtime.blocker)
            }
            val featurePayload = JSONObject().apply {
                put("session_id", sessionId)
                put("timestamp", System.currentTimeMillis() / 1000)
                put("collector_app", "featureapp")
                put("schema_version", "expanded-v2.1-status")
                put("collection_manifest", collectionManifest)
                put("android_native_data", nativeDataLayered)
                put("webview_data", webViewFallback)
                put("web_data", webFallback)
            }
            attachCollectionStatus(
                featurePayload,
                mapOf(
                    "android_native_data" to (nativeCollectionFailure ?: "observed"),
                    "webview_data" to "runtime_error",
                    "web_data" to "not_applicable"
                )
            )

            val featureCount = countLeafValues(featurePayload.optJSONObject("android_native_data")) +
                countLeafValues(featurePayload.optJSONObject("webview_data")) +
                countLeafValues(featurePayload.optJSONObject("web_data"))
            val uploadStatus = uploadExpandedFeatures(featurePayload, featureCount)

            runOnUiThread {
                uploadText.text = if (uploadStatus.uploaded) "Uploaded" else "Upload failed"
                statusText.text = "${uploadStatus.message} Fallback reason: ${runtime.reason}."
            }
        }
    }

    override fun onExpandedPayload(payloadJson: String) {
        if (!payloadAccepted.compareAndSet(false, true)) return
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
                    put("schema_version", "expanded-v2.1-status")
                    put("collection_manifest", collectionManifest)
                    put("android_native_data", nativeDataLayered)
                    put("webview_data", webPayload.optJSONObject("webview_data") ?: JSONObject())
                    put("web_data", webPayload.optJSONObject("web_data") ?: JSONObject())
                }
                attachCollectionStatus(
                    featurePayload,
                    mapOf("android_native_data" to (nativeCollectionFailure ?: "observed"))
                )

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

    private fun uploadTimedOutPartialPayload() {
        if (!payloadAccepted.compareAndSet(false, true)) return
        statusText.text = "WebView probe timed out. Uploading partial payload with field status."
        val webViewPartial = try {
            val active = webView
            if (active == null) JSONObject() else ExpandedFingerprintCollector.webViewSettingsSnapshot(active)
        } catch (_: Exception) {
            JSONObject()
        }
        thread {
            val payload = JSONObject().apply {
                put("session_id", sessionId)
                put("timestamp", System.currentTimeMillis() / 1000)
                put("collector_app", "featureapp")
                put("schema_version", "expanded-v2.1-status")
                put("collection_manifest", collectionManifest)
                put("android_native_data", nativeDataLayered)
                put("webview_data", webViewPartial)
                put("web_data", JSONObject())
            }
            attachCollectionStatus(
                payload,
                mapOf(
                    "android_native_data" to (nativeCollectionFailure ?: "observed"),
                    "webview_data" to "timeout",
                    "web_data" to "timeout"
                )
            )
            val featureCount = countLeafValues(nativeDataLayered) + countLeafValues(webViewPartial)
            val result = uploadExpandedFeatures(payload, featureCount)
            runOnUiThread {
                uploadText.text = if (result.uploaded) "Partial uploaded" else "Upload failed"
                statusText.text = result.message
            }
        }
    }

    private fun attachCollectionStatus(payload: JSONObject, failures: Map<String, String>) {
        payload.put("collection_status", fieldStatusReporter.build(payload, failures))
    }

    private fun uploadExpandedFeatures(payload: JSONObject, featureCount: Int): UploadStatus {
        val body = payload
            .toString()
            .toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url(collectEndpoint)
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

    private fun resolveCollectEndpoint(): String {
        val override = intent?.getStringExtra(INTENT_EXTRA_COLLECT_ENDPOINT)?.trim().orEmpty()
        return if (override.startsWith("http://") || override.startsWith("https://")) {
            override
        } else {
            COLLECT_ENDPOINT
        }
    }

    private fun updateProbeUi(status: String, detail: String, style: String) {
        val activeWebView = webView ?: return
        val script = """
            window.HybridGuardProbe && window.HybridGuardProbe.updateResult(
                ${JSONObject.quote(status)},
                ${JSONObject.quote(detail)},
                ${JSONObject.quote(style)}
            );
        """.trimIndent()
        activeWebView.evaluateJavascript(script, null)
    }

    private fun detectFallbackRuntime(): FallbackRuntime? {
        val appDataPath = applicationInfo.dataDir.orEmpty()
        val filesPath = filesDir.absolutePath
        if (
            appDataPath.contains("/io.va.exposed64/virtual/") ||
            filesPath.contains("/io.va.exposed64/virtual/")
        ) {
            return FallbackRuntime(
                containerName = "VirtualXposed",
                reason = "virtualxposed_webview_crash",
                blocker = "VirtualXposed cannot initialize Chromium/WebView on this API30 runtime"
            )
        }

        if (Build.MANUFACTURER.equals("BlueStacks", ignoreCase = true)) {
            return blueStacksFallbackRuntime()
        }
        val blueStacksPackages = listOf(
            "com.bluestacks.settings",
            "com.bluestacks.gamecenter",
            "com.bluestacks.bsxlauncher",
            "com.uncube.launcher3"
        )
        return if (blueStacksPackages.any { packageName ->
            try {
                packageManager.getPackageInfo(packageName, 0)
                true
            } catch (e: Exception) {
                false
            }
        }) blueStacksFallbackRuntime() else null
    }

    private fun blueStacksFallbackRuntime() = FallbackRuntime(
        containerName = "BlueStacks",
        reason = "bluestacks_webview_renderthread_crash",
        blocker = "BlueStacks WebView RenderThread crashed before the JavaScript probe could run"
    )

    private fun buildHttpClient(): OkHttpClient {
        val proxyHost = intent?.getStringExtra(INTENT_EXTRA_HTTP_PROXY_HOST)?.trim().orEmpty()
        val proxyPort = intent?.getIntExtra(INTENT_EXTRA_HTTP_PROXY_PORT, 0) ?: 0
        if (proxyHost.isBlank() || proxyPort !in 1..65535) return OkHttpClient()

        return OkHttpClient.Builder()
            .proxy(Proxy(Proxy.Type.HTTP, InetSocketAddress(proxyHost, proxyPort)))
            .build()
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

    private data class FallbackRuntime(
        val containerName: String,
        val reason: String,
        val blocker: String
    )

    companion object {
        const val INTENT_EXTRA_COLLECT_ENDPOINT = "collect_endpoint"
        const val INTENT_EXTRA_ENABLE_WEBVIEW_DEBUG = "enable_webview_debug"
        const val INTENT_EXTRA_PROBE_DELAY_MS = "probe_delay_ms"
        const val INTENT_EXTRA_HTTP_PROXY_HOST = "http_proxy_host"
        const val INTENT_EXTRA_HTTP_PROXY_PORT = "http_proxy_port"
        const val INTENT_EXTRA_RUNTIME_CONTEXT = "runtime_context"
        const val INTENT_EXTRA_COLLECTION_ROUND = "collection_round"
        const val INTENT_EXTRA_DEVICE_MANIFEST_ID = "device_manifest_id"
        private const val WEBVIEW_COLLECTION_TIMEOUT_MS = 20_000L
        private const val COLLECT_ENDPOINT =
            "http://127.0.0.1:8000/api/collect/fingerprint"
    }
}
