package com.example.hybridguard.featureapp

import android.content.Context
import android.os.Build
import android.os.Process
import android.os.UserManager
import android.webkit.WebView
import org.json.JSONObject
import java.util.UUID

/** Builds non-label metadata used to group repeated collections by device and Android profile. */
class CollectionManifestBuilder(private val context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun build(
        runtimeContext: String,
        collectionRound: Int,
        deviceManifestIdOverride: String?
    ): JSONObject {
        val installId = preferences.getString(INSTALL_ID_KEY, null) ?: UUID.randomUUID().toString().also {
            preferences.edit().putString(INSTALL_ID_KEY, it).apply()
        }
        val uid = Process.myUid()
        val userManager = context.getSystemService(UserManager::class.java)
        val webViewPackage = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WebView.getCurrentWebViewPackage()
        } else {
            null
        }
        val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
        val versionCode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageInfo.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            packageInfo.versionCode.toLong()
        }
        val manifestId = deviceManifestIdOverride
            ?.trim()
            ?.takeIf { it.matches(Regex("[A-Za-z0-9._:-]{1,96}")) }
            ?: installId

        return JSONObject().apply {
            put("manifest_schema_version", "device-profile-manifest-v1")
            put("device_manifest_id", manifestId)
            put("collector_install_id", installId)
            put("runtime_context", runtimeContext.ifBlank { "unspecified" })
            put("collection_round", collectionRound.coerceAtLeast(1))
            put("collection_week", "week7")
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
            put("schema_version", "expanded-v2.1-status")
            put("process_uid", uid)
            put("android_user_id", uid / UID_PER_USER_RANGE)
            put("android_app_id", uid % UID_PER_USER_RANGE)
            put("is_managed_profile", userManager?.isManagedProfile ?: false)
            put("is_system_user", userManager?.isSystemUser ?: false)
        }
    }

    companion object {
        private const val PREFERENCES_NAME = "featureapp_collection_manifest"
        private const val INSTALL_ID_KEY = "collector_install_id"
        private const val UID_PER_USER_RANGE = 100_000
    }
}
