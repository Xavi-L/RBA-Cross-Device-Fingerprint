package com.example.hybridguard.featureapp

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class GeometrySamplingPolicyTest {
    @Test fun duplicateBridgeAndTimeoutCannotAcceptTwoPayloads() {
        val policy = GeometrySamplingPolicy()
        assertTrue(policy.acceptPayload())
        assertFalse(policy.acceptPayload())
        assertTrue(policy.finishOnce())
        assertFalse(policy.finishOnce())
        assertFalse(policy.callbackIsCurrent(0))
    }

    @Test fun navigationRejectsOldJavascriptCallback() {
        val policy = GeometrySamplingPolicy()
        val oldDocument = policy.navigate()
        assertTrue(policy.acceptPayload())
        assertTrue(policy.callbackIsCurrent(oldDocument))
        val next = policy.navigate()
        assertFalse(policy.callbackIsCurrent(oldDocument))
        assertTrue(policy.callbackIsCurrent(next))
    }

    @Test fun destroyedActivityCannotAcceptOrReuseAnyCallback() {
        val policy = GeometrySamplingPolicy()
        val generation = policy.navigate()
        policy.destroy()
        assertFalse(policy.acceptPayload())
        assertFalse(policy.callbackIsCurrent(generation))
        assertFalse(policy.callbackIsCurrent(policy.generation))
        // Cancellation still completes the already held legacy payload once.
        assertTrue(policy.finishOnce())
        assertFalse(policy.finishOnce())
    }

    @Test fun observedHostChangeOrLongWindowIsUnstable() {
        assertTrue(GeometrySamplingPolicy.hostStable("layout1/scale1/doc1", "layout1/scale1/doc1", "400x600", "400x600", 5L, 10L))
        assertFalse(GeometrySamplingPolicy.hostStable("a", "b", "400x600", "400x600", 5L, 10L))
        assertFalse(GeometrySamplingPolicy.hostStable("a", "a", "400x600", "600x400", 5L, 10L))
        assertFalse(GeometrySamplingPolicy.hostStable("a", "a", "400x600", "400x600", 5L, 4L))
        assertFalse(GeometrySamplingPolicy.hostStable("a", "a", "400x600", "400x600", 5L, 2000L))
    }

    @Test fun stableHostPolicyHasNoWebOperands() {
        // A measured contradiction, if any, is evaluated downstream and cannot influence this gate.
        val unusualButStable = "width=393,height=851,density=2.75"
        assertTrue(GeometrySamplingPolicy.hostStable("same", "same", unusualButStable, unusualButStable, 0L, 50L))
    }

    private fun web() = JSONObject().put("document_id", "doc-id").put("binding", JSONObject()
        .put("session_id", "session").put("webview_instance_id", "view")
        .put("document_generation", 4).put("observation_id", "observation").put("attempt_id", 1))
    private fun matches(value: JSONObject?) = GeometrySnapshotBinding.matches(value, "doc-id", "session", "view", 4, "observation", 1)

    @Test fun eachBindingComponentIsRequiredAndCannotComeFromOtherSession() {
        assertTrue(matches(web()))
        assertFalse(matches(null))
        assertFalse(matches(web().put("document_id", "another-document")))
        for ((key, value) in mapOf("session_id" to "other", "webview_instance_id" to "other", "document_generation" to 5, "observation_id" to "other", "attempt_id" to 2)) {
            val snapshot = web()
            snapshot.getJSONObject("binding").put(key, value)
            assertFalse("must reject $key", matches(snapshot))
        }
        assertFalse(matches(JSONObject().put("document_id", "doc-id")))
        assertFalse(GeometrySnapshotBinding.matches(web(), null, "session", "view", 4, "observation", 1))
    }

    @Test fun fixedZoomOperationDoesNotSilentlyChangeUnsupportedRequests() {
        assertTrue(GeometryExperimentControl.validZoom(1f))
        assertTrue(GeometryExperimentControl.validZoom(1.25f))
        for (factor in listOf(0f, -1f, 2f, Float.NaN, Float.POSITIVE_INFINITY)) assertFalse(GeometryExperimentControl.validZoom(factor))
    }
}
