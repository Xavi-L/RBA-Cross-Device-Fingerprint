package com.example.hybridguard.featureapp

import android.os.Build
import java.security.KeyStore
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager
import okhttp3.OkHttpClient

/** Extra public root for collection HTTP clients on Android 5–7, never a global TLS override. */
internal object CollectionTls {
    fun clientBuilder(sdkInt: Int = Build.VERSION.SDK_INT): OkHttpClient.Builder {
        val builder = OkHttpClient.Builder()
        // API 25 also includes Android 7.1.0; ISRG X1 arrived in stock 7.1.1.
        if (sdkInt <= 25) {
            val trustManager = SupplementalRootTrustManager(
                systemTrustManager(),
                trustManagerFor(listOf(bundledRoot()))
            )
            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, arrayOf(trustManager), null)
            builder.sslSocketFactory(sslContext.socketFactory, trustManager)
        }
        // Keep OkHttp's certificate-chain and hostname verification enabled.
        return builder
    }

    internal fun bundledRoot(): X509Certificate =
        checkNotNull(CollectionTls::class.java.getResourceAsStream("/tls/isrg_root_x1.pem")) {
            "Missing bundled ISRG Root X1 certificate"
        }.use { CertificateFactory.getInstance("X.509").generateCertificate(it) as X509Certificate }

    internal fun systemTrustManager(): X509TrustManager = trustManager(null)

    internal fun trustManagerFor(roots: List<X509Certificate>): X509TrustManager {
        val store = KeyStore.getInstance(KeyStore.getDefaultType()).apply {
            load(null, null)
            roots.forEachIndexed { index, root -> setCertificateEntry("root-$index", root) }
        }
        return trustManager(store)
    }

    private fun trustManager(store: KeyStore?): X509TrustManager =
        TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply {
            init(store)
        }.trustManagers.filterIsInstance<X509TrustManager>().single()
}

internal class SupplementalRootTrustManager(
    private val system: X509TrustManager,
    private val supplemental: X509TrustManager
) : X509TrustManager {
    override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
        try {
            system.checkServerTrusted(chain, authType)
        } catch (systemFailure: CertificateException) {
            try {
                supplemental.checkServerTrusted(chain, authType)
            } catch (supplementalFailure: CertificateException) {
                supplementalFailure.addSuppressed(systemFailure)
                throw supplementalFailure
            }
        }
    }

    override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) =
        system.checkClientTrusted(chain, authType)

    override fun getAcceptedIssuers(): Array<X509Certificate> =
        (system.acceptedIssuers + supplemental.acceptedIssuers).distinct().toTypedArray()
}
