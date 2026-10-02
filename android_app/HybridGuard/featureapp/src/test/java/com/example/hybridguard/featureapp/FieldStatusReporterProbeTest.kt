package com.example.hybridguard.featureapp

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FieldStatusReporterProbeTest {
    private val gl1 = "web_data.graphics_layer.webgl_renderer"
    private val gl2 = "web_data.graphics_layer.webgl2_supported"

    @Test fun webgl2FailureDoesNotContaminateWebgl1() {
        val statuses = JSONObject("""{"webgl":"observed","webgl2":"runtime_error"}""")
        assertNull(FieldStatusReporter.probeFailure(gl1, statuses))
        assertEquals("runtime_error", FieldStatusReporter.probeFailure(gl2, statuses))
    }

    @Test fun webgl1FailureDoesNotMaskIndependentWebgl2Observation() {
        for (state in listOf("runtime_error", "not_applicable", "timeout")) {
            val statuses = JSONObject().put("webgl", state).put("webgl2", "observed")
            assertEquals(state, FieldStatusReporter.probeFailure(gl1, statuses))
            assertNull(FieldStatusReporter.probeFailure(gl2, statuses))
        }
    }

    @Test fun bridgeFailureMarksBothProbesAsFailed() {
        val statuses = JSONObject("""{"webgl":"runtime_error","webgl2":"runtime_error"}""")
        assertEquals("runtime_error", FieldStatusReporter.probeFailure(gl1, statuses))
        assertEquals("runtime_error", FieldStatusReporter.probeFailure(gl2, statuses))
    }
}
