package com.example.hybridguard.featureapp

import android.content.Context
import android.os.Build
import org.json.JSONObject

/** Keeps collection availability metadata separate from the fixed 177 signal values. */
class FieldStatusReporter(private val context: Context) {
    fun build(payload: JSONObject, layerFailures: Map<String, String>): JSONObject {
        val fields = JSONObject()
        val counts = linkedMapOf(
            "observed" to 0,
            "unsupported_by_os" to 0,
            "permission_denied" to 0,
            "runtime_error" to 0,
            "timeout" to 0,
            "not_applicable" to 0
        )

        expectedFields().forEach { field ->
            val layer = field.substringBefore('.')
            val failure = layerFailures[layer]
            val status = when {
                hasObservedValue(payload, field) -> "observed"
                minimumApi(field) > Build.VERSION.SDK_INT -> "unsupported_by_os"
                failure == "permission_denied" -> "permission_denied"
                failure == "timeout" -> "timeout"
                failure == "not_applicable" -> "not_applicable"
                else -> "runtime_error"
            }
            fields.put(field, status)
            counts[status] = counts.getValue(status) + 1
        }

        return JSONObject().apply {
            put("status_schema_version", "field-status-v1")
            put("android_api", Build.VERSION.SDK_INT)
            put("fixed_signal_count", fields.length())
            put("counts", JSONObject(counts as Map<*, *>))
            put("layer_failures", JSONObject(layerFailures))
            put("fields", fields)
        }
    }

    private fun expectedFields(): List<String> = context.assets
        .open("expanded_v2_field_catalog.csv")
        .bufferedReader()
        .useLines { lines ->
            lines.drop(1)
                .map { it.substringBefore(',').trim() }
                .filter {
                    it.startsWith("android_native_data.") ||
                        it.startsWith("webview_data.") ||
                        it.startsWith("web_data.")
                }
                .toList()
        }

    private fun hasObservedValue(root: JSONObject, fieldPath: String): Boolean {
        var current: Any = root
        for (part in fieldPath.split('.')) {
            if (current !is JSONObject || !current.has(part)) return false
            current = current.opt(part) ?: return false
        }
        return current !== JSONObject.NULL
    }

    private fun minimumApi(field: String): Int = when {
        field.endsWith("min_sdk_version") -> 24
        field.contains("safe_browsing_enabled") -> 26
        field.contains("webview_provider_") -> 26
        else -> 21
    }
}
