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
import android.opengl.EGL14
import android.opengl.EGLConfig
import android.opengl.EGLContext
import android.opengl.EGLDisplay
import android.opengl.EGLSurface
import android.opengl.GLES20
import android.provider.Settings
import android.security.NetworkSecurityPolicy
import android.webkit.WebSettings
import android.webkit.WebView
import android.view.WindowManager
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
        val display = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            context.display
        } else {
            @Suppress("DEPRECATION")
            (context.getSystemService(Context.WINDOW_SERVICE) as WindowManager).defaultDisplay
        }
        val modePhysicalWidth = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            display?.mode?.physicalWidth
        } else {
            null
        }
        val modePhysicalHeight = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            display?.mode?.physicalHeight
        } else {
            null
        }
        val modeRefreshRate = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            display?.mode?.refreshRate?.toDouble()
        } else {
            null
        }

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
            put(
                "security_patch",
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) Build.VERSION.SECURITY_PATCH else JSONObject.NULL
            )
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
            put("screen_mode_physical_width", modePhysicalWidth ?: JSONObject.NULL)
            put("screen_mode_physical_height", modePhysicalHeight ?: JSONObject.NULL)
            put("screen_mode_refresh_rate_hz", modeRefreshRate ?: JSONObject.NULL)
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
        val graphicsLayer = collectNativeGraphicsLayer()

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
            put("graphics_layer", graphicsLayer)
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
            features.put("app_version_code", packageVersionCode(packageInfo))

            val installerName = try {
                context.packageManager.getInstallerPackageName(context.packageName) ?: "manual"
            } catch (e: Exception) {
                "unknown"
            }
            features.put("installer_package", installerName)

            val webViewPackage = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WebView.getCurrentWebViewPackage()
            } else {
                null
            }
            webViewPackage?.let {
                features.put("webview_provider_package", webViewPackage.packageName)
                features.put("webview_provider_version", webViewPackage.versionName)
                features.put("webview_provider_version_code", packageVersionCode(webViewPackage))
                features.put("webview_provider_major", parseMajor(webViewPackage.versionName))
            }
            if (webViewPackage == null) {
                features.put("webview_provider_package", JSONObject.NULL)
                features.put("webview_provider_version", JSONObject.NULL)
                features.put("webview_provider_version_code", JSONObject.NULL)
                features.put("webview_provider_major", JSONObject.NULL)
            }

            features.put("default_ua_native", WebSettings.getDefaultUserAgent(context))
            features.put("system_http_agent", System.getProperty("http.agent") ?: "unknown")
            features.put(
                "is_cleartext_traffic_permitted",
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted
                } else {
                    JSONObject.NULL
                }
            )

            features.put("first_install_time", packageInfo.firstInstallTime)
            features.put("last_update_time", packageInfo.lastUpdateTime)
            features.put("target_sdk_version", context.applicationInfo.targetSdkVersion)
            features.put("min_sdk_version", CollectionManifestBuilder.MINIMUM_SUPPORTED_ANDROID_API)

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
        val network = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) cm.activeNetwork else null
        val caps = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            network?.let { cm.getNetworkCapabilities(it) }
        } else {
            null
        }
        @Suppress("DEPRECATION")
        val legacyInfo = if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) cm.activeNetworkInfo else null

        val transports = mutableListOf<String>()
        if (caps != null) {
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) transports.add("wifi")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) transports.add("cellular")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) transports.add("vpn")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) transports.add("ethernet")
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_BLUETOOTH)) transports.add("bluetooth")
        } else if (legacyInfo?.isConnected == true) {
            @Suppress("DEPRECATION")
            when (legacyInfo.type) {
                ConnectivityManager.TYPE_WIFI -> transports.add("wifi")
                ConnectivityManager.TYPE_MOBILE -> transports.add("cellular")
                ConnectivityManager.TYPE_ETHERNET -> transports.add("ethernet")
                ConnectivityManager.TYPE_BLUETOOTH -> transports.add("bluetooth")
                else -> transports.add("other")
            }
        }

        return JSONObject().apply {
            put("active_network_present", network != null || legacyInfo?.isConnected == true)
            put("active_transport_types", JSONArray(transports))
            put("network_metered", cm.isActiveNetworkMetered)
            put("has_vpn_transport", caps?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ?: false)
            put("has_wifi_transport", caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ?: false)
            put("has_cellular_transport", caps?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ?: false)
            put(
                "link_downstream_kbps",
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) caps?.linkDownstreamBandwidthKbps ?: -1 else JSONObject.NULL
            )
            put(
                "link_upstream_kbps",
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) caps?.linkUpstreamBandwidthKbps ?: -1 else JSONObject.NULL
            )
        }
    }

    private fun collectNativeGraphicsLayer(): JSONObject {
        val result = JSONObject().apply {
            put("native_gpu_vendor", JSONObject.NULL)
            put("native_gpu_renderer", JSONObject.NULL)
            put("egl_vendor", JSONObject.NULL)
            put("egl_renderer", JSONObject.NULL)
            put("gles_version", JSONObject.NULL)
        }

        var display: EGLDisplay? = null
        var context: EGLContext? = null
        var surface: EGLSurface? = null

        try {
            display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY)
            if (display == EGL14.EGL_NO_DISPLAY) {
                throw IllegalStateException("EGL display unavailable")
            }

            val version = IntArray(2)
            if (!EGL14.eglInitialize(display, version, 0, version, 1)) {
                throw IllegalStateException("EGL initialize failed")
            }

            result.put("egl_vendor", EGL14.eglQueryString(display, EGL14.EGL_VENDOR) ?: JSONObject.NULL)

            val configAttribs = intArrayOf(
                EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT,
                EGL14.EGL_RED_SIZE, 8,
                EGL14.EGL_GREEN_SIZE, 8,
                EGL14.EGL_BLUE_SIZE, 8,
                EGL14.EGL_ALPHA_SIZE, 8,
                EGL14.EGL_NONE
            )
            val configs = arrayOfNulls<EGLConfig>(1)
            val configCount = IntArray(1)
            val hasConfig = EGL14.eglChooseConfig(
                display,
                configAttribs,
                0,
                configs,
                0,
                configs.size,
                configCount,
                0
            )
            val config = configs.firstOrNull()
            if (!hasConfig || configCount[0] == 0 || config == null) {
                throw IllegalStateException("EGL config unavailable")
            }

            context = EGL14.eglCreateContext(
                display,
                config,
                EGL14.EGL_NO_CONTEXT,
                intArrayOf(EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE),
                0
            )
            if (context == EGL14.EGL_NO_CONTEXT) {
                throw IllegalStateException("EGL context unavailable")
            }

            surface = EGL14.eglCreatePbufferSurface(
                display,
                config,
                intArrayOf(EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE),
                0
            )
            if (surface == EGL14.EGL_NO_SURFACE) {
                throw IllegalStateException("EGL surface unavailable")
            }

            if (!EGL14.eglMakeCurrent(display, surface, surface, context)) {
                throw IllegalStateException("EGL makeCurrent failed")
            }

            val glVendor = GLES20.glGetString(GLES20.GL_VENDOR)
            val glRenderer = GLES20.glGetString(GLES20.GL_RENDERER)
            result.put("native_gpu_vendor", glVendor ?: JSONObject.NULL)
            result.put("native_gpu_renderer", glRenderer ?: JSONObject.NULL)
            result.put("egl_renderer", glRenderer ?: JSONObject.NULL)
            result.put("gles_version", GLES20.glGetString(GLES20.GL_VERSION) ?: JSONObject.NULL)
        } catch (e: Exception) {
            result.put("graphics_probe_error", e.message ?: e.javaClass.simpleName)
        } finally {
            val eglDisplay = display
            if (eglDisplay != null && eglDisplay != EGL14.EGL_NO_DISPLAY) {
                EGL14.eglMakeCurrent(
                    eglDisplay,
                    EGL14.EGL_NO_SURFACE,
                    EGL14.EGL_NO_SURFACE,
                    EGL14.EGL_NO_CONTEXT
                )
                val eglSurface = surface
                if (eglSurface != null && eglSurface != EGL14.EGL_NO_SURFACE) {
                    EGL14.eglDestroySurface(eglDisplay, eglSurface)
                }
                val eglContext = context
                if (eglContext != null && eglContext != EGL14.EGL_NO_CONTEXT) {
                    EGL14.eglDestroyContext(eglDisplay, eglContext)
                }
                EGL14.eglTerminate(eglDisplay)
            }
        }

        return result
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

    private fun packageVersionCode(packageInfo: android.content.pm.PackageInfo): Long {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageInfo.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            packageInfo.versionCode.toLong()
        }
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
                put(
                    "safe_browsing_enabled",
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) settings.safeBrowsingEnabled else JSONObject.NULL
                )
                put("settings_user_agent", settings.userAgentString ?: "")
            }
        }
    }
}
