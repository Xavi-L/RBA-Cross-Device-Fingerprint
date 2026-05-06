package com.example.hybridguard.riskapp

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.Sensor
import android.hardware.SensorManager
import android.os.BatteryManager
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import android.security.NetworkSecurityPolicy
import android.webkit.WebSettings
import android.webkit.WebView
import org.json.JSONObject

class FingerprintCollector(private val context: Context) {

    fun collectNativeFlat(): JSONObject {
        val actManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        actManager.getMemoryInfo(memInfo)

        val metrics = context.resources.displayMetrics

        val batteryStatus = context.registerReceiver(
            null,
            IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        )
        val batteryLevel = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val batteryScale = batteryStatus?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val batteryTemp = (batteryStatus?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1) / 10.0
        val batteryVoltage = batteryStatus?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1) ?: -1
        val isCharging = batteryStatus?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) == BatteryManager.BATTERY_STATUS_CHARGING

        val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val sensorList = sensorManager.getSensorList(Sensor.TYPE_ALL)
        val adbEnabled = Settings.Global.getInt(context.contentResolver, Settings.Global.ADB_ENABLED, 0) == 1

        return JSONObject().apply {
            put("device_model", Build.MODEL)
            put("device_brand", Build.BRAND)
            put("device_manufacturer", Build.MANUFACTURER)
            put("device_product", Build.PRODUCT)
            put("device_board", Build.BOARD)
            put("device_hardware", Build.HARDWARE)
            put("os_version", "Android ${Build.VERSION.RELEASE}")
            put("os_api_level", Build.VERSION.SDK_INT)
            put("cpu_abi", Build.SUPPORTED_ABIS.firstOrNull() ?: "unknown")
            put("build_fingerprint", Build.FINGERPRINT)
            put("build_tags", Build.TAGS)
            put("build_type", Build.TYPE)
            put("uptime_ms", SystemClock.uptimeMillis())
            put("total_memory_gb", memInfo.totalMem / (1024.0 * 1024.0 * 1024.0))
            put("avail_memory_gb", memInfo.availMem / (1024.0 * 1024.0 * 1024.0))
            put("is_low_memory", memInfo.lowMemory)
            put("screen_resolution_physical", "${metrics.widthPixels}x${metrics.heightPixels}")
            put("screen_density_dpi", metrics.densityDpi)
            put("screen_xdpi", metrics.xdpi.toDouble())
            put("screen_ydpi", metrics.ydpi.toDouble())
            put("screen_scaled_density", metrics.scaledDensity.toDouble())
            put(
                "battery_level_pct",
                if (batteryLevel >= 0 && batteryScale > 0) batteryLevel * 100.0 / batteryScale else -1.0
            )
            put("battery_temp_celsius", batteryTemp)
            put("battery_voltage_mv", batteryVoltage)
            put("is_charging", isCharging)
            put("sensor_total_count", sensorList.size)
            put("has_gyroscope", sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE) != null)
            put("has_accelerometer", sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) != null)
            put("has_magnetic_field", sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD) != null)
            put("has_light_sensor", sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT) != null)
            put("has_proximity_sensor", sensorManager.getDefaultSensor(Sensor.TYPE_PROXIMITY) != null)
            put("has_pressure_sensor", sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE) != null)
            put("is_adb_enabled", adbEnabled)
        }
    }

    fun collectWebViewSecurityFlat(): JSONObject {
        val features = JSONObject()
        try {
            val isDebuggable =
                (context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
            features.put("is_debuggable", isDebuggable)
            features.put("app_package_name", context.packageName)

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
            }

            val defaultUA = try {
                WebSettings.getDefaultUserAgent(context)
            } catch (e: Exception) {
                "unknown"
            }
            features.put("default_ua_native", defaultUA)
            features.put("system_http_agent", System.getProperty("http.agent") ?: "unknown")
            features.put(
                "is_cleartext_traffic_permitted",
                NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted
            )

            val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            features.put("first_install_time", packageInfo.firstInstallTime)
            features.put("last_update_time", packageInfo.lastUpdateTime)
            features.put("target_sdk_version", context.applicationInfo.targetSdkVersion)
            features.put("min_sdk_version", context.applicationInfo.minSdkVersion)
        } catch (e: Exception) {
            features.put("error_msg", e.message ?: "unknown")
        }
        return features
    }

    companion object {
        fun flattenLayers(layered: JSONObject?): JSONObject {
            val flat = JSONObject()
            if (layered == null) return flat

            val keys = layered.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val value = layered.opt(key)
                if (value is JSONObject) {
                    val innerKeys = value.keys()
                    while (innerKeys.hasNext()) {
                        val innerKey = innerKeys.next()
                        flat.put(innerKey, value.opt(innerKey))
                    }
                }
            }
            return flat
        }
    }
}
