(function (global) {
    "use strict";

    // Auxiliary raw evidence. The canonical 67-field projection deliberately
    // keeps its original defaults and read time; this snapshot never replaces it.
    var REVISION = "webview-web-geometry-v1";
    var documentId = "document:" + Date.now().toString(36) + ":" +
        Math.random().toString(36).slice(2) + ":" + Math.random().toString(36).slice(2);

    function describe(error) {
        return String(error && error.name ? error.name + ":" + error.message : error);
    }

    function read(getter, type, unit) {
        try {
            var value = getter();
            if (value === undefined || value === null) {
                return { value: null, status: "unsupported", reason: "api_or_value_unavailable", unit: unit };
            }
            if (typeof value !== type) {
                return { value: value, status: "wrong_type", reason: "expected_" + type, unit: unit };
            }
            if (type === "number" && !Number.isFinite(value)) {
                return { value: null, status: "non_finite", reason: String(value), unit: unit };
            }
            return { value: value, status: "observed", reason: null, unit: unit };
        } catch (error) {
            return { value: null, status: "runtime_error", reason: describe(error), unit: unit };
        }
    }

    function optional(object, property) {
        return object == null ? undefined : object[property];
    }

    function capture(request) {
        request = request || {};
        var epochStart = Date.now();
        var performanceStart = read(function () { return global.performance.now(); }, "number", "ms");
        var fields = {};
        function field(name, getter, type, unit) {
            fields[name] = read(getter, type || "number", unit || "css_px");
        }
        // Identical platform getters to canonical getScreenFeatures; no || 0,
        // || 1 or -1 substitution. Additional document/offset fields are raw.
        field("inner_width", function () { return global.innerWidth; });
        field("inner_height", function () { return global.innerHeight; });
        field("outer_width", function () { return global.outerWidth; });
        field("outer_height", function () { return global.outerHeight; });
        field("document_client_width", function () { return optional(global.document.documentElement, "clientWidth"); });
        field("document_client_height", function () { return optional(global.document.documentElement, "clientHeight"); });
        field("screen_width", function () { return optional(global.screen, "width"); });
        field("screen_height", function () { return optional(global.screen, "height"); });
        field("avail_width", function () { return optional(global.screen, "availWidth"); });
        field("avail_height", function () { return optional(global.screen, "availHeight"); });
        field("avail_left", function () { return optional(global.screen, "availLeft"); });
        field("avail_top", function () { return optional(global.screen, "availTop"); });
        field("device_pixel_ratio", function () { return global.devicePixelRatio; }, "number", "ratio");
        ["width", "height", "scale", "offsetLeft", "offsetTop", "pageLeft", "pageTop"].forEach(function (property) {
            var suffix = property.replace(/[A-Z]/g, function (match) { return "_" + match.toLowerCase(); });
            field("visual_viewport_" + suffix, function () {
                return optional(global.visualViewport, property);
            }, "number", property === "scale" ? "ratio" : "css_px");
        });
        field("orientation_type", function () { return optional(optional(global.screen, "orientation"), "type"); }, "string", "enum");
        field("orientation_angle", function () { return optional(optional(global.screen, "orientation"), "angle"); }, "number", "degrees");
        field("viewport_meta", function () {
            var meta = global.document.querySelector('meta[name="viewport"]');
            return meta ? meta.getAttribute("content") : null;
        }, "string", "text");
        field("document_url", function () { return global.document.URL; }, "string", "url");
        field("document_ready_state", function () { return global.document.readyState; }, "string", "enum");
        field("document_compat_mode", function () { return global.document.compatMode; }, "string", "enum");
        var performanceEnd = read(function () { return global.performance.now(); }, "number", "ms");
        var timeOrigin = read(function () { return global.performance.timeOrigin; }, "number", "epoch_ms");
        return {
            schema_version: REVISION,
            read_status: Object.keys(fields).every(function (name) { return fields[name].status === "observed"; }) ? "observed" : "partial",
            binding: {
                session_id: request.session_id,
                webview_instance_id: request.webview_instance_id,
                document_generation: request.document_generation,
                observation_id: request.observation_id,
                attempt_id: request.attempt_id
            },
            document_id: documentId,
            clock: {
                epoch_start_ms: epochStart,
                epoch_end_ms: Date.now(),
                performance_start_ms: performanceStart.value,
                performance_end_ms: performanceEnd.value,
                time_origin_ms: timeOrigin.value,
                statuses: { performance_start: performanceStart, performance_end: performanceEnd, time_origin: timeOrigin },
                domains: { epoch: "javascript_Date_unix_ms", performance: "current_document_performance_ms" }
            },
            fields: fields,
            same_snapshot_as_legacy_screen_layer: false,
            timing_claim: "single_synchronous_javascript_call_not_cross_thread_atomic"
        };
    }

    global.HybridGuardWebViewGeometry = Object.freeze({
        REVISION: REVISION,
        documentId: documentId,
        capture: capture
    });
})(window);
