package com.example.hybridguard.featureapp

import org.json.JSONObject

internal object AppCollectionObservations {
    /** Preserve JS observations without creating missing values or certifying their origin. */
    fun copyIfPresent(webPayload: JSONObject, appPayload: JSONObject) {
        webPayload.optJSONObject("collection_observations")?.let { observations ->
            appPayload.put("collection_observations", observations)
        }
    }
}
