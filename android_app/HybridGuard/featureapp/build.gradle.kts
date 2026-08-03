import java.net.URI

plugins {
    alias(libs.plugins.android.application)
}

fun String.asBuildConfigString(): String = replace("\\", "\\\\").replace("\"", "\\\"")

fun backendOrigin(endpoint: String): String {
    return try {
        val parsed = URI(endpoint)
        if (
            (parsed.scheme == "http" || parsed.scheme == "https") &&
            !parsed.host.isNullOrBlank() &&
            parsed.userInfo == null
        ) {
            val defaultPort = if (parsed.scheme == "https") 443 else 80
            val portSuffix = if (parsed.port > 0 && parsed.port != defaultPort) ":${parsed.port}" else ""
            "${parsed.scheme}://${parsed.host}$portSuffix"
        } else {
            "http://10.0.2.2:8000"
        }
    } catch (_: Exception) {
        "http://10.0.2.2:8000"
    }
}

fun validatePublicHttpsEndpoint(label: String, endpoint: String, expectedPath: String) {
    val parsed = try {
        URI(endpoint)
    } catch (error: Exception) {
        throw GradleException("$label must be a valid public HTTPS URL: $endpoint", error)
    }
    val host = parsed.host?.lowercase().orEmpty()
    val localHosts = setOf("10.0.2.2", "127.0.0.1", "localhost", "::1")
    check(
        parsed.scheme == "https" &&
            host.isNotBlank() &&
            host !in localHosts &&
            !host.endsWith(".local") &&
            parsed.userInfo == null &&
            parsed.query == null &&
            parsed.fragment == null &&
            parsed.path == expectedPath
    ) {
        "$label must be a credential-free public HTTPS URL with path $expectedPath; got $endpoint"
    }
}

android {
    namespace = "com.example.hybridguard.featureapp"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.example.hybridguard.featureapp"
        minSdk = 21
        targetSdk = 36
        versionCode = 8
        versionName = "1.6.1-expanded-v2.2-browser-recovery"

        val configuredEndpoint = providers.gradleProperty("hybridguardCollectEndpoint")
            .orElse("http://10.0.2.2:8000/api/collect/fingerprint")
            .get()
        val configuredBackendOrigin = backendOrigin(configuredEndpoint)
        val configuredBrowserTicketEndpoint = providers
            .gradleProperty("hybridguardBrowserTicketEndpoint")
            .orElse("$configuredBackendOrigin/api/collect/browser-ticket")
            .get()
        val configuredBrowserPairPollBaseUrl = providers
            .gradleProperty("hybridguardBrowserPairPollBaseUrl")
            .orElse("$configuredBackendOrigin/api/collect/browser-pairs")
            .get()
        val requirePublicEndpoints = providers
            .gradleProperty("hybridguardRequirePublicEndpoints")
            .map { value ->
                when (value.lowercase()) {
                    "true" -> true
                    "false" -> false
                    else -> throw GradleException(
                        "hybridguardRequirePublicEndpoints must be true or false; got $value"
                    )
                }
            }
            .orElse(false)
            .get()
        if (requirePublicEndpoints) {
            validatePublicHttpsEndpoint(
                "hybridguardCollectEndpoint",
                configuredEndpoint,
                "/api/collect/fingerprint"
            )
            validatePublicHttpsEndpoint(
                "hybridguardBrowserTicketEndpoint",
                configuredBrowserTicketEndpoint,
                "/api/collect/browser-ticket"
            )
            validatePublicHttpsEndpoint(
                "hybridguardBrowserPairPollBaseUrl",
                configuredBrowserPairPollBaseUrl,
                "/api/collect/browser-pairs"
            )
            check(
                setOf(
                    backendOrigin(configuredEndpoint),
                    backendOrigin(configuredBrowserTicketEndpoint),
                    backendOrigin(configuredBrowserPairPollBaseUrl)
                ).size == 1
            ) {
                "Cloud build collect, browser-ticket, and browser-pairs endpoints must share one origin"
            }
        }
        // Public static page only: the backend URL and short-lived credentials are
        // supplied at runtime in the URL fragment and are never committed here.
        val configuredBrowserProbeBaseUrl = providers
            .gradleProperty("hybridguardBrowserProbeBaseUrl")
            .orElse("https://xavi-l.github.io/RBA-Cross-Device-Fingerprint/")
            .get()
        val configuredWebProbeRevision = providers
            .gradleProperty("hybridguardWebProbeRevision")
            .orElse("expanded-web-67-v1")
            .get()

        buildConfigField(
            "String",
            "COLLECT_ENDPOINT",
            "\"${configuredEndpoint.asBuildConfigString()}\""
        )
        buildConfigField(
            "String",
            "BROWSER_TICKET_ENDPOINT",
            "\"${configuredBrowserTicketEndpoint.asBuildConfigString()}\""
        )
        buildConfigField(
            "String",
            "BROWSER_PAIR_POLL_BASE_URL",
            "\"${configuredBrowserPairPollBaseUrl.asBuildConfigString()}\""
        )
        buildConfigField(
            "String",
            "BROWSER_PROBE_BASE_URL",
            "\"${configuredBrowserProbeBaseUrl.asBuildConfigString()}\""
        )
        buildConfigField(
            "String",
            "WEB_PROBE_REVISION",
            "\"${configuredWebProbeRevision.asBuildConfigString()}\""
        )

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    buildFeatures {
        buildConfig = true
    }

    val canonicalWebProbeAssets = rootProject.projectDir
        .resolve("../../web_probe")
        .canonicalFile
    check(canonicalWebProbeAssets.isDirectory) {
        "Canonical Web probe assets directory is missing: $canonicalWebProbeAssets"
    }
    check(canonicalWebProbeAssets.name == "web_probe") {
        "Refusing to package an unexpected Web probe assets directory: $canonicalWebProbeAssets"
    }
    sourceSets.named("main") {
        assets.directories.add(canonicalWebProbeAssets.absolutePath)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    testImplementation(libs.junit)
    testImplementation("org.json:json:20240303")
}
