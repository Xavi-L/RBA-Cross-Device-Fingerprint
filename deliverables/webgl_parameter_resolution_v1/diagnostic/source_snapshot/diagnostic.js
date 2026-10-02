(function (global) {
    "use strict";
    function session() {
        return global.AndroidBridge && global.AndroidBridge.getSessionId ? global.AndroidBridge.getSessionId() : null;
    }
    function drain(gl, label, events, details) {
        var errors = [], code = gl.getError(), count = 0;
        while (code !== 0 && count < 8) {
            errors.push(code); count += 1; code = gl.getError();
        }
        var event = {operation: label, errors: errors, drained: code === 0};
        if (details) { event.result = details; }
        events.push(event);
        return event;
    }
    function sample(gl, value, events) {
        var result = gl.getParameter(value);
        drain(gl, "getParameter", events, {argument: value, argument_kind: typeof value,
            value_kind: result === null ? "null" : typeof result,
            value: typeof result === "string" || typeof result === "number" || result === null ? result : null});
    }
    function context(type, profile) {
        var row = {context_type: type, profile: profile, status: "STARTED", events: []};
        try {
            var canvas = global.document.createElement("canvas");
            canvas.width = canvas.height = 8;
            var gl = canvas.getContext(type, {antialias: false});
            if (!gl) { row.status = "UNAVAILABLE"; return row; }
            row.context_created = true;
            if (profile === "error_first") {
                // The first API call after creation is getError, without isContextLost.
                drain(gl, "after_context_creation", row.events);
                var initialLost = gl.isContextLost();
                drain(gl, "after_isContextLost", row.events, {context_lost: initialLost});
            }
            var ext = gl.getExtension("WEBGL_debug_renderer_info");
            row.extension_available = ext !== null;
            row.extension_constants = ext ? {vendor: ext.UNMASKED_VENDOR_WEBGL, renderer: ext.UNMASKED_RENDERER_WEBGL} : null;
            if (profile === "observer_order") {
                var observerLost = gl.isContextLost();
                drain(gl, "after_extension_and_isContextLost", row.events, {context_lost: observerLost});
            } else {
                drain(gl, "after_getExtension_and_constants", row.events);
                if (profile === "extension_first") {
                    var extensionLost = gl.isContextLost();
                    drain(gl, "after_isContextLost", row.events, {context_lost: extensionLost});
                }
            }
            [34921, 37445, 37446].forEach(function (parameter) {
                if (parameter !== 34921 && !ext) { return; }
                sample(gl, parameter, row.events);
                sample(gl, String(parameter), row.events);
                sample(gl, parameter, row.events);
            });
            row.context_lost_at_end = gl.isContextLost();
            drain(gl, "final_context_check", row.events);
            row.status = "MEASURED";
        } catch (error) {
            row.status = "FAILED";
            row.exception = String(error);
        }
        return row;
    }
    global.HybridGuardWebGLDiagnostic = {run: function (profiles) {
        var result = {schema: "webgl-error-localization-v1", url: global.location.href,
            session_id_before: session(), contexts: []};
        profiles.forEach(function (profile) {
            ["webgl", "webgl2"].forEach(function (type) { result.contexts.push(context(type, profile)); });
        });
        result.session_id_after = session();
        return result;
    }};
}(window));
