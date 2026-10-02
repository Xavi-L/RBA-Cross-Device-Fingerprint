package com.example.hybridguard.featureapp

import org.junit.Assert.*
import org.junit.Test

class GeometryReadBoundaryTest {
    @Test fun hostBeforeExceptionCompletesOnceWithoutLosingFailureReason() {
        val policy = GeometrySamplingPolicy()
        val generation = policy.navigate()
        assertTrue(policy.acceptPayload())
        val failures = mutableListOf<String>()
        var completions = 0
        fun complete() { if (policy.finishOnce()) completions += 1 }
        val snapshot = GeometryReadBoundary.readIfCurrent(
            { policy.callbackIsCurrent(generation) }, "host_before_snapshot",
            { throw IllegalStateException("injected Android getter failure") }
        ) { reason -> failures.add(reason); complete() }
        assertNull(snapshot)
        assertEquals(listOf("host_before_snapshot_IllegalStateException"), failures)
        // Timeout/destroy after the failure cannot deliver the legacy payload twice.
        complete(); policy.destroy(); complete()
        assertEquals(1, completions)
    }

    @Test fun hostAfterFailureRemainsBoundedAndLateCallbackDoesNotRead() {
        val policy = GeometrySamplingPolicy()
        val generation = policy.navigate()
        assertTrue(policy.acceptPayload())
        val failures = mutableListOf<String>()
        var reads = 0
        var completions = 0
        repeat(GeometrySamplingPolicy.MAX_ATTEMPTS) {
            assertNull(GeometryReadBoundary.readIfCurrent(
                { policy.callbackIsCurrent(generation) }, "host_after_snapshot",
                { reads += 1; throw IllegalArgumentException("injected asynchronous getter failure") }
            ) { reason ->
                failures.add(reason)
                if (failures.size == GeometrySamplingPolicy.MAX_ATTEMPTS && policy.finishOnce()) completions += 1
            })
        }
        assertEquals(2, reads)
        assertEquals(2, failures.size)
        assertTrue(failures.all { it == "host_after_snapshot_IllegalArgumentException" })
        assertEquals(1, completions)
        GeometryReadBoundary.readIfCurrent(
            { policy.callbackIsCurrent(generation) }, "host_after_snapshot",
            { reads += 1; "late value" }
        ) { fail("completed callback must not fail again") }
        assertEquals(2, reads)
        assertFalse(policy.finishOnce())
    }

    @Test fun replacedDocumentAndDestroyedActivityDoNotInvokeGetter() {
        val policy = GeometrySamplingPolicy()
        val oldGeneration = policy.navigate()
        policy.navigate()
        fun readOld() = GeometryReadBoundary.readIfCurrent(
            { policy.callbackIsCurrent(oldGeneration) }, "host_after_snapshot",
            { fail("stale callback must not access the View"); "unreachable" }
        ) { fail("stale callback must not create a new failure") }
        assertNull(readOld())
        policy.destroy()
        assertNull(readOld())
    }

    @Test fun successfulReadIsPassedThroughWithoutChangingMeasuredValues() {
        val measured = linkedMapOf("width_px" to 393, "height_px" to 851)
        var readCount = 0
        val returned = GeometryReadBoundary.readIfCurrent(
            { true }, "host_after_snapshot", { readCount += 1; measured }
        ) { fail("normal getter must not produce failure") }
        assertSame(measured, returned)
        assertEquals(1, readCount)
    }
}
