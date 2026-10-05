package com.example.hybridguard.featureapp

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BrowserLaunchDecisionTest {
    @Test
    fun concreteQualifiedHandlerIsSelectedWithoutFallback() {
        val result = BrowserLaunchDecision.select(
            resolvedPackageName = "com.android.chrome",
            resolvedActivityName = "com.google.android.apps.chrome.Main",
            handlers = listOf(
                candidate(
                    "org.mozilla.firefox",
                    "org.mozilla.firefox.App",
                    declaredBrowserApp = true
                ),
                candidate(
                    "com.android.chrome",
                    "com.google.android.apps.chrome.Main",
                    declaredBrowserApp = true
                )
            )
        )

        assertEquals(
            BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RESOLVED,
            result.status
        )
        assertEquals("com.android.chrome", result.packageName)
        assertEquals(
            "com.google.android.apps.chrome.Main",
            result.activityName
        )
        assertTrue(result.canLaunch)
    }

    @Test
    fun onePlusStyleChooserSelectsAospBrowserInsteadOfWeibo() {
        val result = BrowserLaunchDecision.select(
            resolvedPackageName = "android",
            resolvedActivityName = "com.android.internal.app.ResolverActivity",
            handlers = listOf(
                candidate("com.sina.weibo", "com.sina.weibo.browser.BrowserActivity"),
                candidate(
                    "com.android.browser",
                    "com.android.browser.BrowserActivity",
                    declaredBrowserApp = true
                )
            )
        )

        assertEquals(
            BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RANKED,
            result.status
        )
        assertEquals("com.android.browser", result.packageName)
        assertEquals(
            "com.android.browser.BrowserActivity",
            result.activityName
        )
        assertTrue(result.canLaunch)
    }

    @Test
    fun samsungStyleChooserSelectsSamsungInternet() {
        val result = BrowserLaunchDecision.select(
            resolvedPackageName = "android",
            resolvedActivityName = "com.android.internal.app.ResolverActivity",
            handlers = listOf(
                candidate(
                    "com.baidu.searchbox_samsung",
                    "com.baidu.searchbox.RouterActivity"
                ),
                candidate(
                    "com.sec.android.app.sbrowser",
                    "com.sec.android.app.sbrowser.SBrowserMainActivity",
                    declaredBrowserApp = true
                ),
                candidate("com.smile.gifmaker", "com.yxcorp.gifshow.HomeActivity")
            )
        )

        assertEquals(
            BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RANKED,
            result.status
        )
        assertEquals("com.sec.android.app.sbrowser", result.packageName)
        assertTrue(result.canLaunch)
    }

    @Test
    fun declaredBrowserCategorySupportsUnknownVendorPackage() {
        val result = BrowserLaunchDecision.select(
            resolvedPackageName = null,
            resolvedActivityName = null,
            handlers = listOf(
                candidate(
                    "vendor.web.client",
                    "vendor.web.client.MainActivity",
                    declaredBrowserApp = true
                )
            )
        )

        assertEquals(
            BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RANKED,
            result.status
        )
        assertEquals("vendor.web.client", result.packageName)
        assertTrue(result.canLaunch)
    }

    @Test
    fun arbitraryHttpsHandlersAreNotTreatedAsBrowsers() {
        val result = BrowserLaunchDecision.select(
            resolvedPackageName = "android",
            resolvedActivityName = "com.android.internal.app.ResolverActivity",
            handlers = listOf(
                candidate("com.sina.weibo", "com.sina.weibo.browser.BrowserActivity"),
                candidate("com.smile.gifmaker", "com.yxcorp.gifshow.HomeActivity"),
                candidate(
                    "com.vendor.browserhelper",
                    "com.vendor.browserhelper.BrowserActivity"
                )
            )
        )

        assertEquals(
            BrowserLaunchResolution.STATUS_NO_TRUSTED_BROWSER,
            result.status
        )
        assertNull(result.packageName)
        assertNull(result.activityName)
        assertFalse(result.canLaunch)
    }

    @Test
    fun duplicateAndReorderedCandidatesProduceStableSelection() {
        val samsung = candidate(
            "com.sec.android.app.sbrowser",
            "com.sec.android.app.sbrowser.SBrowserMainActivity",
            declaredBrowserApp = true
        )
        val chrome = candidate(
            "com.android.chrome",
            "com.google.android.apps.chrome.Main",
            declaredBrowserApp = true
        )

        val first = BrowserLaunchDecision.select(
            resolvedPackageName = null,
            resolvedActivityName = null,
            handlers = listOf(chrome, samsung, chrome)
        )
        val second = BrowserLaunchDecision.select(
            resolvedPackageName = null,
            resolvedActivityName = null,
            handlers = listOf(samsung, chrome)
        )

        assertEquals(first, second)
        assertEquals("com.sec.android.app.sbrowser", first.packageName)
        assertEquals(
            listOf("com.android.chrome", "com.sec.android.app.sbrowser"),
            first.visibleHandlerPackageNames
        )
    }

    @Test
    fun emptyHandlerSetIsReportedExplicitly() {
        val result = BrowserLaunchDecision.select(
            resolvedPackageName = null,
            resolvedActivityName = null,
            handlers = emptyList()
        )

        assertEquals(BrowserLaunchResolution.STATUS_NO_HANDLER, result.status)
        assertFalse(result.canLaunch)
    }

    private fun candidate(
        packageName: String,
        activityName: String,
        declaredBrowserApp: Boolean = false
    ) = BrowserHandlerCandidate(
        packageName = packageName,
        activityName = activityName,
        declaredBrowserApp = declaredBrowserApp
    )
}
