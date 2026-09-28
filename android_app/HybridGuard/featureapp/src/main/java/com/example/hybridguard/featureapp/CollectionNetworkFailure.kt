package com.example.hybridguard.featureapp

import java.security.cert.CertificateException
import java.security.cert.CertPathBuilderException
import java.security.cert.CertPathValidatorException
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLPeerUnverifiedException
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

internal data class CollectionNetworkFailure(val retryable: Boolean, val detail: String) {
    companion object {
        fun from(error: Exception, operation: String, endpoint: String): CollectionNetworkFailure {
            val causes = mutableListOf<Throwable>()
            var cause: Throwable? = error
            while (cause != null && causes.none { it === cause }) {
                causes.add(cause)
                cause = cause.cause
            }
            val certificateError = causes.any {
                it is CertificateException || it is CertPathValidatorException ||
                    it is CertPathBuilderException || it is SSLPeerUnverifiedException
            }
            val handshakeError = causes.any { it is SSLHandshakeException }
            val code = when {
                certificateError -> "TLS_CERTIFICATE_ERROR"
                handshakeError -> "TLS_HANDSHAKE_ERROR"
                else -> "NETWORK_REQUEST_FAILED"
            }
            val explanation = when {
                certificateError -> "证书校验失败，请检查采集域名的证书链、设备时间及代理证书；自动重试已停止"
                handshakeError -> "TLS 握手失败，请检查服务端与设备的 TLS 兼容性；自动重试已停止"
                else -> "网络请求失败，可重试"
            }
            // Do not put a query string, ticket, or full request URL into diagnostics.
            val host = endpoint.toHttpUrlOrNull()?.host ?: "invalid-host"
            return CollectionNetworkFailure(
                !certificateError && !handshakeError,
                "$code: $operation host=$host; $explanation; cause=${causes.last().javaClass.simpleName}"
            )
        }
    }
}
