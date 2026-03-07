package com.example.hybridguard

import android.webkit.JavascriptInterface

class WebAppInterface(private val sessionId: String) {

    // 加上这个注解，网页里的 JS 才能调用这个方法
    @JavascriptInterface
    fun getSessionId(): String {
        return sessionId
    }
}