function hybridGuardBehaviorFeasibilityProbe() {
    "use strict";
    const started = performance.now();
    const result = {
        schema: "webgl-behavior-probe-v1",
        session_id: window.AndroidBridge.getSessionId(),
        url: location.href,
        canonical_probe_revision: window.HybridGuardWebProbe.REVISION,
        contexts: []
    };
    for (const type of ["webgl", "webgl2"]) {
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 8;
        const row = {type, status: "STARTED", width: 8, height: 8};
        result.contexts.push(row);
        let gl;
        try {
            gl = canvas.getContext(type, {antialias: false, preserveDrawingBuffer: true});
            if (!gl) { row.status = "UNAVAILABLE"; continue; }
            row.context_attributes = gl.getContextAttributes();
            function measure(fn) {
                const before = [];
                let e = gl.getError();
                for (let i = 0; e !== gl.NO_ERROR && i < 8; i++) {
                    before.push(e); e = gl.getError();
                }
                const sample = {pre_errors: before, drained: e === gl.NO_ERROR,
                    context_lost_before: gl.isContextLost()};
                try {
                    const value = fn();
                    sample.value_kind = value === null ? "null" : typeof value;
                    sample.value = value === undefined ? null : value;
                    sample.error = gl.getError();
                } catch (error) {
                    sample.exception = String(error);
                }
                sample.context_lost_after = gl.isContextLost();
                return sample;
            }
            const query = arg => ({argument: arg, argument_kind: typeof arg,
                ...measure(() => gl.getParameter(arg))});
            // Fresh context: no getExtension call has occurred on this context.
            row.extension_disabled = {
                vendor: query(37445), renderer: query(37446)
            };
            const ext = gl.getExtension("WEBGL_debug_renderer_info");
            row.extension_available = ext !== null;
            row.extension_constants = ext ? {vendor: ext.UNMASKED_VENDOR_WEBGL,
                renderer: ext.UNMASKED_RENDERER_WEBGL} : null;
            row.extension_enabled = {};
            if (ext) {
                for (const [name, enumValue] of [["vendor", 37445], ["renderer", 37446]]) {
                    row.extension_enabled[name] = {
                        numeric_before: query(enumValue),
                        numeric_string: query(String(enumValue)),
                        numeric_after: query(enumValue)
                    };
                }
            }
            // Positive control for the same WebIDL numeric conversion.
            row.capability = {numeric: query(gl.MAX_VERTEX_ATTRIBS),
                numeric_string: query(String(gl.MAX_VERTEX_ATTRIBS))};
            const limit = row.capability.numeric.value;
            if (Number.isInteger(limit) && limit > 0 && limit <= 1024) {
                row.capability.last_valid_index = measure(() => gl.enableVertexAttribArray(limit - 1));
                gl.disableVertexAttribArray(limit - 1);
                row.capability.first_invalid_index = measure(() => gl.enableVertexAttribArray(limit));
            }
            // A tiny real GPU/translator workload, independent of vendor strings.
            // It validates execution only; pixels are not a hardware identity.
            row.render = measure(() => {
                const vertex = type === "webgl2"
                    ? "#version 300 es\nin vec2 position; void main(){gl_Position=vec4(position,0.0,1.0);}"
                    : "attribute vec2 position; void main(){gl_Position=vec4(position,0.0,1.0);}";
                const fragment = type === "webgl2"
                    ? "#version 300 es\nprecision mediump float; out vec4 color; void main(){color=vec4(1.0,0.0,0.0,1.0);}"
                    : "precision mediump float; void main(){gl_FragColor=vec4(1.0,0.0,0.0,1.0);}";
                const shaders = [];
                const logs = [];
                for (const [shaderType, source] of [[gl.VERTEX_SHADER, vertex], [gl.FRAGMENT_SHADER, fragment]]) {
                    const shader = gl.createShader(shaderType);
                    gl.shaderSource(shader, source); gl.compileShader(shader);
                    shaders.push(shader);
                    logs.push({compiled: gl.getShaderParameter(shader, gl.COMPILE_STATUS),
                        log: gl.getShaderInfoLog(shader)});
                }
                const program = gl.createProgram();
                for (const shader of shaders) gl.attachShader(program, shader);
                gl.bindAttribLocation(program, 0, "position");
                gl.linkProgram(program);
                const linked = gl.getProgramParameter(program, gl.LINK_STATUS);
                const programLog = gl.getProgramInfoLog(program);
                if (!linked || logs.some(log => !log.compiled)) {
                    return {status: "COMPILE_OR_LINK_FAILED", shaders: logs, linked, program_log: programLog};
                }
                gl.useProgram(program);
                const buffer = gl.createBuffer();
                gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
                gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
                gl.enableVertexAttribArray(0);
                gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
                gl.viewport(0, 0, 8, 8);
                gl.disable(gl.DITHER);
                gl.clearColor(0, 0, 1, 1); gl.clear(gl.COLOR_BUFFER_BIT);
                gl.drawArrays(gl.TRIANGLES, 0, 3);
                const pixels = new Uint8Array(8 * 8 * 4);
                gl.readPixels(0, 0, 8, 8, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
                gl.disableVertexAttribArray(0);
                gl.deleteBuffer(buffer); gl.deleteProgram(program);
                for (const shader of shaders) gl.deleteShader(shader);
                return {status: "EXECUTED", shaders: logs, linked, program_log: programLog,
                    pixels: Array.from(pixels)};
            });
            row.context_lost_at_end = gl.isContextLost();
            row.status = "MEASURED";
        } catch (error) {
            row.status = "RUNTIME_ERROR";
            row.exception = String(error.stack || error);
        }
    }
    result.session_id_after = window.AndroidBridge.getSessionId();
    result.elapsed_ms = performance.now() - started;
    return result;
}
