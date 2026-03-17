package com.example.hybridguard

import android.webkit.JavascriptInterface
import android.content.Context

// 🚀 注意这里：新增了 val context: Context，让这个类拥有了调用系统底层的权限！
class WebAppInterface(private val context: Context, private val sessionId: String) {

    @JavascriptInterface
    fun getSessionId(): String {
        return sessionId
    }

    // 🚀 终极版：WebView 容器与宿主环境全量探针 (近 20 个维度)
    @JavascriptInterface
    fun getWebViewSecurityFeatures(): String {
        val features = org.json.JSONObject()
        try {
            // --- 1. 基础安全状态 ---
            val isDebuggable = (context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
            features.put("is_debuggable", isDebuggable)
            features.put("app_package_name", context.packageName)

            val installerName = try {
                context.packageManager.getInstallerPackageName(context.packageName) ?: "manual"
            } catch (e: Exception) { "unknown" }
            features.put("installer_package", installerName)

            // --- 2. WebView 内核真实溯源 ---
            if (android.os.Build.VERSION.SDK_INT >= 26) {
                android.webkit.WebView.getCurrentWebViewPackage()?.let { webViewPackage ->
                    features.put("webview_provider_package", webViewPackage.packageName)
                    features.put("webview_provider_version", webViewPackage.versionName)
                    if (android.os.Build.VERSION.SDK_INT >= 28) {
                        features.put("webview_provider_version_code", webViewPackage.longVersionCode)
                    }
                }
            }

            // --- 3. 容器原生 UA 嗅探 (防魔改浏览器内核) ---
            val defaultUA = try {
                android.webkit.WebSettings.getDefaultUserAgent(context)
            } catch (e: Exception) { "unknown" }
            features.put("default_ua_native", defaultUA)
            features.put("is_cleartext_traffic_permitted", android.security.NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted)

            // --- 4. 宿主 App 时间维度 ---
            val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            features.put("first_install_time", packageInfo.firstInstallTime)
            features.put("last_update_time", packageInfo.lastUpdateTime)

            // --- 5. 编译环境维度 ---
            features.put("target_sdk_version", context.applicationInfo.targetSdkVersion)
            if (android.os.Build.VERSION.SDK_INT >= 24) {
                features.put("min_sdk_version", context.applicationInfo.minSdkVersion)
            }

            // --- 6. 底层网络 UA ---
            features.put("system_http_agent", System.getProperty("http.agent") ?: "unknown")

        } catch (e: Exception) {
            features.put("error_msg", e.message)
        }
        return features.toString()
    }
}