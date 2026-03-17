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
        // 加载探针网页
        myWebView.loadUrl("http://10.0.2.2:5500/index.html")
    }

    private fun collectAndSendNativeData() {
        thread {
            try {
                // ==========================================
                // 🚀 1. 史诗级原生硬件与物理探针库 (40+ 维度)
                // ==========================================
                val nativeDataJson = org.json.JSONObject()

                // --- A. 深度构建指纹 (Build Properties) ---
                nativeDataJson.put("device_model", Build.MODEL)
                nativeDataJson.put("device_brand", Build.BRAND)
                nativeDataJson.put("device_manufacturer", Build.MANUFACTURER)
                nativeDataJson.put("device_product", Build.PRODUCT)
                nativeDataJson.put("device_board", Build.BOARD)
                nativeDataJson.put("device_hardware", Build.HARDWARE)
                nativeDataJson.put("os_version", "Android ${Build.VERSION.RELEASE}")
                nativeDataJson.put("os_api_level", Build.VERSION.SDK_INT)
                nativeDataJson.put("cpu_abi", Build.SUPPORTED_ABIS.firstOrNull() ?: "unknown")
                nativeDataJson.put("build_fingerprint", Build.FINGERPRINT)
                nativeDataJson.put("build_tags", Build.TAGS)
                nativeDataJson.put("build_type", Build.TYPE)
                nativeDataJson.put("uptime_ms", SystemClock.uptimeMillis())

                // --- B. 真实内存探测 (ActivityManager) ---
                val actManager = getSystemService(ACTIVITY_SERVICE) as android.app.ActivityManager
                val memInfo = android.app.ActivityManager.MemoryInfo()
                actManager.getMemoryInfo(memInfo)
                nativeDataJson.put("total_memory_gb", memInfo.totalMem / (1024.0 * 1024.0 * 1024.0))
                nativeDataJson.put("avail_memory_gb", memInfo.availMem / (1024.0 * 1024.0 * 1024.0))
                nativeDataJson.put("is_low_memory", memInfo.lowMemory)

                // --- C. 物理屏幕深度参数 (DisplayMetrics) ---
                val metrics = resources.displayMetrics
                nativeDataJson.put("screen_resolution_physical", "${metrics.widthPixels}x${metrics.heightPixels}")
                nativeDataJson.put("screen_density_dpi", metrics.densityDpi)
                nativeDataJson.put("screen_xdpi", metrics.xdpi.toDouble())
                nativeDataJson.put("screen_ydpi", metrics.ydpi.toDouble())
                nativeDataJson.put("screen_scaled_density", metrics.scaledDensity.toDouble())

                // --- D. 电池动态物理量 (BatteryManager - 抓模拟器神器) ---
                val batteryStatus: android.content.Intent? = android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED).let { ifilter ->
                    registerReceiver(null, ifilter)
                }
                val batteryLevel = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1) ?: -1
                val batteryScale = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1) ?: -1
                val batteryTemp = (batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1) / 10.0
                val batteryVoltage = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_VOLTAGE, -1) ?: -1
                val isCharging = batteryStatus?.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1) == android.os.BatteryManager.BATTERY_STATUS_CHARGING

                nativeDataJson.put("battery_level_pct", if (batteryLevel >= 0 && batteryScale > 0) (batteryLevel * 100f / batteryScale).toDouble() else -1.0)
                nativeDataJson.put("battery_temp_celsius", batteryTemp)
                nativeDataJson.put("battery_voltage_mv", batteryVoltage)
                nativeDataJson.put("is_charging", isCharging)

                // --- E. 传感器全局矩阵 (SensorManager - 数量即正义) ---
                val sensorManager = getSystemService(SENSOR_SERVICE) as android.hardware.SensorManager
                val sensorList = sensorManager.getSensorList(android.hardware.Sensor.TYPE_ALL)

                nativeDataJson.put("sensor_total_count", sensorList.size)
                nativeDataJson.put("has_gyroscope", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_GYROSCOPE) != null)
                nativeDataJson.put("has_accelerometer", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_ACCELEROMETER) != null)
                nativeDataJson.put("has_magnetic_field", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_MAGNETIC_FIELD) != null)
                nativeDataJson.put("has_light_sensor", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_LIGHT) != null)
                nativeDataJson.put("has_proximity_sensor", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_PROXIMITY) != null)
                nativeDataJson.put("has_pressure_sensor", sensorManager.getDefaultSensor(android.hardware.Sensor.TYPE_PRESSURE) != null)

                // --- F. 系统底层安全与调试配置 ---
                val adbEnabled = android.provider.Settings.Global.getInt(contentResolver, android.provider.Settings.Global.ADB_ENABLED, 0) == 1
                nativeDataJson.put("is_adb_enabled", adbEnabled)


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

                val request = okhttp3.Request.Builder()
                    .url("http://10.0.2.2:8000/api/collect/fingerprint")
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