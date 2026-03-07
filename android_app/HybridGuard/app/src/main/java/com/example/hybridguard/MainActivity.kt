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
        myWebView.addJavascriptInterface(WebAppInterface(sessionId), "AndroidBridge")

        // 加载探针网页
        myWebView.loadUrl("http://10.0.2.2:5500/index.html")
    }

    private fun collectAndSendNativeData() {
        thread {
            try {
                // 1. 采集原生硬件特征
                val deviceModel = Build.MODEL
                val deviceBrand = Build.BRAND
                val osVersion = "Android " + Build.VERSION.RELEASE
                val cpuAbi = Build.SUPPORTED_ABIS[0]
                val uptimeMs = SystemClock.uptimeMillis()

                // 简单估算一下内存 (为了代码极简，这里写死一个大致逻辑，实际应用中可通过 ActivityManager 获取)
                val totalMemoryGb = 8.0
                val physicalRes = resources.displayMetrics.let {
                    "${it.widthPixels}x${it.heightPixels}"
                }

                // 2. 组装符合 JSON 契约的数据结构 (使用原生的 JSONObject)
                val nativeDataJson = org.json.JSONObject().apply {
                    put("device_model", deviceModel)
                    put("device_brand", deviceBrand)
                    put("os_version", osVersion)
                    put("cpu_abi", cpuAbi)
                    put("total_memory_gb", totalMemoryGb)
                    put("screen_resolution_physical", physicalRes)
                    put("uptime_ms", uptimeMs)
                }

                val payload = org.json.JSONObject().apply {
                    put("session_id", sessionId) // 极其重要：使用相同的 UUID
                    put("timestamp", System.currentTimeMillis() / 1000)
                    put("android_native_data", nativeDataJson)
                }

                // 3. 使用 OkHttp 发送 POST 请求 (OkHttp 4.x Kotlin 现代写法)
                val client = okhttp3.OkHttpClient()

                // 【修复1】：使用 toMediaType() 和 toRequestBody() 扩展函数
                val mediaType = "application/json; charset=utf-8".toMediaType()
                val body = payload.toString().toRequestBody(mediaType)

                val request = okhttp3.Request.Builder()
                    .url("http://10.0.2.2:8000/api/collect/fingerprint")
                    .post(body)
                    .build()

                val response = client.newCall(request).execute()

                if (response.isSuccessful) {
                    println("✅ 原生数据 POST 成功！Session ID: $sessionId")
                } else {
                    // 【修复2】：把 response.code() 的括号去掉，直接作为属性访问
                    println("❌ 原生数据 POST 失败，状态码: ${response.code}")
                }
            } catch (e: Exception) {
                println("❌ 网络请求异常: ${e.message}")
            }
        }
    }
}