package com.example.hybridguard.featureapp

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BrowserPairContractTest {
    private val receipt = VerifiedCollectionReceipt(
        receiptId = "0123456789abcdef01234567",
        sessionId = "app-session-1",
        payloadSha256 = "b".repeat(64),
        collectionBatchId = "hgbatch-v1-test",
        validationStatus = "accepted",
        warningCount = 0
    )

    @Test
    fun ticketMustEchoTheDurableAppReceiptBinding() {
        val response = validTicketJson()

        val ticket = BrowserPairTransport.parseAndVerifyTicket(
            response,
            receipt,
            "ticket-request-1",
            "https://probe.example/collect/"
        )

        assertNotNull(ticket)
        assertEquals("hgpair-v1-1234", ticket?.pairId)
        assertEquals(receipt.payloadSha256, ticket?.appPayloadSha256)
    }

    @Test
    fun ticketWithDifferentAppHashIsRejected() {
        val response = validTicketJson().apply {
            put("app_payload_sha256", "c".repeat(64))
        }

        assertNull(
            BrowserPairTransport.parseAndVerifyTicket(
                response,
                receipt,
                "ticket-request-1",
                "https://probe.example/collect/"
            )
        )
    }

    @Test
    fun provisionalRequestUsesStableIdAndOmitsReceiptBinding() {
        val resolution = BrowserLaunchResolution(
            status = BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RANKED,
            packageName = "com.android.chrome",
            detail = "test",
            activityName = "com.google.android.apps.chrome.Main",
            visibleHandlerPackageNames = listOf(
                "com.android.chrome",
                "com.sina.weibo"
            )
        )

        val first = BrowserPairTransport.buildTicketRequestJson(
            appSessionId = receipt.sessionId,
            ticketRequestId = "stable-ticket-request",
            receipt = null,
            resolution = resolution,
            browserProbeBaseUrl = "https://probe.example/collect/",
            webProbeRevision = "expanded-web-67-v1"
        )
        val retry = BrowserPairTransport.buildTicketRequestJson(
            appSessionId = receipt.sessionId,
            ticketRequestId = "stable-ticket-request",
            receipt = null,
            resolution = resolution,
            browserProbeBaseUrl = "https://probe.example/collect/",
            webProbeRevision = "expanded-web-67-v1"
        )

        assertEquals("stable-ticket-request", first.getString("ticket_request_id"))
        assertFalse(first.has("app_receipt_id"))
        assertFalse(first.has("app_payload_sha256"))
        assertEquals(
            BrowserLaunchResolution.STATUS_AVAILABLE_BROWSER_RANKED,
            first.getString("launch_resolution_status")
        )
        assertEquals(
            "com.android.chrome",
            first.getString("selected_browser_package")
        )
        assertEquals(
            "com.google.android.apps.chrome.Main",
            first.getString("selected_browser_activity")
        )
        assertEquals(
            BROWSER_SELECTION_POLICY_REVISION,
            first.getString("browser_selection_policy_revision")
        )
        assertEquals(
            listOf("com.android.chrome", "com.sina.weibo"),
            List(first.getJSONArray("browser_candidate_packages").length()) { index ->
                first.getJSONArray("browser_candidate_packages").getString(index)
            }
        )
        assertEquals(first.toString(), retry.toString())
    }

    @Test
    fun provisionalTicketMayStartWithoutReceiptBinding() {
        val response = validTicketJson().apply {
            put("pair_status", "awaiting_app_and_browser")
            put("app_receipt_id", JSONObject.NULL)
            put("app_payload_sha256", JSONObject.NULL)
            put(
                "ticket_binding_mode",
                BrowserPairTransport.BINDING_MODE_PROVISIONAL
            )
        }

        val ticket = BrowserPairTransport.parseAndVerifyProvisionalTicket(
            response,
            receipt.sessionId,
            "ticket-request-1",
            "https://probe.example/collect/"
        )

        assertNotNull(ticket)
        assertNull(ticket?.appReceiptId)
        assertNull(ticket?.appPayloadSha256)
    }

    @Test
    fun provisionalTicketWithDifferentRequestIdIsRejected() {
        val response = validTicketJson().apply {
            put("pair_status", "awaiting_app_and_browser")
            put("ticket_request_id", "different-ticket-request")
            put("app_receipt_id", JSONObject.NULL)
            put("app_payload_sha256", JSONObject.NULL)
            put(
                "ticket_binding_mode",
                BrowserPairTransport.BINDING_MODE_PROVISIONAL
            )
        }

        assertNull(
            BrowserPairTransport.parseAndVerifyProvisionalTicket(
                response,
                receipt.sessionId,
                "ticket-request-1",
                "https://probe.example/collect/"
            )
        )
    }

    @Test
    fun provisionalPollMayTransitionFromNullToReceiptBinding() {
        val state = provisionalPollState()
        val response = pollResponse(state, "awaiting_browser").apply {
            put("app_receipt_id", receipt.receiptId)
            put("app_payload_sha256", receipt.payloadSha256)
        }

        val result = BrowserPairTransport.parseAndVerifyPoll(response, state)

        assertNotNull(result)
        assertFalse(result?.terminal ?: true)
        assertEquals(receipt.receiptId, result?.appReceiptId)
        assertEquals(receipt.payloadSha256, result?.appPayloadSha256)
    }

    @Test
    fun completedProvisionalPollRequiresCompleteReceiptBinding() {
        val state = provisionalPollState()
        val incomplete = pollResponse(state, "completed").apply {
            put("browser_session_id", "browser-session-1")
            put("browser_receipt_id", "browser-receipt-1")
            put("browser_payload_sha256", "d".repeat(64))
        }
        val complete = JSONObject(incomplete.toString()).apply {
            put("app_receipt_id", receipt.receiptId)
            put("app_payload_sha256", receipt.payloadSha256)
        }

        assertNull(BrowserPairTransport.parseAndVerifyPoll(incomplete, state))
        assertNotNull(BrowserPairTransport.parseAndVerifyPoll(complete, state))
    }

    @Test
    fun completedPollMustRemainBoundToSamePairAndReceipt() {
        val state = BrowserPairPollState(
            pairId = "hgpair-v1-1234",
            ticketRequestId = "ticket-request-1",
            pollToken = "poll-token-abcdefghijklmnopqrstuvwxyz",
            pollBaseUrl = "https://backend.example/api/collect/browser-pairs",
            browserStageUrl = "https://backend.example/api/collect/browser-stage",
            collectionBatchId = receipt.collectionBatchId,
            appSessionId = receipt.sessionId,
            appReceiptId = receipt.receiptId,
            appPayloadSha256 = receipt.payloadSha256,
            ticketBindingMode = BrowserPairTransport.BINDING_MODE_RECEIPT,
            expiresAt = "2030-01-01T00:00:00Z"
        )
        val response = JSONObject().apply {
            put("status", "success")
            put("pair_status", "completed")
            put("pair_id", state.pairId)
            put("ticket_request_id", state.ticketRequestId)
            put("collection_batch_id", state.collectionBatchId)
            put("app_session_id", state.appSessionId)
            put("app_receipt_id", state.appReceiptId)
            put("app_payload_sha256", state.appPayloadSha256)
            put("ticket_binding_mode", state.ticketBindingMode)
            put("browser_session_id", "browser-session-1")
            put("browser_receipt_id", "browser-receipt-1")
            put("browser_payload_sha256", "d".repeat(64))
        }

        val result = BrowserPairTransport.parseAndVerifyPoll(response, state)

        assertNotNull(result)
        assertTrue(result?.terminal == true)
        assertEquals("completed", result?.pairStatus)
    }

    @Test
    fun pendingPollIsNonTerminal() {
        val state = BrowserPairPollState(
            pairId = "hgpair-v1-1234",
            ticketRequestId = "ticket-request-1",
            pollToken = "poll-token-abcdefghijklmnopqrstuvwxyz",
            pollBaseUrl = "https://backend.example/api/collect/browser-pairs",
            browserStageUrl = "https://backend.example/api/collect/browser-stage",
            collectionBatchId = receipt.collectionBatchId,
            appSessionId = receipt.sessionId,
            appReceiptId = receipt.receiptId,
            appPayloadSha256 = receipt.payloadSha256,
            ticketBindingMode = BrowserPairTransport.BINDING_MODE_RECEIPT,
            expiresAt = "2030-01-01T00:00:00Z"
        )
        val response = JSONObject().apply {
            put("status", "success")
            put("pair_status", "awaiting_browser")
            put("pair_id", state.pairId)
            put("ticket_request_id", state.ticketRequestId)
            put("collection_batch_id", state.collectionBatchId)
            put("app_session_id", state.appSessionId)
            put("app_receipt_id", state.appReceiptId)
            put("app_payload_sha256", state.appPayloadSha256)
            put("ticket_binding_mode", state.ticketBindingMode)
        }

        val result = BrowserPairTransport.parseAndVerifyPoll(response, state)

        assertNotNull(result)
        assertFalse(result?.terminal ?: true)
    }

    @Test
    fun pendingPollCarriesBrowserStageForRelaunchSuppression() {
        val state = provisionalPollState()
        val response = pollResponse(state, "awaiting_browser").apply {
            put("latest_browser_stage", "page_loaded")
            put("latest_launch_attempt", 1)
            put("browser_stage_count", 1)
        }

        val result = BrowserPairTransport.parseAndVerifyPoll(response, state)

        assertEquals("page_loaded", result?.latestBrowserStage)
        assertEquals(1, result?.latestLaunchAttempt)
        assertEquals(1, result?.browserStageCount)
    }

    @Test
    fun expiredPollIsTerminalWithoutInventingBrowserEvidence() {
        val state = BrowserPairPollState(
            pairId = "hgpair-v1-1234",
            ticketRequestId = "ticket-request-1",
            pollToken = "poll-token-abcdefghijklmnopqrstuvwxyz",
            pollBaseUrl = "https://backend.example/api/collect/browser-pairs",
            browserStageUrl = "https://backend.example/api/collect/browser-stage",
            collectionBatchId = receipt.collectionBatchId,
            appSessionId = receipt.sessionId,
            appReceiptId = receipt.receiptId,
            appPayloadSha256 = receipt.payloadSha256,
            ticketBindingMode = BrowserPairTransport.BINDING_MODE_RECEIPT,
            expiresAt = "2030-01-01T00:00:00Z"
        )
        val response = JSONObject().apply {
            put("status", "success")
            put("pair_status", "expired")
            put("pair_id", state.pairId)
            put("ticket_request_id", state.ticketRequestId)
            put("collection_batch_id", state.collectionBatchId)
            put("app_session_id", state.appSessionId)
            put("app_receipt_id", state.appReceiptId)
            put("app_payload_sha256", state.appPayloadSha256)
            put("ticket_binding_mode", state.ticketBindingMode)
        }

        val result = BrowserPairTransport.parseAndVerifyPoll(response, state)

        assertNotNull(result)
        assertTrue(result?.terminal == true)
        assertEquals("expired", result?.pairStatus)
    }

    @Test
    fun backgroundReceiptHandoffRoundTripsWithItsOwningEndpoint() {
        val expected = PendingBrowserHandoff(
            receipt = receipt,
            collectEndpoint = "https://collector.example/api/collect/fingerprint",
            browserTicketRequestId = "ticket-request-1"
        )

        val parsed = PendingBrowserHandoff.fromJson(expected.toJson().toString())

        assertEquals(expected, parsed)
    }

    @Test
    fun malformedBackgroundReceiptHandoffFailsClosed() {
        assertNull(PendingBrowserHandoff.fromJson("""{"session_id":"missing-binding"}"""))
    }

    @Test
    fun rebuiltActivityCanPeekHandoffOwnedByPreviousAppSession() {
        val previousSessionReceipt = receipt.copy(sessionId = "previous-app-session")
        val handoff = PendingBrowserHandoff(
            receipt = previousSessionReceipt,
            collectEndpoint = "https://collector.example/api/collect/fingerprint",
            browserTicketRequestId = "ticket-request-1"
        )
        val serialized = handoff.toJson().toString()
        val entries = linkedMapOf<String, Any>(
            "new-activity-session" to """{"payload":"still pending"}""",
            "previous-app-session:browser_handoff" to serialized
        )

        val claim = ExpandedUploadWorker.selectPendingBrowserHandoff(entries)

        assertNotNull(claim)
        assertEquals(previousSessionReceipt, claim?.handoff?.receipt)
        assertEquals(serialized, entries["previous-app-session:browser_handoff"])
    }

    @Test
    fun handoffKeyMustMatchReceiptSessionBinding() {
        val handoff = PendingBrowserHandoff(
            receipt = receipt,
            collectEndpoint = "https://collector.example/api/collect/fingerprint",
            browserTicketRequestId = "ticket-request-1"
        )

        val claim = ExpandedUploadWorker.selectPendingBrowserHandoff(
            mapOf("different-session:browser_handoff" to handoff.toJson().toString())
        )

        assertNull(claim)
    }

    @Test
    fun acknowledgementOnlyMatchesTheExactPeekedRecord() {
        val handoff = PendingBrowserHandoff(
            receipt = receipt,
            collectEndpoint = "https://collector.example/api/collect/fingerprint",
            browserTicketRequestId = "ticket-request-1"
        )
        val serialized = handoff.toJson().toString()
        val claim = PendingBrowserHandoffClaim(
            storageKey = "${receipt.sessionId}:browser_handoff",
            serializedValue = serialized,
            handoff = handoff
        )
        val replacement = PendingBrowserHandoff(
            receipt = receipt.copy(receiptId = "fedcba9876543210fedcba98"),
            collectEndpoint = handoff.collectEndpoint,
            browserTicketRequestId = handoff.browserTicketRequestId
        ).toJson().toString()

        assertTrue(ExpandedUploadWorker.matchesPendingBrowserHandoffClaim(serialized, claim))
        assertFalse(ExpandedUploadWorker.matchesPendingBrowserHandoffClaim(replacement, claim))
        assertFalse(ExpandedUploadWorker.matchesPendingBrowserHandoffClaim(null, claim))
    }

    @Test
    fun handledMarkerMatchesOnlyItsStableTicketRequestId() {
        val marker = JSONObject().apply {
            put("browser_ticket_request_id", "stable-ticket-request")
            put("pair_id", "hgpair-v1-1234")
        }.toString()

        assertTrue(
            ExpandedUploadWorker.matchesBrowserTicketHandledMarker(
                marker,
                "stable-ticket-request"
            )
        )
        assertFalse(
            ExpandedUploadWorker.matchesBrowserTicketHandledMarker(
                marker,
                "different-ticket-request"
            )
        )
    }

    private fun provisionalPollState() = BrowserPairPollState(
        pairId = "hgpair-v1-1234",
        ticketRequestId = "ticket-request-1",
        pollToken = "poll-token-abcdefghijklmnopqrstuvwxyz",
        pollBaseUrl = "https://backend.example/api/collect/browser-pairs",
        browserStageUrl = "https://backend.example/api/collect/browser-stage",
        collectionBatchId = receipt.collectionBatchId,
        appSessionId = receipt.sessionId,
        appReceiptId = null,
        appPayloadSha256 = null,
        ticketBindingMode = BrowserPairTransport.BINDING_MODE_PROVISIONAL,
        expiresAt = "2030-01-01T00:00:00Z"
    )

    private fun pollResponse(
        state: BrowserPairPollState,
        pairStatus: String
    ) = JSONObject().apply {
        put("status", "success")
        put("pair_status", pairStatus)
        put("pair_id", state.pairId)
        put("ticket_request_id", state.ticketRequestId)
        put("collection_batch_id", state.collectionBatchId)
        put("app_session_id", state.appSessionId)
        put("app_receipt_id", state.appReceiptId ?: JSONObject.NULL)
        put("app_payload_sha256", state.appPayloadSha256 ?: JSONObject.NULL)
        put("ticket_binding_mode", state.ticketBindingMode)
    }

    private fun validTicketJson() = JSONObject().apply {
        put("status", "issued")
        put("pair_status", "awaiting_browser")
        put("pair_id", "hgpair-v1-1234")
        put("ticket_request_id", "ticket-request-1")
        put("browser_ticket", "browser-ticket-abcdefghijklmnopqrstuvwxyz")
        put("poll_token", "poll-token-abcdefghijklmnopqrstuvwxyz")
        put(
            "probe_url",
            "https://probe.example/collect/#pair_id=hgpair-v1-1234" +
                "&browser_ticket=browser-ticket-abcdefghijklmnopqrstuvwxyz" +
                "&browser_upload_url=https%3A%2F%2Fbackend.example%2Fapi%2Fcollect%2Fbrowser-fingerprint" +
                "&browser_stage_url=https%3A%2F%2Fbackend.example%2Fapi%2Fcollect%2Fbrowser-stage" +
                "&launch_attempt=1"
        )
        put(
            "browser_upload_url",
            "https://backend.example/api/collect/browser-fingerprint"
        )
        put(
            "browser_stage_url",
            "https://backend.example/api/collect/browser-stage"
        )
        put("expires_at", "2030-01-01T00:00:00Z")
        put("collection_batch_id", receipt.collectionBatchId)
        put("app_session_id", receipt.sessionId)
        put("app_receipt_id", receipt.receiptId)
        put("app_payload_sha256", receipt.payloadSha256)
        put("ticket_binding_mode", BrowserPairTransport.BINDING_MODE_RECEIPT)
        put("duplicate_ticket_request", false)
    }
}
