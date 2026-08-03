package com.example.hybridguard.featureapp

import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import java.util.Collections
import java.util.HashSet
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import org.json.JSONObject

class MainActivity : AppCompatActivity(), ExpandedWebBridge.Listener {

    private lateinit var sessionId: String
    private lateinit var browserTicketRequestId: String
    private val payloadAccepted = AtomicBoolean(false)
    private val preparedFallbackReceiptIds =
        Collections.synchronizedSet(HashSet<String>())
    private val handledBrowserPairIds =
        Collections.synchronizedSet(HashSet<String>())
    private val pendingBrowserRetries = mutableMapOf<String, BrowserRetryState>()
    private val provisionalTicketStarted = AtomicBoolean(false)
    private val browserFlowLock = Any()
    private var provisionalTicketState = ProvisionalTicketState.NOT_STARTED
    private var verifiedReceiptForFallback: VerifiedCollectionReceipt? = null
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
    private val pendingBrowserHandoffCheck = object : Runnable {
        override fun run() {
            if (isFinishing || isDestroyed) {
                return
            }
            val claim = ExpandedUploadWorker.peekPendingBrowserHandoff(applicationContext)
            if (claim != null) {
                val accepted = prepareReceiptBoundBrowserFallback(
                    claim.handoff.receipt,
                    claim.handoff.collectEndpoint,
                    claim.handoff.browserTicketRequestId,
                    claim
                )
                if (!accepted) {
                    mainHandler.postDelayed(this, BACKGROUND_HANDOFF_CHECK_MS)
                }
                return
            }
            mainHandler.postDelayed(this, BACKGROUND_HANDOFF_CHECK_MS)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sessionId = savedInstanceState?.getString(STATE_SESSION_ID)
            ?: UUID.randomUUID().toString()
        browserTicketRequestId =
            savedInstanceState?.getString(STATE_BROWSER_TICKET_REQUEST_ID)
                ?: UUID.randomUUID().toString()
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
                put("web_probe_revision", BuildConfig.WEB_PROBE_REVISION)
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
                put("web_probe_revision", BuildConfig.WEB_PROBE_REVISION)
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

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString(STATE_SESSION_ID, sessionId)
        outState.putString(STATE_BROWSER_TICKET_REQUEST_ID, browserTicketRequestId)
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        mainHandler.removeCallbacks(pendingBrowserHandoffCheck)
        mainHandler.post(pendingBrowserHandoffCheck)
        schedulePendingBrowserRetries(BROWSER_RETRY_AFTER_RESUME_MS)
    }

    override fun onPause() {
        mainHandler.removeCallbacks(pendingBrowserHandoffCheck)
        super.onPause()
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
            val webProbeDiagnostics = webPayload.optJSONObject("collection_diagnostics")
            val probeStatuses = webProbeDiagnostics
                ?.optJSONObject("probe_statuses")
                ?: JSONObject()
            val webProbeRevision = webProbeDiagnostics
                ?.optString("web_probe_revision")
                ?.takeIf(String::isNotBlank)
                ?: BuildConfig.WEB_PROBE_REVISION
            val featurePayload = JSONObject().apply {
                put("session_id", sessionId)
                put("browser_ticket_request_id", browserTicketRequestId)
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
                        put("web_probe_revision", webProbeRevision)
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

            val payloadPersisted = try {
                ExpandedUploadWorker.persistAndEnqueue(
                    applicationContext,
                    sessionId,
                    serializedPayload,
                    collectEndpoint
                )
            } catch (error: Exception) {
                Log.e(
                    TAG_BROWSER_FLOW,
                    "Payload persistence failed; provisional browser launch is suppressed.",
                    error
                )
                synchronized(browserFlowLock) {
                    provisionalTicketState = ProvisionalTicketState.FAILED
                }
                false
            }
            if (payloadPersisted) {
                startProvisionalBrowserTicketRequest()
            }

            thread(name = "hybridguard-app-upload") {
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
                uploadStatus.receipt?.let {
                    onAppReceiptVerified(it)
                }
            }
        } catch (e: Exception) {
            val emergencyPayload = JSONObject().apply {
                put("session_id", sessionId)
                put("browser_ticket_request_id", browserTicketRequestId)
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
                        put("web_probe_revision", BuildConfig.WEB_PROBE_REVISION)
                        put("fallback_reason", "android_payload_assembly_error")
                        put("assembly_error", e.javaClass.simpleName)
                        put("collection_finished_at_ms", System.currentTimeMillis())
                    }
                )
            }.toString()
            try {
                val emergencyPayloadPersisted = ExpandedUploadWorker.persistAndEnqueue(
                    applicationContext,
                    sessionId,
                    emergencyPayload,
                    collectEndpoint
                )
                if (emergencyPayloadPersisted) {
                    startProvisionalBrowserTicketRequest()
                }
                thread(name = "hybridguard-emergency-app-upload") {
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
                        emergencyStatus.receipt?.let {
                            onAppReceiptVerified(it)
                        }
                    }
                }
            } catch (_: Exception) {
                synchronized(browserFlowLock) {
                    provisionalTicketState = ProvisionalTicketState.FAILED
                }
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
                        "$observedSignalCount/$fixedSignalCount observed. Receipt/hash verified.",
                    lastAttempt.receipt
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
            "Upload deferred for background retry: ${lastAttempt.detail}.",
            null
        )
    }

    private fun startProvisionalBrowserTicketRequest() {
        if (!provisionalTicketStarted.compareAndSet(false, true)) {
            return
        }
        synchronized(browserFlowLock) {
            provisionalTicketState = ProvisionalTicketState.IN_FLIGHT
        }
        thread(name = "hybridguard-provisional-browser-ticket") {
            val preparation = BrowserCollectionCoordinator.prepareProvisional(
                context = applicationContext,
                appSessionId = sessionId,
                ticketRequestId = browserTicketRequestId,
                collectEndpoint = collectEndpoint
            )
            val fallbackReceipt = synchronized(browserFlowLock) {
                provisionalTicketState = when (preparation) {
                    is BrowserCollectionCoordinator.Preparation.Ready ->
                        ProvisionalTicketState.READY
                    is BrowserCollectionCoordinator.Preparation.Failed ->
                        ProvisionalTicketState.FAILED
                    is BrowserCollectionCoordinator.Preparation.Skipped ->
                        ProvisionalTicketState.SKIPPED
                }
                if (provisionalTicketState == ProvisionalTicketState.FAILED) {
                    verifiedReceiptForFallback
                } else {
                    null
                }
            }
            runOnUiThread {
                when (preparation) {
                    is BrowserCollectionCoordinator.Preparation.Ready ->
                        handlePreparedBrowserTicket(
                            preparation,
                            browserTicketRequestId,
                            appReceiptAlreadyVerified =
                                preparation.ticket.appReceiptId != null
                        )
                    is BrowserCollectionCoordinator.Preparation.Skipped -> {
                        statusText.text =
                            "App upload continues; ${preparation.detail}"
                        updateProbeUi(
                            "Browser companion collection skipped",
                            preparation.detail,
                            "good"
                        )
                    }
                    is BrowserCollectionCoordinator.Preparation.Failed -> {
                        statusText.text =
                            "App upload continues; provisional browser ticket failed."
                        updateProbeUi(
                            "Waiting for receipt-bound browser fallback",
                            preparation.detail,
                            "good"
                        )
                    }
                }
            }
            fallbackReceipt?.let {
                prepareReceiptBoundBrowserFallback(
                    receipt = it,
                    receiptCollectEndpoint = collectEndpoint,
                    ticketRequestId = browserTicketRequestId
                )
            }
        }
    }

    private fun onAppReceiptVerified(receipt: VerifiedCollectionReceipt) {
        val shouldStartFallback = synchronized(browserFlowLock) {
            verifiedReceiptForFallback = receipt
            provisionalTicketState == ProvisionalTicketState.FAILED
        }
        Log.i(
            TAG_BROWSER_FLOW,
            "app_receipt_verified session=${receipt.sessionId}; receipt=${receipt.receiptId}; " +
                "sha256=${receipt.payloadSha256}; provisional_state=$provisionalTicketState; " +
                "receipt_fallback=$shouldStartFallback"
        )
        if (shouldStartFallback) {
            prepareReceiptBoundBrowserFallback(
                receipt = receipt,
                receiptCollectEndpoint = collectEndpoint,
                ticketRequestId = browserTicketRequestId
            )
        }
    }

    private fun prepareReceiptBoundBrowserFallback(
        receipt: VerifiedCollectionReceipt,
        receiptCollectEndpoint: String,
        ticketRequestId: String,
        pendingHandoffClaim: PendingBrowserHandoffClaim? = null
    ): Boolean {
        if (!preparedFallbackReceiptIds.add(receipt.receiptId)) {
            return false
        }
        Log.i(
            TAG_BROWSER_FLOW,
            "receipt_bound_fallback session=${receipt.sessionId}; receipt=${receipt.receiptId}; " +
                "request=$ticketRequestId"
        )
        thread(name = "hybridguard-receipt-browser-ticket") {
            val preparation = BrowserCollectionCoordinator.prepareReceiptBound(
                context = applicationContext,
                receipt = receipt,
                ticketRequestId = ticketRequestId,
                collectEndpoint = receiptCollectEndpoint
            )
            if (preparation !is BrowserCollectionCoordinator.Preparation.Ready) {
                // A failed/skipped ticket preparation must leave a durable
                // background handoff available for a later foreground retry.
                preparedFallbackReceiptIds.remove(receipt.receiptId)
            }
            runOnUiThread {
                when (preparation) {
                    is BrowserCollectionCoordinator.Preparation.Skipped -> {
                        statusText.text =
                            "App payload uploaded and verified. ${preparation.detail}"
                        updateProbeUi(
                            "App payload uploaded; browser collection skipped",
                            preparation.detail,
                            "good"
                        )
                    }
                    is BrowserCollectionCoordinator.Preparation.Failed -> {
                        // Browser pairing is intentionally non-destructive: the App
                        // receipt has already been verified and its pending upload cleared.
                        statusText.text =
                            "App payload uploaded and verified. ${preparation.detail}"
                        updateProbeUi(
                            "App payload safe; browser companion failed",
                            preparation.detail,
                            "good"
                        )
                        if (pendingHandoffClaim != null && !isFinishing && !isDestroyed) {
                            mainHandler.removeCallbacks(pendingBrowserHandoffCheck)
                            mainHandler.postDelayed(
                                pendingBrowserHandoffCheck,
                                BACKGROUND_HANDOFF_RETRY_MS
                            )
                        }
                    }
                    is BrowserCollectionCoordinator.Preparation.Ready -> {
                        handlePreparedBrowserTicket(
                            preparation,
                            ticketRequestId,
                            appReceiptAlreadyVerified = true
                        )
                    }
                }
            }
        }
        return true
    }

    private fun handlePreparedBrowserTicket(
        preparation: BrowserCollectionCoordinator.Preparation.Ready,
        ticketRequestId: String,
        appReceiptAlreadyVerified: Boolean
    ) {
        val pairId = preparation.ticket.pairId
        if (!handledBrowserPairIds.add(pairId)) {
            Log.i(
                TAG_BROWSER_FLOW,
                "browser_launch_duplicate_suppressed pair_id=$pairId; request=$ticketRequestId"
            )
            return
        }
        val appStateDetail = if (appReceiptAlreadyVerified) {
            "App receipt is already bound."
        } else {
            "App payload is persisted; App upload continues in background."
        }
        val launchIntent = BrowserCollectionCoordinator.explicitLaunchIntent(preparation)
        if (launchIntent == null) {
            ExpandedUploadWorker.markBrowserTicketHandled(
                applicationContext,
                preparation.ticket.appSessionId,
                ticketRequestId,
                pairId
            )
            val detail =
                "Browser ticket recorded, but resolution=${preparation.resolution.status}; " +
                    "no qualified available browser was selected. " +
                    "The system chooser was not opened; pair $pairId will be polled. " +
                    appStateDetail
            statusText.text = detail
            updateProbeUi(
                "No qualified available browser",
                detail,
                "good"
            )
            Log.w(TAG_BROWSER_FLOW, detail)
            return
        }
        if (isFinishing || isDestroyed) {
            handledBrowserPairIds.remove(pairId)
            val detail =
                "Ticket $pairId is persisted for polling, but Activity is no longer launchable."
            statusText.text = "$detail $appStateDetail"
            Log.w(TAG_BROWSER_FLOW, detail)
            return
        }
        try {
            // Restrict resolution to the selected browser package, while letting
            // that browser route the web URL to its own correct internal Activity.
            startActivity(launchIntent)
            reportBrowserLaunchAttempt(preparation.pollState, 1)
            pendingBrowserRetries[pairId] = BrowserRetryState(
                preparation = preparation,
                ticketRequestId = ticketRequestId
            )
            scheduleBrowserRetry(pairId, BROWSER_FIRST_STAGE_DEADLINE_MS)
            val handledPersisted = ExpandedUploadWorker.markBrowserTicketHandled(
                applicationContext,
                preparation.ticket.appSessionId,
                ticketRequestId,
                pairId
            )
            val detail =
                "Available browser package ${preparation.resolution.packageName} " +
                    "launched (resolved activity " +
                    "${preparation.resolution.activityName}) via " +
                    "${preparation.resolution.status}; " +
                    "pair $pairId is polling without an App callback. $appStateDetail"
            statusText.text = detail
            updateProbeUi(
                "Available-browser companion collection launched",
                detail,
                "good"
            )
            Log.i(
                TAG_BROWSER_FLOW,
                "browser_launched pair_id=$pairId; request=$ticketRequestId; " +
                    "binding_mode=${preparation.ticket.ticketBindingMode}; " +
                    "handled_persisted=$handledPersisted; $detail"
            )
        } catch (error: Exception) {
            handledBrowserPairIds.remove(pairId)
            val detail =
                "Explicit browser launch failed (${error.javaClass.simpleName}); " +
                    "pair $pairId remains auditable. $appStateDetail"
            statusText.text = detail
            updateProbeUi(
                "Browser launch failed",
                detail,
                "good"
            )
            Log.e(TAG_BROWSER_FLOW, detail, error)
        }
    }

    private fun reportBrowserLaunchAttempt(
        state: BrowserPairPollState,
        launchAttempt: Int
    ) {
        thread(name = "hybridguard-browser-launch-stage-$launchAttempt") {
            BrowserPairTransport.reportLaunchAttempt(state, launchAttempt)
        }
    }

    private fun schedulePendingBrowserRetries(delayMs: Long) {
        pendingBrowserRetries.keys.toList().forEach { pairId ->
            scheduleBrowserRetry(pairId, delayMs)
        }
    }

    private fun scheduleBrowserRetry(pairId: String, delayMs: Long) {
        val retryState = pendingBrowserRetries[pairId] ?: return
        if (retryState.scheduled || retryState.attempted) {
            return
        }
        retryState.scheduled = true
        mainHandler.postDelayed(
            {
                retryState.scheduled = false
                inspectAndMaybeRetryBrowser(pairId, retryState)
            },
            delayMs
        )
    }

    private fun inspectAndMaybeRetryBrowser(
        pairId: String,
        retryState: BrowserRetryState
    ) {
        if (pendingBrowserRetries[pairId] !== retryState || retryState.attempted) {
            return
        }
        if (!activityCanLaunchBrowser()) {
            // The browser still owns the foreground. onResume will schedule the
            // check again if the cloud runner returns to the collector App.
            return
        }
        thread(name = "hybridguard-browser-stage-check") {
            val poll = BrowserPairTransport.poll(retryState.preparation.pollState)
            runOnUiThread {
                if (
                    pendingBrowserRetries[pairId] !== retryState ||
                    retryState.attempted
                ) {
                    return@runOnUiThread
                }
                val browserReachedPage =
                    poll is BrowserPairTransport.PollResult.Received &&
                        (
                            poll.result.terminal ||
                                poll.result.latestBrowserStage != null ||
                                poll.result.browserStageCount > 0
                            )
                if (browserReachedPage) {
                    pendingBrowserRetries.remove(pairId)
                    Log.i(
                        TAG_BROWSER_FLOW,
                        "browser_retry_suppressed pair_id=$pairId; " +
                            "browser stage or terminal payload already observed"
                    )
                    return@runOnUiThread
                }
                if (!activityCanLaunchBrowser()) {
                    return@runOnUiThread
                }
                val retryIntent = BrowserCollectionCoordinator.explicitLaunchIntent(
                    retryState.preparation,
                    launchAttempt = 2
                ) ?: run {
                    pendingBrowserRetries.remove(pairId)
                    return@runOnUiThread
                }
                retryState.attempted = true
                pendingBrowserRetries.remove(pairId)
                try {
                    startActivity(retryIntent)
                    reportBrowserLaunchAttempt(retryState.preparation.pollState, 2)
                    Log.i(
                        TAG_BROWSER_FLOW,
                        "browser_relaunched pair_id=$pairId; request=" +
                            retryState.ticketRequestId + "; launch_attempt=2"
                    )
                } catch (error: Exception) {
                    Log.e(
                        TAG_BROWSER_FLOW,
                        "Browser relaunch failed pair_id=$pairId",
                        error
                    )
                }
            }
        }
    }

    private fun activityCanLaunchBrowser(): Boolean {
        return !isFinishing &&
            !isDestroyed &&
            lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)
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

    private data class UploadStatus(
        val uploaded: Boolean,
        val message: String,
        val receipt: VerifiedCollectionReceipt?
    )

    private enum class ProvisionalTicketState {
        NOT_STARTED,
        IN_FLIGHT,
        READY,
        FAILED,
        SKIPPED
    }

    private data class BrowserRetryState(
        val preparation: BrowserCollectionCoordinator.Preparation.Ready,
        val ticketRequestId: String,
        var scheduled: Boolean = false,
        var attempted: Boolean = false
    )

    companion object {
        private const val STATE_SESSION_ID = "state_session_id"
        private const val STATE_BROWSER_TICKET_REQUEST_ID =
            "state_browser_ticket_request_id"
        private const val WEB_PROBE_DEADLINE_MS = 15_000L
        private const val BACKGROUND_HANDOFF_CHECK_MS = 2_000L
        private const val BACKGROUND_HANDOFF_RETRY_MS = 10_000L
        private const val BROWSER_FIRST_STAGE_DEADLINE_MS = 8_000L
        private const val BROWSER_RETRY_AFTER_RESUME_MS = 1_000L
        private const val IMMEDIATE_UPLOAD_ATTEMPTS = 3
        private val IMMEDIATE_RETRY_DELAYS_MS = longArrayOf(250, 750)
        private const val TAG_BROWSER_FLOW = "HG-BrowserFlow"
    }
}
