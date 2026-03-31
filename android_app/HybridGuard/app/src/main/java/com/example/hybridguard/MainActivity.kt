package com.example.hybridguard

import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import java.util.UUID
import kotlin.concurrent.thread
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

class MainActivity : AppCompatActivity() {

    private val sessionId = UUID.randomUUID().toString()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        collectAndSendNativeData()

        val myWebView: WebView = findViewById(R.id.webview)
        myWebView.settings.javaScriptEnabled = true
        myWebView.webViewClient = WebViewClient()

        // 注入 JSBridge
        myWebView.addJavascriptInterface(WebAppInterface(this, sessionId), "AndroidBridge")
        // 构造一个包含绕过特征的 Header Map
        val extraHeaders = mutableMapOf<String, String>()
        extraHeaders["ngrok-skip-browser-warning"] = "true"
        // 加载探针网页
        myWebView.loadUrl("https://hemispheric-overmoist-candance.ngrok-free.dev", extraHeaders)
    }

    private fun collectAndSendNativeData() {
        thread {
            try {
                // ==========================================
                // 🚀 1. 史诗级原生硬件与物理探针库 (分层架构版)
                // ==========================================

                // --- A. 深度构建指纹层 ---
                val buildLayer = org.json.JSONObject().apply {
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
                }

                // --- B. 真实内存探测层 ---
                val actManager = getSystemService(ACTIVITY_SERVICE) as android.app.ActivityManager
                val memInfo = android.app.ActivityManager.MemoryInfo()
                actManager.getMemoryInfo(memInfo)
                val memoryLayer = org.json.JSONObject().apply {
                    put("total_memory_gb", memInfo.totalMem / (1024.0 * 1024.0 * 1024.0))
                    put("avail_memory_gb", memInfo.availMem / (1024.0 * 1024.0 * 1024.0))
                    put("is_low_memory", memInfo.lowMemory)
                }

                // --- C. 物理屏幕深度层 ---
                val metrics = resources.displayMetrics
                val screenLayer = org.json.JSONObject().apply {
                    put("screen_resolution_physical", "${metrics.widthPixels}x${metrics.heightPixels}")
                    put("screen_density_dpi", metrics.densityDpi)
                    put("screen_xdpi", metrics.xdpi.toDouble())
                    put("screen_ydpi", metrics.ydpi.toDouble())
                    put("screen_scaled_density", metrics.scaledDensity.toDouble())
                }

                // --- D. 电池动态物理层 ---
                val batteryStatus = registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))
                val batteryLevel = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1) ?: -1
                val batteryScale = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1) ?: -1
                val batteryTemp = (batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1) / 10.0
                val batteryVoltage = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_VOLTAGE, -1) ?: -1
                val isCharging = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1) == android.os.BatteryManager.BATTERY_STATUS_CHARGING
                val batteryLayer = org.json.JSONObject().apply {
                    put("battery_level_pct", if (batteryLevel >= 0 && batteryScale > 0) (batteryLevel * 100f / batteryScale).toDouble() else -1.0)
                    put("battery_temp_celsius", batteryTemp)
                    put("battery_voltage_mv", batteryVoltage)
                    put("is_charging", isCharging)
                }

                // --- E. 传感器全局矩阵层 ---
                val sensorManager = getSystemService(SENSOR_SERVICE) as android.hardware.SensorManager
                val sensorList = sensorManager.getSensorList(android.hardware.Sensor.TYPE_ALL)
                val sensorLayer = org.json.JSONObject().apply {
                    put("sensor_total_count", sensorList.size)
                    put("has_gyroscope", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_GYROSCOPE) != null)
                    put("has_accelerometer", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_ACCELEROMETER) != null)
                    put("has_magnetic_field", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_MAGNETIC_FIELD) != null)
                    put("has_light_sensor", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_LIGHT) != null)
                    put("has_proximity_sensor", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_PROXIMITY) != null)
                    put("has_pressure_sensor", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_PRESSURE) != null)
                }

                // --- F. 系统底层安全层 ---
                val adbEnabled = android.provider.Settings.Global.getInt(contentResolver, android.provider.Settings.Global.ADB_ENABLED, 0) == 1
                val securityLayer = org.json.JSONObject().apply {
                    put("is_adb_enabled", adbEnabled)
                }

                // 👇 核心拼装：把 6 个子层组装成最终的嵌套 JSON 对象
                val nativeDataJson = org.json.JSONObject().apply {
                    put("build_fingerprint_layer", buildLayer)
                    put("memory_layer", memoryLayer)
                    put("screen_display_layer", screenLayer)
                    put("battery_dynamics_layer", batteryLayer)
                    put("sensor_matrix_layer", sensorLayer)
                    put("security_config_layer", securityLayer)
                }

                // ==========================================
                // 🚀 2. 组装 Payload 数据包
                // ==========================================
                val payload = org.json.JSONObject().apply {
                    put("session_id", sessionId)
                    put("timestamp", System.currentTimeMillis() / 1000)
                    put("android_native_data", nativeDataJson)
                }

                // ==========================================
                // 🚀 3. 发送网络请求到 FastAPI 后端
                // ==========================================
                val client = okhttp3.OkHttpClient()

                // 👇 最现代、最优雅的 Kotlin 写法，彻底告别红线和废弃警告！
                val mediaType = "application/json; charset=utf-8".toMediaType()
                val body = payload.toString().toRequestBody(mediaType)

                // ... 前面的拼装 body 代码保持不变 ...

                val request = okhttp3.Request.Builder()
                    .url("https://hemispheric-overmoist-candance.ngrok-free.dev/api/collect/fingerprint")
                    // 👇 加入这行神仙代码，直接无视 Ngrok 的警告页面！
                    .addHeader("ngrok-skip-browser-warning", "true")
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()

                if (response.isSuccessful) {
                    println("✅ 原生全量数据 POST 成功！Session ID: $sessionId")
                } else {
                    println("❌ 原生数据 POST 失败，状态码: ${response.code}")
                }
            } catch (e: Exception) {
                println("❌ 网络请求异常: ${e.message}")
            }
        }
    }
}