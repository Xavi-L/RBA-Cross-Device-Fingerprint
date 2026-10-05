package com.example.hybridguard.featureapp

import java.io.IOException
import java.net.SocketTimeoutException
import java.security.cert.CertificateException
import java.security.cert.CertPathValidatorException
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLPeerUnverifiedException
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import org.junit.Assert.*
import org.junit.Test

class CollectionTlsTest {
    private fun root(name: String) = HeldCertificate.Builder()
        .commonName(name).certificateAuthority(1).build()

    @Test fun bundledCertificateIsThePublicSelfSignedRoot() {
        val certificate = CollectionTls.bundledRoot()
        assertTrue(certificate.subjectX500Principal.name.contains("CN=ISRG Root X1"))
        assertEquals(certificate.subjectX500Principal, certificate.issuerX500Principal)
        assertTrue(certificate.basicConstraints >= 0)
        certificate.checkValidity()
        certificate.verify(certificate.publicKey)
    }

    @Test fun supplementIsLimitedToLegacyAndroidAndRetainsSystemRoots() {
        val root = CollectionTls.bundledRoot()
        for (sdk in listOf(21, 22, 23, 24, 25)) {
            val manager = CollectionTls.clientBuilder(sdk).build().x509TrustManager!!
            assertTrue(manager is SupplementalRootTrustManager)
            assertTrue(manager.acceptedIssuers.contains(root))
            assertTrue(manager.acceptedIssuers.toSet().containsAll(
                CollectionTls.systemTrustManager().acceptedIssuers.toSet()
            ))
        }
        assertFalse(CollectionTls.clientBuilder(26).build().x509TrustManager is SupplementalRootTrustManager)
    }

    @Test fun supplementalRootRepairsMissingTrustButPreservesPlatformTrust() {
        val platform = root("platform")
        val extra = root("extra")
        val missingRootLeaf = HeldCertificate.Builder().commonName("localhost")
            .addSubjectAlternativeName("localhost").signedBy(extra).build()
        expectTlsFailure { request(missingRootLeaf, extra, platform, root("unrelated")) }
        assertEquals("ok", request(missingRootLeaf, extra, platform, extra))
        for (signer in listOf(platform, extra)) {
            val leaf = HeldCertificate.Builder().commonName("localhost")
                .addSubjectAlternativeName("localhost").signedBy(signer).build()
            assertEquals("ok", request(leaf, signer, platform, extra))
        }
    }

    @Test fun untrustedServerIsStillRejected() {
        val platform = root("platform")
        val extra = root("extra")
        val attacker = root("untrusted")
        val leaf = HeldCertificate.Builder().commonName("localhost")
            .addSubjectAlternativeName("localhost").signedBy(attacker).build()
        expectTlsFailure { request(leaf, attacker, platform, extra) }
    }

    @Test fun supplementalTrustDoesNotDisableHostnameVerification() {
        val extra = root("extra")
        val leaf = HeldCertificate.Builder().commonName("wrong.example")
            .addSubjectAlternativeName("wrong.example").signedBy(extra).build()
        expectTlsFailure { request(leaf, extra, root("platform"), extra) }
    }

    @Test fun expiredLeafIsStillRejected() {
        val extra = root("extra")
        val leaf = HeldCertificate.Builder().commonName("localhost")
            .addSubjectAlternativeName("localhost").validityInterval(1L, 2L)
            .signedBy(extra).build()
        expectTlsFailure { request(leaf, extra, root("platform"), extra) }
    }

    @Test fun certificateFailuresAreTerminalButNetworkTimeoutsRemainRetryable() {
        val wrapped = IOException("request", SSLHandshakeException("handshake").apply {
            initCause(CertificateException("untrusted"))
        })
        val observedFailure = SSLHandshakeException("handshake").apply {
            initCause(CertPathValidatorException("Trust anchor for certification path not found."))
        }
        for (error in listOf(wrapped, observedFailure, SSLPeerUnverifiedException("hostname"))) {
            for (operation in listOf("readiness", "upload", "browser-ticket", "browser-pair-poll")) {
                val failure = CollectionNetworkFailure.from(error, operation, "https://test.example/path?token=SECRET")
                assertFalse(failure.retryable)
                assertTrue(failure.detail.contains("TLS_CERTIFICATE_ERROR"))
                assertTrue(failure.detail.contains("host=test.example"))
                assertFalse(failure.detail.contains("SECRET"))
            }
        }
        assertTrue(CollectionNetworkFailure.from(SocketTimeoutException(), "upload", "https://test.example").retryable)
        assertFalse(CollectionNetworkFailure.from(SSLHandshakeException("protocol"), "upload", "https://test.example").retryable)
    }

    private fun request(
        leaf: HeldCertificate,
        signer: HeldCertificate,
        platform: HeldCertificate,
        extra: HeldCertificate
    ): String {
        val trust = SupplementalRootTrustManager(
            CollectionTls.trustManagerFor(listOf(platform.certificate)),
            CollectionTls.trustManagerFor(listOf(extra.certificate))
        )
        val context = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trust), null) }
        val client = OkHttpClient.Builder().sslSocketFactory(context.socketFactory, trust)
            .callTimeout(3, TimeUnit.SECONDS).retryOnConnectionFailure(false).build()
        val serverTls = HandshakeCertificates.Builder().heldCertificate(leaf, signer.certificate).build()
        return MockWebServer().use { server ->
            server.useHttps(serverTls.sslSocketFactory(), false)
            server.enqueue(MockResponse().setBody("ok"))
            server.start()
            try {
                client.newCall(Request.Builder().url(server.url("/")).build()).execute().use {
                    check(it.isSuccessful)
                    it.body!!.string()
                }
            } finally {
                client.connectionPool.evictAll()
                client.dispatcher.executorService.shutdown()
            }
        }
    }

    private fun expectTlsFailure(block: () -> Unit) {
        try {
            block()
            fail("Invalid server must not be trusted")
        } catch (error: IOException) {
            assertFalse(CollectionNetworkFailure.from(error, "test", "https://localhost").retryable)
        }
    }
}
