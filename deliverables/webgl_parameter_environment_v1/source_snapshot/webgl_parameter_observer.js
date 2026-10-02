(function (global) {
    "use strict";

    var SCHEMA = "webgl-parameter-equivalence-observation-v1";
    var REVISION = "webgl-parameter-observer-v1";
    var SCOPE = "fresh-webgl-contexts-v1";
    var MAX_DRAIN = 8;

    function errorText(error) {
        try { return String(error).slice(0, 300); }
        catch (ignored) { return "unprintable_error"; }
    }

    function errorState(gl) {
        var state = {read_status: "runtime_error", errors: [], drained: false};
        try {
            state.context_lost_before = gl.isContextLost();
            var code = gl.getError();
            var count = 0;
            while (code !== 0 && count < MAX_DRAIN) {
                state.errors.push(code);
                count += 1;
                code = gl.getError();
            }
            state.drained = code === 0;
            state.context_lost_after = gl.isContextLost();
            state.read_status = "observed";
        } catch (error) {
            state.exception = errorText(error);
        }
        return state;
    }

    function query(gl, argument) {
        var before = errorState(gl);
        var sample = {
            argument: argument,
            argument_kind: typeof argument,
            read_status: "not_attempted",
            pre_errors: before.errors,
            drained: before.drained,
            context_lost_before: before.context_lost_before
        };
        if (before.read_status !== "observed" || !before.drained ||
                before.context_lost_before !== false || before.context_lost_after !== false) {
            sample.context_lost_after = before.context_lost_after;
            if (before.exception) { sample.exception = before.exception; }
            return sample;
        }
        try {
            var value = gl.getParameter(argument);
            sample.value_kind = value === null ? "null" : typeof value;
            // The profile expects primitive strings/numbers. Keep unexpected
            // types explicit without serializing arbitrary browser objects.
            sample.value = value === null || typeof value === "string" ||
                typeof value === "boolean" || (typeof value === "number" && isFinite(value)) ? value : null;
            sample.error = gl.getError();
            sample.context_lost_after = gl.isContextLost();
            sample.read_status = "observed";
        } catch (error) {
            sample.read_status = "runtime_error";
            sample.exception = errorText(error);
        }
        return sample;
    }

    function triplet(gl, parameter) {
        return {
            numeric_before: query(gl, parameter),
            numeric_string: query(gl, String(parameter)),
            numeric_after: query(gl, parameter)
        };
    }

    function contextObservation(type) {
        var row = {
            context_type: type,
            context_creation_status: "not_attempted",
            extension_read_status: "not_attempted",
            extension_available: null,
            extension_constants: null,
            preflight: null,
            control: null,
            parameters: {},
            context_lost_at_end: null
        };
        try {
            var canvas = global.document.createElement("canvas");
            canvas.width = canvas.height = 8;
            var gl = canvas.getContext(type, {antialias: false});
            row.context_creation_status = gl ? "observed" : "unavailable";
            if (!gl) { return row; }
            // Do not run the earlier extension-disabled H1 experiment here.
            // This version captures only H2 and an ordinary GLenum control.
            var extension;
            try {
                extension = gl.getExtension("WEBGL_debug_renderer_info");
                row.extension_available = extension !== null;
                if (extension) {
                    row.extension_constants = {
                        vendor: extension.UNMASKED_VENDOR_WEBGL,
                        renderer: extension.UNMASKED_RENDERER_WEBGL
                    };
                }
                row.extension_read_status = "observed";
            } catch (error) {
                row.extension_read_status = "runtime_error";
                row.extension_exception = errorText(error);
                row.context_lost_at_end = gl.isContextLost();
                return row;
            }
            // Initialization/extension errors remain explicit. The evaluator
            // treats a nonempty preflight as UNKNOWN even if draining succeeds.
            row.preflight = errorState(gl);
            if (row.preflight.read_status === "observed" && row.preflight.drained &&
                    row.preflight.context_lost_before === false && row.preflight.context_lost_after === false) {
                row.control = {
                    parameter: "MAX_VERTEX_ATTRIBS",
                    enum_value: 34921,
                    queries: triplet(gl, 34921)
                };
                if (row.extension_available && row.extension_constants &&
                        row.extension_constants.vendor === 37445 && row.extension_constants.renderer === 37446) {
                    row.parameters.vendor = triplet(gl, 37445);
                    row.parameters.renderer = triplet(gl, 37446);
                }
            }
            row.context_lost_at_end = gl.isContextLost();
        } catch (error) {
            if (row.context_creation_status === "not_attempted") {
                row.context_creation_status = "runtime_error";
            }
            row.exception = errorText(error);
        }
        return row;
    }

    function observe(options) {
        options = options || {};
        if (typeof options.realmBinding !== "string" || !options.realmBinding.trim()) {
            throw new Error("webgl_parameter_realm_binding_required");
        }
        return {
            observation_schema_version: SCHEMA,
            observer_revision: REVISION,
            observation_scope: SCOPE,
            realm_binding: options.realmBinding,
            contexts: [contextObservation("webgl"), contextObservation("webgl2")]
        };
    }

    // Loading this script performs no reads, creates no canvases and installs
    // no event listeners. Collection requires an explicit observe() call.
    global.HybridGuardWebGLParameterObserver = {
        OBSERVATION_SCHEMA_VERSION: SCHEMA,
        REVISION: REVISION,
        OBSERVATION_SCOPE: SCOPE,
        observe: observe
    };
}(typeof window !== "undefined" ? window : this));
