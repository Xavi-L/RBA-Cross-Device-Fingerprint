package com.example.hybridguard.featureapp

import android.graphics.Rect
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.View
import android.view.WindowInsets
import android.webkit.WebView
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener

/** All View reads and JS dispatch/callback work occur asynchronously on the main Looper. */
internal class WebViewGeometryObserver(
    private val webView: WebView,
    private val sessionId: String,
    private val policy: GeometrySamplingPolicy,
    private val experimentReceipt: JSONObject
) {
    private val handler = Handler(Looper.getMainLooper())
    val instanceId = UUID.randomUUID().toString()
    private var layoutSequence = 0L
    private var scaleSequence = 0L
    private var lastEventAt = SystemClock.elapsedRealtime()
    private var scaleValue: Float? = null
    private var scaleTime: Long? = null
    private var scaleGeneration: Long? = null
    private val attempts = JSONArray()
    private var callback: ((JSONObject) -> Unit)? = null
    private var selected: JSONObject? = null
    private var attemptToken: String? = null
    private var expectedDocumentId: String? = null
    private var startedAt = 0L
    private var startedGeneration = 0L
    private val overallTimeout = Runnable { finish("timeout", "geometry_total_timeout") }
    private val layoutListener = View.OnLayoutChangeListener { _, l, t, r, b, ol, ot, or, ob ->
        if (l != ol || t != ot || r != or || b != ob) {
            layoutSequence += 1
            lastEventAt = SystemClock.elapsedRealtime()
        }
    }

    init { checkMain(); webView.addOnLayoutChangeListener(layoutListener) }

    fun onNavigation() {
        checkMain()
        policy.navigate()
        lastEventAt = SystemClock.elapsedRealtime()
        scaleValue = null; scaleTime = null; scaleGeneration = null
        if (callback != null) {
            if (attempts.length() > 0) attempts.getJSONObject(attempts.length() - 1)
                .put("read_status", "unavailable").put("reason", "document_changed_during_geometry")
            finish("unavailable", "document_changed_during_geometry")
        }
    }

    fun onScaleChanged(oldScale: Float, newScale: Float) {
        checkMain()
        scaleSequence += 1
        lastEventAt = SystemClock.elapsedRealtime()
        scaleValue = newScale.takeIf { it.isFinite() && it > 0f }
        scaleTime = lastEventAt
        scaleGeneration = policy.generation
        experimentReceipt.put("latest_scale_callback", JSONObject()
            .put("old_scale", oldScale.toDouble()).put("new_scale", newScale.toDouble())
            .put("elapsed_realtime_ms", lastEventAt).put("event_sequence", scaleSequence)
            .put("document_generation", policy.generation))
    }

    fun collect(documentId: String?, completion: (JSONObject) -> Unit) {
        checkMain()
        if (callback != null) return
        callback = completion
        expectedDocumentId = documentId
        startedAt = SystemClock.elapsedRealtime()
        startedGeneration = policy.generation
        handler.postDelayed(overallTimeout, GeometrySamplingPolicy.TOTAL_TIMEOUT_MS)
        if (documentId.isNullOrBlank()) finish("unavailable", "legacy_document_binding_missing")
        else attempt()
    }

    private fun attempt() {
        try { attemptInternal() }
        catch (error: Exception) { finish("runtime_error", "host_snapshot_${error.javaClass.simpleName}") }
    }

    private fun attemptInternal() {
        checkMain()
        if (callback == null) return
        if (!policy.callbackIsCurrent(startedGeneration)) {
            finish("unavailable", "activity_or_document_replaced"); return
        }
        val wait = GeometrySamplingPolicy.QUIET_MS - (SystemClock.elapsedRealtime() - lastEventAt)
        if (wait > 0) { handler.postDelayed({ attempt() }, wait); return }
        if (attempts.length() >= GeometrySamplingPolicy.MAX_ATTEMPTS) {
            finish("unstable", "attempt_limit_reached"); return
        }
        val observationId = UUID.randomUUID().toString()
        val entry = JSONObject().put("observation_id", observationId)
            .put("attempt_id", attempts.length() + 1)
            .put("session_id", sessionId).put("webview_instance_id", instanceId)
            .put("document_generation", startedGeneration)
        attempts.put(entry)
        attemptToken = observationId
        val before = GeometryReadBoundary.readIfCurrent(
            { callback != null && policy.callbackIsCurrent(startedGeneration) },
            "host_before_snapshot", ::hostSnapshot
        ) { reason ->
            entry.put("read_status", "runtime_error").put("reason", reason)
            finish("runtime_error", reason)
        } ?: return
        entry.put("host_before", before)
        val request = JSONObject().put("session_id", sessionId)
            .put("webview_instance_id", instanceId).put("document_generation", startedGeneration)
            .put("observation_id", observationId).put("attempt_id", entry.getInt("attempt_id"))
        val timeout = Runnable {
            if (attemptToken == observationId && callback != null) {
                attemptToken = null
                entry.put("read_status", "timeout").put("reason", "evaluate_javascript_timeout")
                retryOrFinish(entry)
            }
        }
        handler.postDelayed(timeout, GeometrySamplingPolicy.ATTEMPT_TIMEOUT_MS)
        try {
            webView.evaluateJavascript(
                "(function(){return window.HybridGuardProbe && " +
                    "window.HybridGuardProbe.captureWebViewGeometry ? " +
                    "window.HybridGuardProbe.captureWebViewGeometry($request) : null;})()"
            ) { encoded ->
                checkMain()
                if (attemptToken != observationId || callback == null) return@evaluateJavascript
                handler.removeCallbacks(timeout)
                attemptToken = null
                if (!policy.callbackIsCurrent(startedGeneration)) {
                    entry.put("read_status", "unavailable").put("reason", "stale_document_callback")
                    finish("unavailable", "stale_document_callback"); return@evaluateJavascript
                }
                try {
                    // This runs later on the main Looper; the dispatch try cannot catch it.
                    val after = GeometryReadBoundary.readIfCurrent(
                        { callback != null && policy.callbackIsCurrent(startedGeneration) },
                        "host_after_snapshot", ::hostSnapshot
                    ) { reason ->
                        entry.put("read_status", "runtime_error").put("reason", reason)
                        retryOrFinish(entry)
                    } ?: return@evaluateJavascript
                    entry.put("host_after", after)
                    val decoded = JSONTokener(encoded ?: "null").nextValue()
                    val web = when (decoded) {
                        is JSONObject -> decoded
                        is String -> JSONObject(decoded)
                        else -> null
                    }
                    entry.put("web", web ?: JSONObject.NULL)
                    val bound = GeometrySnapshotBinding.matches(web, expectedDocumentId, sessionId,
                        instanceId, startedGeneration, observationId, entry.getInt("attempt_id"))
                    val stable = GeometrySamplingPolicy.hostStable(
                        before.getJSONObject("sequence").toString(), after.getJSONObject("sequence").toString(),
                        hostSignature(before), hostSignature(after),
                        before.getJSONObject("clock").getLong("elapsed_realtime_ms"),
                        after.getJSONObject("clock").getLong("elapsed_realtime_ms"))
                    entry.put("binding_valid", bound).put("host_stable", stable)
                    entry.put("read_status", if (!bound) "unavailable" else if (!stable) "unstable" else "observed")
                    entry.put("reason", if (!bound) "web_binding_mismatch_or_missing" else if (!stable) "host_changed_during_window" else JSONObject.NULL)
                    // Web values do not participate in stability, including any stable contradiction.
                    if (bound && stable) { selected = entry; finish("observed", null) }
                    else retryOrFinish(entry)
                } catch (error: Exception) {
                    entry.put("read_status", "runtime_error").put("reason", "web_snapshot_parse_${error.javaClass.simpleName}")
                    retryOrFinish(entry)
                }
            }
        } catch (error: Exception) {
            handler.removeCallbacks(timeout); attemptToken = null
            entry.put("read_status", "runtime_error").put("reason", "evaluate_javascript_${error.javaClass.simpleName}")
            retryOrFinish(entry)
        }
    }

    private fun retryOrFinish(entry: JSONObject) {
        // A late callback cannot schedule another read after completion/navigation.
        if (callback == null || !policy.callbackIsCurrent(startedGeneration)) return
        if (attempts.length() < GeometrySamplingPolicy.MAX_ATTEMPTS) handler.postDelayed({ attempt() }, GeometrySamplingPolicy.QUIET_MS)
        else finish(entry.optString("read_status", "unavailable"), entry.optString("reason", "attempt_limit_reached"))
    }

    private fun finish(status: String, reason: String?) {
        checkMain()
        val complete = callback ?: return
        callback = null; attemptToken = null
        if (attempts.length() > 0) {
            val last = attempts.getJSONObject(attempts.length() - 1)
            if (!last.has("read_status")) last.put("read_status", status).put("reason", reason ?: JSONObject.NULL)
        }
        handler.removeCallbacks(overallTimeout)
        if (!policy.finishOnce()) return
        val result = JSONObject().put("schema_version", "webview-geometry-v1")
            .put("collector_version", "featureapp-geometry-v1.1").put("read_status", status)
            .put("reason", reason ?: JSONObject.NULL).put("session_id", sessionId)
            .put("webview_instance_id", instanceId).put("document_generation", startedGeneration)
            .put("document_id", expectedDocumentId ?: JSONObject.NULL)
            .put("started_elapsed_realtime_ms", startedAt)
            .put("finished_elapsed_realtime_ms", SystemClock.elapsedRealtime())
            .put("clock_domain", "android_elapsed_realtime_ms")
            .put("attempt_limit", GeometrySamplingPolicy.MAX_ATTEMPTS)
            .put("timeout_ms", GeometrySamplingPolicy.TOTAL_TIMEOUT_MS)
            .put("stability_claim", "no_host_change_observed_not_atomic")
            .put("same_snapshot_as_legacy_screen_layer", false)
            .put("attempts", attempts).put("selected_observation_id", selected?.optString("observation_id") ?: JSONObject.NULL)
            .put("operation_receipt", JSONObject(experimentReceipt.toString()))
        selected?.let {
            result.put("host_before", it.getJSONObject("host_before"))
                .put("web", it.get("web")).put("host_after", it.getJSONObject("host_after"))
                .put("binding_valid", it.getBoolean("binding_valid")).put("host_stable", it.getBoolean("host_stable"))
        }
        complete(result)
    }

    fun destroy() {
        checkMain()
        // Complete an accepted legacy payload as degraded once; later JS callbacks cannot mutate it.
        if (callback != null) {
            if (attempts.length() > 0) attempts.getJSONObject(attempts.length() - 1)
                .put("read_status", "unavailable").put("reason", "activity_destroyed")
            finish("unavailable", "activity_destroyed")
        }
        policy.destroy()
        handler.removeCallbacksAndMessages(null)
        webView.removeOnLayoutChangeListener(layoutListener)
    }

    @Suppress("DEPRECATION")
    private fun hostSnapshot(): JSONObject {
        checkMain()
        val now = SystemClock.elapsedRealtime()
        val location = IntArray(2); webView.getLocationInWindow(location)
        val visible = Rect(); val visibleOk = webView.getGlobalVisibleRect(visible)
        val frame = Rect(); webView.getWindowVisibleDisplayFrame(frame)
        val parent = webView.parent as? View
        val metrics = webView.resources.displayMetrics
        val callbackObserved = scaleValue != null && scaleGeneration == policy.generation
        val insets = JSONObject().put("status", "unsupported")
        if (Build.VERSION.SDK_INT >= 23) {
            val current = webView.rootWindowInsets
            if (current == null) insets.put("status", "unavailable")
            else {
                insets.put("status", "observed")
                    .put("system_window_left_px", current.systemWindowInsetLeft)
                    .put("system_window_top_px", current.systemWindowInsetTop)
                    .put("system_window_right_px", current.systemWindowInsetRight)
                    .put("system_window_bottom_px", current.systemWindowInsetBottom)
                    .put("stable_left_px", current.stableInsetLeft).put("stable_top_px", current.stableInsetTop)
                    .put("stable_right_px", current.stableInsetRight).put("stable_bottom_px", current.stableInsetBottom)
                if (Build.VERSION.SDK_INT >= 30) insets.put("ime_visible", current.isVisible(WindowInsets.Type.ime()))
                else insets.put("ime_visible", JSONObject.NULL).put("ime_read_status", "unsupported")
            }
        }
        val settings = webView.settings
        return JSONObject().put("read_status", "observed").put("thread", "android_main")
            .put("clock", JSONObject().put("elapsed_realtime_ms", now).put("epoch_ms", System.currentTimeMillis()))
            .put("sequence", JSONObject().put("layout", layoutSequence).put("scale", scaleSequence).put("document", policy.generation))
            .put("last_host_event_elapsed_realtime_ms", lastEventAt)
            .put("width_px", webView.width).put("height_px", webView.height)
            .put("padding_left_px", webView.paddingLeft).put("padding_top_px", webView.paddingTop)
            .put("padding_right_px", webView.paddingRight).put("padding_bottom_px", webView.paddingBottom)
            .put("content_width_px", webView.width - webView.paddingLeft - webView.paddingRight)
            .put("content_height_px", webView.height - webView.paddingTop - webView.paddingBottom)
            .put("content_region_definition", "view_bounds_minus_padding_no_inset_subtraction")
            .put("location_in_window_px", JSONArray(listOf(location[0], location[1])))
            .put("global_visible_rect_available", visibleOk).put("global_visible_rect_px", rect(visible))
            .put("window_visible_display_frame_px", rect(frame))
            .put("root_width_px", webView.rootView.width).put("root_height_px", webView.rootView.height)
            .put("parent_width_px", parent?.width ?: JSONObject.NULL).put("parent_height_px", parent?.height ?: JSONObject.NULL)
            .put("density", metrics.density.toDouble()).put("density_dpi", metrics.densityDpi)
            .put("resources_display_metrics_role", "display_configuration_not_webview_content")
            .put("orientation", webView.resources.configuration.orientation)
            .put("view_scale_x", webView.scaleX.toDouble()).put("view_scale_y", webView.scaleY.toDouble())
            .put("rotation_degrees", webView.rotation.toDouble())
            .put("scroll_x_px", webView.scrollX).put("scroll_y_px", webView.scrollY)
            .put("horizontal_scrollbar_enabled", webView.isHorizontalScrollBarEnabled)
            .put("vertical_scrollbar_enabled", webView.isVerticalScrollBarEnabled)
            .put("scrollbar_style", webView.scrollBarStyle)
            .put("visibility", webView.visibility).put("window_visibility", webView.windowVisibility)
            .put("is_shown", webView.isShown).put("is_attached_to_window", webView.isAttachedToWindow)
            .put("root_window_insets", insets)
            .put("scale", JSONObject().put("status", if (callbackObserved) "observed" else "not_observed")
                .put("callback_value", if (callbackObserved) scaleValue!!.toDouble() else JSONObject.NULL)
                .put("source", "WebViewClient.onScaleChanged")
                .put("callback_elapsed_realtime_ms", scaleTime ?: JSONObject.NULL)
                .put("age_ms", scaleTime?.let { now - it } ?: JSONObject.NULL)
                .put("document_generation", scaleGeneration ?: JSONObject.NULL)
                .put("event_sequence", scaleSequence))
            .put("diagnostic_get_scale", JSONObject().put("value", webView.scale.toDouble())
                .put("source", "WebView.getScale_deprecated_potential_race").put("reference_eligible", false))
            .put("web_settings", JSONObject().put("support_zoom", settings.supportZoom())
                .put("built_in_zoom_controls", settings.builtInZoomControls).put("display_zoom_controls", settings.displayZoomControls)
                .put("use_wide_view_port", settings.useWideViewPort).put("load_with_overview_mode", settings.loadWithOverviewMode)
                .put("text_zoom_percent", settings.textZoom).put("layout_algorithm", settings.layoutAlgorithm.name)
                .put("java_script_enabled", settings.javaScriptEnabled))
    }

    private fun hostSignature(host: JSONObject): String = listOf(
        "width_px", "height_px", "padding_left_px", "padding_top_px", "padding_right_px", "padding_bottom_px",
        "location_in_window_px", "global_visible_rect_px", "window_visible_display_frame_px", "orientation",
        "density", "density_dpi", "view_scale_x", "view_scale_y", "rotation_degrees", "root_width_px", "root_height_px",
        "parent_width_px", "parent_height_px", "root_window_insets", "web_settings"
    ).joinToString("|") { host.get(it).toString() }

    private fun rect(value: Rect) = JSONObject().put("left", value.left).put("top", value.top)
        .put("right", value.right).put("bottom", value.bottom).put("width", value.width()).put("height", value.height())
    private fun checkMain() { check(Looper.myLooper() == Looper.getMainLooper()) { "Geometry requires main Looper" } }
}
