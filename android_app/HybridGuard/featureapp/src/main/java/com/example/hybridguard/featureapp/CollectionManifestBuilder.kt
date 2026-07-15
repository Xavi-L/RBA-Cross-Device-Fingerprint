package com.example.hybridguard.featureapp

import android.content.Context
import android.os.Build
import android.os.Process
import android.os.UserManager
import android.webkit.WebView
import java.util.UUID
import org.json.JSONObject

/**
 * Creates non-label collection context for grouping repeated samples by Android profile.
 *
 * The generated install id is persisted in this app's private storage. A cloud-device
 * orchestrator may pass a provider-side stable id with [EXTRA_DEVICE_MANIFEST_ID] when it
 * has one; otherwise the install id remains the grouping id for this app/profile.
 */
class CollectionManifestBuilder(private val context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun build(
        runtimeContext: String,
        collectionRound: Int,
        deviceManifestIdOverride: String?
    ): JSONObject {
        val installId = preferences.getString(INSTALL_ID_KEY, null)
            ?: UUID.randomUUID().toString().also {
                preferences.edit().putString(INSTALL_ID_KEY, it).apply()
            }
        val uid = Process.myUid()
        val userManager = context.getSystemService(Context.USER_SERVICE) as? UserManager
        val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
        val webViewPackage = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WebView.getCurrentWebViewPackage()
        } else {
            null
        }
        val versionCode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageInfo.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            packageInfo.versionCode.toLong()
        }
        val managedProfile = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            userManager?.isManagedProfile
        } else {
            null
        }
        val systemUser = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            userManager?.isSystemUser
        } else {
            null
        }
        val manifestId = deviceManifestIdOverride
            ?.trim()
            ?.takeIf { it.matches(DEVICE_MANIFEST_ID_PATTERN) }
            ?: installId

        return JSONObject().apply {
            put("manifest_schema_version", MANIFEST_SCHEMA_VERSION)
            put("collection_protocol_version", COLLECTION_PROTOCOL_VERSION)
            put("collection_started_at_ms", System.currentTimeMillis())
            put("device_manifest_id", manifestId)
            put("collector_install_id", installId)
            put("runtime_context", runtimeContext.trim().ifBlank { "unspecified" })
            put("collection_round", collectionRound.coerceAtLeast(1))
            put("manufacturer", Build.MANUFACTURER)
            put("brand", Build.BRAND)
            put("model", Build.MODEL)
            put("device", Build.DEVICE)
            put("android_api", Build.VERSION.SDK_INT)
            put("android_release", Build.VERSION.RELEASE)
            put("webview_provider_package", webViewPackage?.packageName ?: JSONObject.NULL)
            put("webview_provider_version", webViewPackage?.versionName ?: JSONObject.NULL)
            put("collector_package", context.packageName)
            put("collector_version_name", packageInfo.versionName ?: JSONObject.NULL)
            put("collector_version_code", versionCode)
            put("schema_version", FEATURE_SCHEMA_VERSION)
            put("minimum_supported_android_api", MINIMUM_SUPPORTED_ANDROID_API)
            put(
                "api_compatibility_mode",
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) "legacy_api21_22_fallbacks" else "guarded_modern_api"
            )
            put("process_uid", uid)
            put("android_user_id", uid / UID_PER_USER_RANGE)
            put("android_app_id", uid % UID_PER_USER_RANGE)
            put("is_managed_profile", managedProfile ?: JSONObject.NULL)
            put("is_system_user", systemUser ?: JSONObject.NULL)
            put(
                "profile_api_status",
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) "observed" else "unsupported_by_os"
            )
            put(
                "webview_provider_api_status",
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) "observed" else "unsupported_by_os"
            )
        }
    }

    companion object {
        const val MANIFEST_SCHEMA_VERSION = "device-profile-manifest-v1"
        const val COLLECTION_PROTOCOL_VERSION = "featureapp-collection-protocol-v2"
        const val FEATURE_SCHEMA_VERSION = "expanded-v2.2-status"
        const val MINIMUM_SUPPORTED_ANDROID_API = 21
        const val EXTRA_DEVICE_MANIFEST_ID =
            "com.example.hybridguard.featureapp.DEVICE_MANIFEST_ID"
        const val EXTRA_RUNTIME_CONTEXT =
            "com.example.hybridguard.featureapp.RUNTIME_CONTEXT"
        const val EXTRA_COLLECTION_ROUND =
            "com.example.hybridguard.featureapp.COLLECTION_ROUND"

        private const val PREFERENCES_NAME = "featureapp_collection_manifest"
        private const val INSTALL_ID_KEY = "collector_install_id"
        private const val UID_PER_USER_RANGE = 100_000
        private val DEVICE_MANIFEST_ID_PATTERN = Regex("[A-Za-z0-9._:-]{1,96}")
    }
}
