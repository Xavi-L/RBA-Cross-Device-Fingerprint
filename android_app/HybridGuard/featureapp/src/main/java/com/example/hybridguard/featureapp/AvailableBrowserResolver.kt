package com.example.hybridguard.featureapp

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ResolveInfo
import android.os.Build
import android.util.Log
import androidx.core.net.toUri

internal object AvailableBrowserResolver {
    private const val TAG = "HG-BrowserResolve"

    fun resolve(context: Context, browserProbeBaseUrl: String): BrowserLaunchResolution {
        return try {
            val probeUri = browserProbeBaseUrl.toUri()
            val genericIntent = Intent(Intent.ACTION_VIEW, probeUri).apply {
                addCategory(Intent.CATEGORY_BROWSABLE)
            }
            val packageManager = context.packageManager
            val declaredBrowserPackages = queryHandlers(
                packageManager,
                Intent.makeMainSelectorActivity(
                    Intent.ACTION_MAIN,
                    Intent.CATEGORY_APP_BROWSER
                )
            ).mapNotNull { it.activityInfo?.packageName?.trim() }
                .filter(String::isNotEmpty)
                .toSet()
            val httpsHandlers = queryHandlers(packageManager, genericIntent)
                .toMutableList()
            // A generic web query can be narrowed by Android when a URL is
            // associated with a non-browser app. Re-query each declared browser
            // explicitly so an installed browser remains discoverable.
            declaredBrowserPackages.sorted().forEach { packageName ->
                httpsHandlers += queryHandlers(
                    packageManager,
                    Intent(genericIntent).setPackage(packageName)
                )
            }
            val candidates = httpsHandlers
                .mapNotNull {
                    toCandidate(
                        packageManager,
                        it,
                        it.activityInfo?.packageName in declaredBrowserPackages
                    )
                }
            val resolved = resolveHandler(packageManager, genericIntent)
            val decision = BrowserLaunchDecision.select(
                resolvedPackageName = resolved?.activityInfo?.packageName,
                resolvedActivityName = resolved?.activityInfo?.name,
                handlers = candidates
            )
            Log.i(
                TAG,
                "resolution_status=${decision.status}; package=${decision.packageName ?: "none"}; " +
                    "activity=${decision.activityName ?: "none"}; " +
                    "selection_policy=${decision.selectionPolicyRevision}; " +
                    "visible_handler_packages=${decision.visibleHandlerPackageNames}"
            )
            decision
        } catch (error: Exception) {
            Log.w(TAG, "Available-browser selection failed", error)
            BrowserLaunchResolution(
                status = BrowserLaunchResolution.STATUS_RESOLUTION_ERROR,
                packageName = null,
                detail = "PackageManager selection failed: ${error.javaClass.simpleName}"
            )
        }
    }

    @Suppress("DEPRECATION")
    private fun queryHandlers(
        packageManager: PackageManager,
        intent: Intent
    ) = if (Build.VERSION.SDK_INT >= 33) {
        packageManager.queryIntentActivities(
            intent,
            PackageManager.ResolveInfoFlags.of(0L)
        )
    } else {
        packageManager.queryIntentActivities(intent, 0)
    }

    @Suppress("DEPRECATION")
    private fun resolveHandler(
        packageManager: PackageManager,
        intent: Intent
    ) = if (Build.VERSION.SDK_INT >= 33) {
        packageManager.resolveActivity(
            intent,
            PackageManager.ResolveInfoFlags.of(PackageManager.MATCH_DEFAULT_ONLY.toLong())
        )
    } else {
        packageManager.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY)
    }

    private fun toCandidate(
        packageManager: PackageManager,
        resolveInfo: ResolveInfo,
        declaredBrowserApp: Boolean
    ): BrowserHandlerCandidate? {
        val activityInfo = resolveInfo.activityInfo ?: return null
        val packageName = activityInfo.packageName?.trim().orEmpty()
        val activityName = activityInfo.name?.trim().orEmpty()
        if (
            packageName.isEmpty() ||
            activityName.isEmpty() ||
            !activityInfo.enabled ||
            !activityInfo.exported ||
            activityInfo.applicationInfo?.enabled == false
        ) {
            return null
        }
        return BrowserHandlerCandidate(
            packageName = packageName,
            activityName = activityName,
            declaredBrowserApp = declaredBrowserApp
        )
    }
}
