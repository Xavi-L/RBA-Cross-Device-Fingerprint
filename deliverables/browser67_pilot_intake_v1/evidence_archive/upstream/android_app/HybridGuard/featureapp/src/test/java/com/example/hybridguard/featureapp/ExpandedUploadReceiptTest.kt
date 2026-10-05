package com.example.hybridguard.featureapp

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ExpandedUploadReceiptTest {
    @Test
    fun completeReceiptEnvelopeIsAccepted() {
        val payload = JSONObject().apply {
            put("session_id", "app-session-1")
            put("timestamp", 1234)
            put("collector_app", "featureapp")
            put("schema_version", "expanded-v2.2-status")
        }
        val response = JSONObject().apply {
            put("status", "success")
            put("session_id", "app-session-1")
            put(
                "receipt",
                JSONObject().apply {
                    put("receipt_schema_version", "collection-receipt-v1")
                    put("receipt_id", "0123456789abcdef01234567")
                    put("session_id", "app-session-1")
                    put("payload_sha256", "a".repeat(64))
                    put("collector_app", "featureapp")
                    put("schema_version", "expanded-v2.2-status")
                    put("storage_target", "expanded_collected_data.jsonl")
                    put("validation_status", "accepted")
                    put("validation_warnings", JSONArray())
                    put("collection_batch_id", "hgbatch-v1-test")
                }
            )
        }

        val receipt = ExpandedUploadTransport.parseAndVerifyReceipt(
            payload.toString(),
            response.toString()
        )

        assertNotNull(receipt)
        assertEquals("0123456789abcdef01234567", receipt?.receiptId)
        assertEquals("a".repeat(64), receipt?.payloadSha256)
        assertEquals("hgbatch-v1-test", receipt?.collectionBatchId)
    }

    @Test
    fun receiptWithDifferentSessionIsRejected() {
        val payload = JSONObject().apply {
            put("session_id", "app-session-1")
            put("timestamp", 1234)
            put("collector_app", "featureapp")
            put("schema_version", "expanded-v2.2-status")
        }
        val response = JSONObject().apply {
            put("status", "success")
            put("session_id", "app-session-1")
            put(
                "receipt",
                JSONObject().apply {
                    put("receipt_schema_version", "collection-receipt-v1")
                    put("receipt_id", "0123456789abcdef01234567")
                    put("session_id", "different-session")
                    put("payload_sha256", "a".repeat(64))
                    put("collector_app", "featureapp")
                    put("schema_version", "expanded-v2.2-status")
                    put("storage_target", "expanded_collected_data.jsonl")
                    put("validation_status", "accepted")
                    put("validation_warnings", JSONArray())
                    put("collection_batch_id", "hgbatch-v1-test")
                }
            )
        }

        assertNull(
            ExpandedUploadTransport.parseAndVerifyReceipt(
                payload.toString(),
                response.toString()
            )
        )
    }
}
