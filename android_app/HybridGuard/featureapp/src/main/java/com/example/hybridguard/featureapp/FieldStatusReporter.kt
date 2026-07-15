package com.example.hybridguard.featureapp

import android.content.Context
import android.os.Build
import org.json.JSONObject

/**
 * Emits availability state separately from the fixed 177 signal values.
 *
 * A field is observed when the collector supplied a non-null value. Empty strings, zeroes and
 * default probe values are still observed: semantic validity is assessed downstream, while this
 * object reports whether collection produced a value at all.
 */
class FieldStatusReporter(private val context: Context) {
    private val expectedFields: List<String> by lazy {
        context.assets.open(FIELD_CATALOG_ASSET).bufferedReader().useLines { lines ->
            lines.drop(1)
                .map { it.substringBefore(',').trim() }
                .filter {
                    it.startsWith("android_native_data.") ||
                        it.startsWith("webview_data.") ||
                        it.startsWith("web_data.")
                }
                .toList()
        }.also { fields ->
            check(fields.size == FIXED_SIGNAL_COUNT) {
                "Expected $FIXED_SIGNAL_COUNT field-status entries, found ${fields.size}"
            }
        }
    }

    fun build(
        payload: JSONObject,
        layerFailures: Map<String, String> = emptyMap(),
        probeStatuses: JSONObject = JSONObject()
    ): JSONObject {
        val fields = JSONObject()
        val counts = linkedMapOf(
            "observed" to 0,
            "unsupported_by_os" to 0,
            "permission_denied" to 0,
            "runtime_error" to 0,
            "timeout" to 0,
            "not_applicable" to 0
        )

        expectedFields.forEach { fieldPath ->
            val layer = fieldPath.substringBefore('.')
            val failure = normalizeFailure(layerFailures[layer])
            val probeFailure = probeFailure(fieldPath, probeStatuses)
            val status = when {
                minimumApi(fieldPath) > Build.VERSION.SDK_INT -> "unsupported_by_os"
                failure != null -> failure
                probeFailure != null -> probeFailure
                hasObservedValue(payload, fieldPath) -> "observed"
                else -> "runtime_error"
            }
            fields.put(fieldPath, status)
            counts[status] = counts.getValue(status) + 1
        }

        return JSONObject().apply {
            put("status_schema_version", STATUS_SCHEMA_VERSION)
            put("android_api", Build.VERSION.SDK_INT)
            put("fixed_signal_count", fields.length())
            put("counts", JSONObject().apply { counts.forEach { (key, value) -> put(key, value) } })
            put(
                "layer_failures",
                JSONObject().apply { layerFailures.forEach { (key, value) -> put(key, value) } }
            )
            put("probe_statuses", probeStatuses)
            put("fields", fields)
        }
    }

    private fun normalizeFailure(value: String?): String? = when (value) {
        "permission_denied" -> "permission_denied"
        "timeout" -> "timeout"
        "not_applicable" -> "not_applicable"
        "runtime_error" -> "runtime_error"
        else -> null
    }

    private fun probeFailure(fieldPath: String, probeStatuses: JSONObject): String? {
        val probeName = when {
            fieldPath.startsWith("webview_data.bridge_routing_layer.") -> "jsbridge"
            fieldPath.startsWith("webview_data.") -> "webview_host"
            fieldPath.startsWith("web_data.navigator_layer.") -> "navigator"
            fieldPath.startsWith("web_data.screen_layer.") -> "screen"
            fieldPath.endsWith(".canvas_hash") -> "canvas"
            fieldPath.startsWith("web_data.graphics_layer.") -> "webgl"
            fieldPath.startsWith("web_data.execution_layer.") -> "execution"
            fieldPath.startsWith("web_data.network_api_layer.") -> "connection"
            fieldPath.startsWith("web_data.audio_layer.") -> "audio"
            fieldPath.startsWith("web_data.font_layer.") -> "font"
            fieldPath.startsWith("web_data.permissions_layer.") -> "permissions"
            fieldPath.startsWith("web_data.automation_surface_layer.") -> "automation"
            else -> return null
        }
        return when (probeStatuses.optString(probeName, "observed")) {
            "timeout" -> "timeout"
            "permission_denied" -> "permission_denied"
            "not_applicable" -> "not_applicable"
            "runtime_error" -> "runtime_error"
            else -> null
        }
    }

    private fun hasObservedValue(root: JSONObject, fieldPath: String): Boolean {
        var current: Any = root
        for (part in fieldPath.split('.')) {
            if (current !is JSONObject || !current.has(part)) return false
            current = current.opt(part) ?: return false
        }
        return current !== JSONObject.NULL
    }

    private fun minimumApi(fieldPath: String): Int = when {
        fieldPath.endsWith("security_patch") -> 23
        fieldPath.contains("screen_mode_") -> 23
        fieldPath.endsWith("link_downstream_kbps") -> 23
        fieldPath.endsWith("link_upstream_kbps") -> 23
        fieldPath.contains("is_cleartext_traffic_permitted") -> 23
        fieldPath.contains("safe_browsing_enabled") -> 26
        fieldPath.contains("webview_provider_") -> 26
        else -> 21
    }

    companion object {
        const val STATUS_SCHEMA_VERSION = "field-status-v1"
        const val FIXED_SIGNAL_COUNT = 177
        private const val FIELD_CATALOG_ASSET = "expanded_v2_field_catalog.csv"
    }
}
