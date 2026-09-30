package com.example.hybridguard.featureapp

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class WebViewProbeControlTest {
    @Test
    fun defaultLaunchLoadsProbeWithDebuggingDisabled() {
        val control = WebViewProbeControl.resolve()

        assertFalse(control.debuggingEnabled)
        assertFalse(control.waitForControl)
        assertEquals(15_000L, control.deadlineMs)
        assertEquals("file:///android_asset/expanded_probe.html", control.initialUrl)
    }

    @Test
    fun frozenRunnerCanWaitForNavigationWithSixtySecondDeadline() {
        val control = WebViewProbeControl.resolve(true, true, 60_000L)

        assertTrue(control.debuggingEnabled)
        assertTrue(control.waitForControl)
        assertEquals(60_000L, control.deadlineMs)
        assertEquals("about:blank", control.initialUrl)
    }

    @Test
    fun waitingDoesNotImplicitlyEnableDebugging() {
        val control = WebViewProbeControl.resolve(waitForControl = true)

        assertFalse(control.debuggingEnabled)
        assertEquals("about:blank", control.initialUrl)
        assertEquals(15_000L, control.deadlineMs)
    }

    @Test
    fun debuggingDoesNotImplicitlyDelayProbeNavigation() {
        val control = WebViewProbeControl.resolve(debuggingEnabled = true)

        assertTrue(control.debuggingEnabled)
        assertEquals("file:///android_asset/expanded_probe.html", control.initialUrl)
    }

    @Test
    fun deadlineIsClampedWithoutOverflow() {
        for (requested in listOf(Long.MIN_VALUE, -1L, 0L, 14_999L, 15_000L)) {
            assertEquals(15_000L, WebViewProbeControl.resolve(requestedDeadlineMs = requested).deadlineMs)
        }
        assertEquals(119_999L, WebViewProbeControl.resolve(requestedDeadlineMs = 119_999L).deadlineMs)
        for (requested in listOf(120_000L, 120_001L, Long.MAX_VALUE)) {
            assertEquals(120_000L, WebViewProbeControl.resolve(requestedDeadlineMs = requested).deadlineMs)
        }
    }

    @Test
    fun observationObjectIsForwardedWithoutReinterpretingRawStates() {
        val observations = JSONObject().apply {
            put("observation_schema_version", "app-web-observations-v1")
            put("webdriver", JSONObject().apply {
                put("api_present", true)
                put("presence_read_status", "observed")
                put("value_read_status", "observed")
                put("value_type", "boolean")
                put("boolean_value", false)
                put("observer_revision", "test-observer")
                put("realm_binding", "featureapp:test-session:main-frame")
            })
            put("unrecognized_extension", JSONObject.NULL)
        }
        val payload = JSONObject().put("collection_observations", observations)
        val finalPayload = JSONObject().put("session_id", "test-session")

        AppCollectionObservations.copyIfPresent(payload, finalPayload)

        assertSame(observations, finalPayload.getJSONObject("collection_observations"))
        val persisted = JSONObject(finalPayload.toString()).getJSONObject("collection_observations")
        assertFalse(persisted.getJSONObject("webdriver").getBoolean("boolean_value"))
        assertTrue(persisted.has("unrecognized_extension"))
        assertTrue(persisted.isNull("unrecognized_extension"))
        assertEquals("test-session", finalPayload.getString("session_id"))
    }

    @Test
    fun missingOrNonObjectObservationsAreNotFabricated() {
        val inputs = listOf(
            JSONObject(),
            JSONObject().put("collection_observations", JSONObject.NULL),
            JSONObject().put("collection_observations", false),
            JSONObject().put("collection_observations", "{}"),
            JSONObject().put("collection_observations", JSONArray())
        )
        for (input in inputs) {
            val finalPayload = JSONObject()
            AppCollectionObservations.copyIfPresent(input, finalPayload)
            assertFalse(finalPayload.has("collection_observations"))
        }
    }

    @Test
    fun incompleteObservationObjectRemainsIncomplete() {
        val observations = JSONObject()
        val finalPayload = JSONObject()

        AppCollectionObservations.copyIfPresent(
            JSONObject().put("collection_observations", observations), finalPayload
        )

        assertSame(observations, finalPayload.getJSONObject("collection_observations"))
        assertEquals(0, finalPayload.getJSONObject("collection_observations").length())
    }
}
