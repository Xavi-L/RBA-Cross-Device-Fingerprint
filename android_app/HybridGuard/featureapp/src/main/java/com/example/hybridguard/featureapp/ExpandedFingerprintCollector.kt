package com.example.hybridguard.featureapp

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.Sensor
import android.hardware.SensorManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.os.SystemClock
import android.provider.Settings
import android.security.NetworkSecurityPolicy
import android.webkit.WebSettings
import android.webkit.WebView
import java.io.File
import java.util.Locale
import java.util.TimeZone
import org.json.JSONArray
import org.json.JSONObject

class ExpandedFingerprintCollector(private val context: Context) {

    fun collectNativeLayered(): JSONObject {
        val actManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        actManager.getMemoryInfo(memInfo)

        val metrics = context.resources.displayMetrics
        val config = context.resources.configuration
        val display = context.display
        val displayMode = display?.mode

        val batteryStatus = context.registerReceiver(
            null,
            IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        )
        val batteryLevel = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val batteryScale = batteryStatus?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val batteryTemp = (batteryStatus?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1) / 10.0
        val batteryVoltage = batteryStatus?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1) ?: -1
        val batteryStatusCode = batteryStatus?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val batteryPlugged = batteryStatus?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
        val batteryHealth = batteryStatus?.getIntExtra(BatteryManager.EXTRA_HEALTH, -1) ?: -1

        val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val sensorList = sensorManager.getSensorList(Sensor.TYPE_ALL)

        val buildLayer = JSONObject().apply {
            put("device_model", Build.MODEL)
            put("device_brand", Build.BRAND)
            put("device_manufacturer", Build.MANUFACTURER)
            put("device_product", Build.PRODUCT)
            put("device_board", Build.BOARD)
            put("device_hardware", Build.HARDWARE)
            put("os_version", "Android ${Build.VERSION.RELEASE}")
            put("os_api_level", Build.VERSION.SDK_INT)
            put("security_patch", Build.VERSION.SECURITY_PATCH)
            put("cpu_abi", Build.SUPPORTED_ABIS.firstOrNull() ?: "unknown")
            put("supported_abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
            put("build_fingerprint", Build.FINGERPRINT)
            put("build_tags", Build.TAGS)
            put("build_type", Build.TYPE)
            put("build_id", Build.ID)
            put("build_display", Build.DISPLAY)
            put("build_bootloader", Build.BOOTLOADER)
            put("build_time_ms", Build.TIME)
            put("kernel_arch", System.getProperty("os.arch") ?: "unknown")
            put("uptime_ms", SystemClock.uptimeMillis())
            put("elapsed_realtime_ms", SystemClock.elapsedRealtime())
        }

        val memoryLayer = JSONObject().apply {
            put("total_memory_gb", memInfo.totalMem / GB)
            put("avail_memory_gb", memInfo.availMem / GB)
            put("memory_threshold_gb", memInfo.threshold / GB)
            put("is_low_memory", memInfo.lowMemory)
        }

        val screenLayer = JSONObject().apply {
            put("screen_resolution_physical", "${metrics.widthPixels}x${metrics.heightPixels}")
            put("screen_density_dpi", metrics.densityDpi)
            put("screen_xdpi", metrics.xdpi.toDouble())
            put("screen_ydpi", metrics.ydpi.toDouble())
            put("screen_scaled_density", metrics.scaledDensity.toDouble())
            put("screen_refresh_rate_hz", display?.refreshRate?.toDouble() ?: -1.0)
            put("screen_mode_physical_width", displayMode?.physicalWidth ?: -1)
            put("screen_mode_physical_height", displayMode?.physicalHeight ?: -1)
            put("screen_mode_refresh_rate_hz", displayMode?.refreshRate?.toDouble() ?: -1.0)
            put("font_scale", config.fontScale.toDouble())
            put("orientation_code", config.orientation)
        }

        val batteryLayer = JSONObject().apply {
            put(
                "battery_level_pct",
                if (batteryLevel >= 0 && batteryScale > 0) batteryLevel * 100.0 / batteryScale else -1.0
            )
            put("battery_temp_celsius", batteryTemp)
            put("battery_voltage_mv", batteryVoltage)
            put("battery_status_code", batteryStatusCode)
            put("battery_health_code", batteryHealth)
            put("battery_plugged_code", batteryPlugged)
            put("battery_technology", batteryStatus?.getStringExtra(BatteryManager.EXTRA_TECHNOLOGY) ?: "unknown")
            put("is_charging", batteryStatusCode == BatteryManager.BATTERY_STATUS_CHARGING)
        }

        val sensorTypes = sensorList.map { it.type }.distinct().sorted()
        val sensorVendors = sensorList.map { it.vendor }.filter { it.isNotBlank() }.distinct()
        val sensorLayer = JSONObject().apply {
            put("sensor_total_count", sensorList.size)
            put("sensor_type_list", JSONArray(sensorTypes))
            put("sensor_vendor_count", sensorVendors.size)
            put("sensor_name_count", sensorList.map { it.name }.distinct().size)
            put("has_gyroscope", hasSensor(sensorManager, Sensor.TYPE_GYROSCOPE))
            put("has_accelerometer", hasSensor(sensorManager, Sensor.TYPE_ACCELEROMETER))
            put("has_magnetic_field", hasSensor(sensorManager, Sensor.TYPE_MAGNETIC_FIELD))
            put("has_light_sensor", hasSensor(sensorManager, Sensor.TYPE_LIGHT))
            put("has_proximity_sensor", hasSensor(sensorManager, Sensor.TYPE_PROXIMITY))
            put("has_pressure_sensor", hasSensor(sensorManager, Sensor.TYPE_PRESSURE))
            put("has_gravity_sensor", hasSensor(sensorManager, Sensor.TYPE_GRAVITY))
            put("has_rotation_vector", hasSensor(sensorManager, Sensor.TYPE_ROTATION_VECTOR))
            put("has_step_counter", hasSensor(sensorManager, Sensor.TYPE_STEP_COUNTER))
            put("has_step_detector", hasSensor(sensorManager, Sensor.TYPE_STEP_DETECTOR))
        }

        val securityLayer = JSONObject().apply {
            put("is_adb_enabled", globalInt(Settings.Global.ADB_ENABLED) == 1)
            put("developer_options_enabled", globalInt(Settings.Global.DEVELOPMENT_SETTINGS_ENABLED) == 1)
            put("http_proxy_setting", Settings.Global.getString(context.contentResolver, Settings.Global.HTTP_PROXY) ?: "")
            put("java_http_proxy_host", System.getProperty("http.proxyHost") ?: "")
            put("java_http_proxy_port", System.getProperty("http.proxyPort") ?: "")
            put("su_binary_present", SU_PATHS.any { File(it).exists() })
        }

        val storageStats = StatFs(Environment.getDataDirectory().path)
        val storageLayer = JSONObject().apply {
            put("data_storage_total_gb", storageStats.blockSizeLong * storageStats.blockCountLong / GB)
            put("data_storage_free_gb", storageStats.blockSizeLong * storageStats.availableBlocksLong / GB)
        }

        val localeLayer = JSONObject().apply {
            put("native_locale", Locale.getDefault().toLanguageTag())
            put("native_language", Locale.getDefault().language)
            put("native_country", Locale.getDefault().country)
            put("native_timezone_id", TimeZone.getDefault().id)
            put("native_timezone_offset_min", TimeZone.getDefault().rawOffset / 60000)
        }

        val networkLayer = collectNetworkLayer()

        return JSONObject().apply {
            put("build_fingerprint_layer", buildLayer)
            put("memory_layer", memoryLayer)
            put("screen_display_layer", screenLayer)
            put("battery_dynamics_layer", batteryLayer)
            put("sensor_matrix_layer", sensorLayer)
            put("security_config_layer", securityLayer)
            put("storage_layer", storageLayer)
            put("locale_timezone_layer", localeLayer)
            put("network_state_layer", networkLayer)
        }
    }

    fun collectWebViewHostFlat(settingsSnapshot: JSONObject): JSONObject {
        val features = JSONObject()
        try {
            val isDebuggable =
                (context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
            features.put("is_debuggable", isDebuggable)
            features.put("app_package_name", context.packageName)

            val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            features.put("app_version_name", packageInfo.versionName ?: "")
            features.put("app_version_code", packageInfo.longVersionCode)

            val installerName = try {
                context.packageManager.getInstallerPackageName(context.packageName) ?: "manual"
            } catch (e: Exception) {
                "unknown"
            }
            features.put("installer_package", installerName)

            WebView.getCurrentWebViewPackage()?.let { webViewPackage ->
                features.put("webview_provider_package", webViewPackage.packageName)
                features.put("webview_provider_version", webViewPackage.versionName)
                features.put("webview_provider_version_code", webViewPackage.longVersionCode)
                features.put("webview_provider_major", parseMajor(webViewPackage.versionName))
            }

            features.put("default_ua_native", WebSettings.getDefaultUserAgent(context))
            features.put("system_http_agent", System.getProperty("http.agent") ?: "unknown")
            features.put(
                "is_cleartext_traffic_permitted",
                NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted
            )

            features.put("first_install_time", packageInfo.firstInstallTime)
            features.put("last_update_time", packageInfo.lastUpdateTime)
            features.put("target_sdk_version", context.applicationInfo.targetSdkVersion)
            features.put("min_sdk_version", context.applicationInfo.minSdkVersion)

            val keys = settingsSnapshot.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                features.put(key, settingsSnapshot.opt(key))
            }
        } catch (e: Exception) {
            features.put("error_msg", e.message ?: "unknown")
        }
        return features
    }

    private fun collectNetworkLayer(): JSONObject {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork
        val caps = network?.let { cm.getNetworkCapabilities(it) }

        val transports = mutableListOf<String>()
        if (caps != null) {
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) transports.add("wifi")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) transports.add("cellular")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) transports.add("vpn")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) transports.add("ethernet")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH)) transports.add("bluetooth")
        }

        return JSONObject().apply {
            put("active_network_present", network != null)
            put("active_transport_types", JSONArray(transports))
            put("network_metered", cm.isActiveNetworkMetered)
            put("has_vpn_transport", caps?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ?: false)
            put("has_wifi_transport", caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ?: false)
            put("has_cellular_transport", caps?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ?: false)
            put("link_downstream_kbps", caps?.linkDownstreamBandwidthKbps ?: -1)
            put("link_upstream_kbps", caps?.linkUpstreamBandwidthKbps ?: -1)
        }
    }

    private fun globalInt(name: String): Int {
        return try {
            Settings.Global.getInt(context.contentResolver, name, 0)
        } catch (e: Exception) {
            0
        }
    }

    private fun hasSensor(sensorManager: SensorManager, type: Int): Boolean {
        return sensorManager.getDefaultSensor(type) != null
    }

    private fun parseMajor(version: String?): Int {
        val text = version ?: return -1
        val prefix = text.substringBefore(".")
        return prefix.toIntOrNull() ?: -1
    }

    companion object {
        private const val GB = 1024.0 * 1024.0 * 1024.0
        private val SU_PATHS = listOf(
            "/system/bin/su",
            "/system/xbin/su",
            "/sbin/su",
            "/vendor/bin/su"
        )

        fun webViewSettingsSnapshot(webView: WebView): JSONObject {
            val settings = webView.settings
            return JSONObject().apply {
                put("java_script_enabled", settings.javaScriptEnabled)
                put("dom_storage_enabled", settings.domStorageEnabled)
                put("database_enabled", settings.databaseEnabled)
                put("allow_file_access", settings.allowFileAccess)
                put("allow_content_access", settings.allowContentAccess)
                put("mixed_content_mode", settings.mixedContentMode)
                put("safe_browsing_enabled", settings.safeBrowsingEnabled)
                put("settings_user_agent", settings.userAgentString ?: "")
            }
        }
    }
}

