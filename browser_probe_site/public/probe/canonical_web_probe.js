(function (global) {
    "use strict";

    var REVISION = "expanded-web-67-v1";
    var STATUS_SCHEMA_VERSION = "browser-field-status-v1";
    var FIELD_PATHS = [
        "web_data.audio_layer.audio_context_supported",
        "web_data.audio_layer.audio_error",
        "web_data.audio_layer.audio_hash",
        "web_data.audio_layer.audio_output_latency",
        "web_data.audio_layer.audio_sample_rate",
        "web_data.automation_surface_layer.mime_types_count",
        "web_data.automation_surface_layer.mime_types_hash",
        "web_data.automation_surface_layer.plugin_probe_error",
        "web_data.automation_surface_layer.plugins_count",
        "web_data.automation_surface_layer.plugins_hash",
        "web_data.automation_surface_layer.webdriver",
        "web_data.execution_layer.compute_task_time_ms",
        "web_data.execution_layer.local_storage_available",
        "web_data.execution_layer.performance_time_origin",
        "web_data.execution_layer.session_storage_available",
        "web_data.execution_layer.timezone_id",
        "web_data.execution_layer.timezone_offset",
        "web_data.font_layer.available_font_hash",
        "web_data.font_layer.font_probe_count",
        "web_data.font_layer.font_probe_error",
        "web_data.graphics_layer.canvas_hash",
        "web_data.graphics_layer.webgl_aliased_line_width_range",
        "web_data.graphics_layer.webgl_extensions_count",
        "web_data.graphics_layer.webgl_max_texture_size",
        "web_data.graphics_layer.webgl_max_viewport_dims",
        "web_data.graphics_layer.webgl_renderer",
        "web_data.graphics_layer.webgl_vendor",
        "web_data.graphics_layer.webgl2_supported",
        "web_data.navigator_layer.cookie_enabled",
        "web_data.navigator_layer.device_memory",
        "web_data.navigator_layer.do_not_track",
        "web_data.navigator_layer.hardware_concurrency",
        "web_data.navigator_layer.language",
        "web_data.navigator_layer.languages",
        "web_data.navigator_layer.max_touch_points",
        "web_data.navigator_layer.online",
        "web_data.navigator_layer.platform",
        "web_data.navigator_layer.product",
        "web_data.navigator_layer.product_sub",
        "web_data.navigator_layer.user_agent",
        "web_data.navigator_layer.vendor",
        "web_data.network_api_layer.downlink_mbps",
        "web_data.network_api_layer.effective_type",
        "web_data.network_api_layer.rtt_ms",
        "web_data.network_api_layer.save_data",
        "web_data.permissions_layer.camera_permission_state",
        "web_data.permissions_layer.clipboard_read_state",
        "web_data.permissions_layer.geolocation_permission_state",
        "web_data.permissions_layer.microphone_permission_state",
        "web_data.permissions_layer.notification_permission_state",
        "web_data.permissions_layer.permission_query_errors",
        "web_data.permissions_layer.permissions_api_supported",
        "web_data.screen_layer.avail_height",
        "web_data.screen_layer.avail_width",
        "web_data.screen_layer.color_depth",
        "web_data.screen_layer.device_pixel_ratio",
        "web_data.screen_layer.inner_height",
        "web_data.screen_layer.inner_width",
        "web_data.screen_layer.orientation_angle",
        "web_data.screen_layer.orientation_type",
        "web_data.screen_layer.outer_height",
        "web_data.screen_layer.outer_width",
        "web_data.screen_layer.pixel_depth",
        "web_data.screen_layer.screen_resolution_logical",
        "web_data.screen_layer.visual_viewport_height",
        "web_data.screen_layer.visual_viewport_scale",
        "web_data.screen_layer.visual_viewport_width"
    ];

    function arrayFrom(value) {
        return Array.prototype.slice.call(value || []);
    }

    function isFiniteNumber(value) {
        return typeof value === "number" && isFinite(value);
    }

    function describeError(error) {
        var name = error && error.name ? error.name : "Error";
        var message = error && error.message ? ": " + error.message : "";
        return name + message;
    }

    function storageAvailable(type) {
        try {
            var storage = global[type];
            var key = "__hybridguard_probe__";
            storage.setItem(key, key);
            storage.removeItem(key);
            return true;
        } catch (_error) {
            return false;
        }
    }

    // Synchronous UTF-8 SHA-256 keeps WebView and full-browser hashes identical.
    function sha256(value) {
        var text = unescape(encodeURIComponent(String(value)));
        var maxWord = Math.pow(2, 32);
        var words = [];
        var bitLength = text.length * 8;
        var hash = [];
        var constants = [];
        var composite = {};
        var primeCounter = 0;
        var candidate = 2;
        var i;
        var j;

        while (primeCounter < 64) {
            if (!composite[candidate]) {
                for (i = candidate * candidate; i < 313; i += candidate) {
                    composite[i] = true;
                }
                if (primeCounter < 8) {
                    hash[primeCounter] = (Math.pow(candidate, 0.5) * maxWord) | 0;
                }
                constants[primeCounter] = (Math.pow(candidate, 1 / 3) * maxWord) | 0;
                primeCounter += 1;
            }
            candidate += 1;
        }

        text += "\x80";
        while (text.length % 64 !== 56) {
            text += "\x00";
        }
        for (i = 0; i < text.length; i += 1) {
            j = text.charCodeAt(i);
            words[i >> 2] |= j << ((3 - i) % 4) * 8;
        }
        words[words.length] = (bitLength / maxWord) | 0;
        words[words.length] = bitLength;

        for (j = 0; j < words.length;) {
            var schedule = words.slice(j, j += 16);
            var oldHash = hash.slice(0);
            var working = hash.slice(0, 8);
            for (i = 0; i < 64; i += 1) {
                var w15 = schedule[i - 15];
                var w2 = schedule[i - 2];
                var a = working[0];
                var e = working[4];
                var sigma0 = i < 16 ? 0 :
                    (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3));
                var sigma1 = i < 16 ? 0 :
                    (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10));
                var word = i < 16 ? schedule[i] :
                    (schedule[i - 16] + sigma0 + schedule[i - 7] + sigma1) | 0;
                schedule[i] = word;
                var choice = (e & working[5]) ^ ((~e) & working[6]);
                var majority = (a & working[1]) ^ (a & working[2]) ^ (working[1] & working[2]);
                var temp1 = (
                    working[7] +
                    (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)) +
                    choice +
                    constants[i] +
                    word
                ) | 0;
                var temp2 = (
                    (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)) +
                    majority
                ) | 0;
                working = [
                    (temp1 + temp2) | 0,
                    working[0],
                    working[1],
                    working[2],
                    (working[3] + temp1) | 0,
                    working[4],
                    working[5],
                    working[6]
                ];
            }
            for (i = 0; i < 8; i += 1) {
                hash[i] = (working[i] + oldHash[i]) | 0;
            }
        }

        var result = "";
        for (i = 0; i < 8; i += 1) {
            for (j = 3; j >= 0; j -= 1) {
                var byteValue = (hash[i] >> (j * 8)) & 255;
                result += (byteValue < 16 ? "0" : "") + byteValue.toString(16);
            }
        }
        return result;
    }

    function rightRotate(value, amount) {
        return (value >>> amount) | (value << (32 - amount));
    }

    function hashProbeValues(values) {
        var text = Array.isArray(values) ? values.join("|") : String(values || "");
        return text ? sha256(text) : "";
    }

    function defaultWebGLInfo() {
        return {
            context_available: false,
            vendor: "Unknown",
            renderer: "Unknown",
            webgl2_supported: false,
            webgl_extensions_count: 0,
            max_texture_size: -1,
            max_viewport_dims: "",
            aliased_line_width_range: ""
        };
    }

    function defaultNavigatorFeatures() {
        return {
            user_agent: "",
            language: "",
            languages: [],
            platform: "",
            vendor: "",
            product: "",
            product_sub: "",
            hardware_concurrency: 0,
            device_memory: 0,
            max_touch_points: 0,
            cookie_enabled: false,
            do_not_track: "",
            online: false
        };
    }

    function defaultScreenFeatures() {
        return {
            screen_resolution_logical: "",
            device_pixel_ratio: -1,
            color_depth: -1,
            pixel_depth: -1,
            avail_width: -1,
            avail_height: -1,
            inner_width: -1,
            inner_height: -1,
            outer_width: -1,
            outer_height: -1,
            visual_viewport_width: -1,
            visual_viewport_height: -1,
            visual_viewport_scale: -1,
            orientation_type: "",
            orientation_angle: -1
        };
    }

    function defaultExecutionFeatures() {
        return {
            compute_task_time_ms: -1,
            timezone_offset: 0,
            timezone_id: "",
            performance_time_origin: 0,
            local_storage_available: false,
            session_storage_available: false
        };
    }

    function defaultConnectionFeatures() {
        return {
            effective_type: "",
            downlink_mbps: -1,
            rtt_ms: -1,
            save_data: false
        };
    }

    function defaultAudioFeatures() {
        return {
            audio_context_supported: false,
            audio_sample_rate: -1,
            audio_output_latency: -1,
            audio_hash: "",
            audio_error: ""
        };
    }

    function defaultFontFeatures() {
        return {
            font_probe_count: 0,
            available_font_hash: "",
            font_probe_error: ""
        };
    }

    function defaultPermissionsFeatures() {
        return {
            permissions_api_supported: false,
            notification_permission_state: "unsupported",
            geolocation_permission_state: "unsupported",
            camera_permission_state: "unsupported",
            microphone_permission_state: "unsupported",
            clipboard_read_state: "unsupported",
            permission_query_errors: []
        };
    }

    function defaultAutomationFeatures() {
        return {
            webdriver: false,
            plugins_count: 0,
            mime_types_count: 0,
            plugins_hash: "",
            mime_types_hash: "",
            plugin_probe_error: ""
        };
    }

    function quoteCssFontName(fontName) {
        return "\"" + String(fontName).replace(/\\/g, "\\\\").replace(/"/g, "\\\"") + "\"";
    }

    function getWebGLInfo() {
        var canvas = document.createElement("canvas");
        var gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
        var gl2 = canvas.getContext("webgl2");
        var info = defaultWebGLInfo();
        info.context_available = !!gl;
        info.webgl2_supported = !!gl2;
        if (gl) {
            var debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
            if (debugInfo) {
                info.vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                info.renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            }
            var extensions = gl.getSupportedExtensions();
            info.webgl_extensions_count = extensions ? extensions.length : 0;
            info.max_texture_size = gl.getParameter(gl.MAX_TEXTURE_SIZE) || -1;
            info.max_viewport_dims = arrayFrom(gl.getParameter(gl.MAX_VIEWPORT_DIMS) || []).join("x");
            info.aliased_line_width_range =
                arrayFrom(gl.getParameter(gl.ALIASED_LINE_WIDTH_RANGE) || []).join("-");
        }
        return info;
    }

    function getNavigatorFeatures() {
        var nav = navigator;
        return {
            user_agent: nav.userAgent,
            language: nav.language || "",
            languages: arrayFrom(nav.languages || []),
            platform: nav.platform || "",
            vendor: nav.vendor || "",
            product: nav.product || "",
            product_sub: nav.productSub || "",
            hardware_concurrency: nav.hardwareConcurrency || 0,
            device_memory: nav.deviceMemory || 0,
            max_touch_points: nav.maxTouchPoints || 0,
            cookie_enabled: !!nav.cookieEnabled,
            do_not_track: nav.doNotTrack || "",
            online: !!nav.onLine
        };
    }

    function getScreenFeatures() {
        var vv = global.visualViewport;
        var orientation = screen.orientation || {};
        return {
            screen_resolution_logical: global.screen.width + "x" + global.screen.height,
            device_pixel_ratio: global.devicePixelRatio || 1,
            color_depth: screen.colorDepth || 0,
            pixel_depth: screen.pixelDepth || 0,
            avail_width: screen.availWidth || 0,
            avail_height: screen.availHeight || 0,
            inner_width: global.innerWidth || 0,
            inner_height: global.innerHeight || 0,
            outer_width: global.outerWidth || 0,
            outer_height: global.outerHeight || 0,
            visual_viewport_width: vv ? vv.width : -1,
            visual_viewport_height: vv ? vv.height : -1,
            visual_viewport_scale: vv ? vv.scale : -1,
            orientation_type: orientation.type || "",
            orientation_angle: isFiniteNumber(orientation.angle) ? orientation.angle : -1
        };
    }

    function runComputeChallenge() {
        var startTime = performance.now();
        var result = 0;
        for (var i = 0; i < 5000000; i += 1) {
            result += Math.sin(i) * Math.cos(i) + Math.tan(i % 100);
        }
        return {
            time_ms: parseFloat((performance.now() - startTime).toFixed(2)),
            guard: result
        };
    }

    function getExecutionFeatures() {
        var timeZone = (Intl.DateTimeFormat().resolvedOptions() || {}).timeZone || "";
        return {
            compute_task_time_ms: runComputeChallenge().time_ms,
            timezone_offset: new Date().getTimezoneOffset(),
            timezone_id: timeZone,
            performance_time_origin: performance.timeOrigin || 0,
            local_storage_available: storageAvailable("localStorage"),
            session_storage_available: storageAvailable("sessionStorage")
        };
    }

    function getConnectionFeatures() {
        var connection =
            navigator.connection || navigator.mozConnection || navigator.webkitConnection || {};
        return {
            effective_type: connection.effectiveType || "",
            downlink_mbps: isFiniteNumber(connection.downlink) ? connection.downlink : -1,
            rtt_ms: isFiniteNumber(connection.rtt) ? connection.rtt : -1,
            save_data: !!connection.saveData
        };
    }

    function getAudioFeatures() {
        var AudioContextCtor = global.AudioContext || global.webkitAudioContext;
        var OfflineAudioContextCtor =
            global.OfflineAudioContext || global.webkitOfflineAudioContext;
        var result = defaultAudioFeatures();
        result.audio_context_supported = !!(AudioContextCtor || OfflineAudioContextCtor);
        var errors = [];

        if (AudioContextCtor) {
            try {
                var audioContext = new AudioContextCtor();
                result.audio_sample_rate =
                    isFiniteNumber(audioContext.sampleRate) ? audioContext.sampleRate : -1;
                if (isFiniteNumber(audioContext.outputLatency)) {
                    result.audio_output_latency = audioContext.outputLatency;
                } else if (isFiniteNumber(audioContext.baseLatency)) {
                    result.audio_output_latency = audioContext.baseLatency;
                }
                if (audioContext.close) {
                    var closeResult = audioContext.close();
                    if (closeResult && closeResult.catch) {
                        closeResult.catch(function () {});
                    }
                }
            } catch (error) {
                errors.push("context:" + describeError(error));
            }
        }

        var renderPromise = Promise.resolve();
        if (OfflineAudioContextCtor) {
            try {
                var sampleRate =
                    result.audio_sample_rate > 0 ? Math.round(result.audio_sample_rate) : 44100;
                var offlineContext = new OfflineAudioContextCtor(1, 4096, sampleRate);
                var oscillator = offlineContext.createOscillator();
                var compressor = offlineContext.createDynamicsCompressor();
                oscillator.type = "triangle";
                oscillator.frequency.value = 10000;
                compressor.threshold.value = -50;
                compressor.knee.value = 40;
                compressor.ratio.value = 12;
                compressor.attack.value = 0;
                compressor.release.value = 0.25;
                oscillator.connect(compressor);
                compressor.connect(offlineContext.destination);
                oscillator.start(0);

                renderPromise = Promise.resolve(offlineContext.startRendering()).then(
                    function (renderedBuffer) {
                        var channelData = renderedBuffer.getChannelData(0);
                        var samples = [];
                        for (var index = 0; index < channelData.length; index += 128) {
                            samples.push(channelData[index].toFixed(8));
                        }
                        result.audio_hash = hashProbeValues(samples);
                    },
                    function (error) {
                        errors.push("offline:" + describeError(error));
                    }
                );
            } catch (error) {
                errors.push("offline:" + describeError(error));
            }
        } else {
            errors.push("offline:unavailable");
        }

        return renderPromise.then(function () {
            result.audio_error = errors.join("; ");
            return result;
        });
    }

    function getFontFeatures() {
        var result = defaultFontFeatures();
        try {
            var canvas = document.createElement("canvas");
            var context = canvas.getContext("2d");
            if (!context) {
                throw new Error("canvas_2d_unavailable");
            }
            var baseFonts = ["monospace", "sans-serif", "serif"];
            var testText = "mmmmmmmmmmlliMW@#12345";
            var testSize = "72px";
            var baseWidths = {};
            baseFonts.forEach(function (baseFont) {
                context.font = testSize + " " + baseFont;
                baseWidths[baseFont] = context.measureText(testText).width;
            });
            var candidateFonts = [
                "Arial",
                "Arial Black",
                "Courier New",
                "Droid Sans",
                "Droid Serif",
                "Droid Sans Mono",
                "Roboto",
                "Roboto Condensed",
                "Noto Sans",
                "Noto Serif",
                "Noto Color Emoji",
                "Noto Sans CJK SC",
                "Noto Sans CJK TC",
                "Noto Sans CJK JP",
                "SamsungOne",
                "MiSans",
                "HarmonyOS Sans",
                "Oppo Sans",
                "Source Han Sans",
                "sans-serif-light",
                "sans-serif-medium",
                "serif-monospace"
            ];
            var detectedFonts = candidateFonts.filter(function (fontName) {
                return baseFonts.some(function (baseFont) {
                    context.font =
                        testSize + " " + quoteCssFontName(fontName) + ", " + baseFont;
                    return Math.abs(context.measureText(testText).width - baseWidths[baseFont]) > 0.01;
                });
            }).sort();
            result.font_probe_count = detectedFonts.length;
            result.available_font_hash = hashProbeValues(detectedFonts);
        } catch (error) {
            result.font_probe_error = describeError(error);
        }
        return result;
    }

    function getPermissionsFeatures() {
        var result = defaultPermissionsFeatures();
        result.permissions_api_supported =
            !!(navigator.permissions && navigator.permissions.query);
        result.notification_permission_state =
            typeof Notification !== "undefined" ? Notification.permission : "unsupported";
        if (!result.permissions_api_supported) {
            return Promise.resolve(result);
        }
        var queries = [
            ["notifications", "notification_permission_state"],
            ["geolocation", "geolocation_permission_state"],
            ["camera", "camera_permission_state"],
            ["microphone", "microphone_permission_state"],
            ["clipboard-read", "clipboard_read_state"]
        ];
        return Promise.all(queries.map(function (query) {
            return Promise.resolve(navigator.permissions.query({ name: query[0] })).then(
                function (status) {
                    result[query[1]] = status && status.state ? status.state : "unknown";
                },
                function (error) {
                    result.permission_query_errors.push(query[0] + ":" + describeError(error));
                }
            );
        })).then(function () {
            result.permission_query_errors.sort();
            return result;
        });
    }

    function getAutomationFeatures() {
        var result = defaultAutomationFeatures();
        result.webdriver = navigator.webdriver === true;
        result.plugins_count = navigator.plugins ? navigator.plugins.length : 0;
        result.mime_types_count = navigator.mimeTypes ? navigator.mimeTypes.length : 0;
        try {
            var pluginSummaries = arrayFrom(navigator.plugins || []).map(function (plugin) {
                var pluginMimeTypes = [];
                for (var index = 0; index < plugin.length; index += 1) {
                    var mime = plugin[index];
                    pluginMimeTypes.push([mime.type || "", mime.suffixes || ""].join(":"));
                }
                return [
                    plugin.name || "",
                    plugin.filename || "",
                    plugin.description || "",
                    pluginMimeTypes.sort().join(",")
                ].join("~");
            }).sort();
            var mimeTypeSummaries = arrayFrom(navigator.mimeTypes || []).map(function (mime) {
                return [
                    mime.type || "",
                    mime.suffixes || "",
                    mime.description || "",
                    mime.enabledPlugin ? mime.enabledPlugin.name : ""
                ].join("~");
            }).sort();
            result.plugins_hash = hashProbeValues(pluginSummaries);
            result.mime_types_hash = hashProbeValues(mimeTypeSummaries);
        } catch (error) {
            result.plugin_probe_error = describeError(error);
        }
        return result;
    }

    function getCanvasFingerprint(container) {
        var canvas = document.createElement("canvas");
        canvas.width = 250;
        canvas.height = 50;
        var context = canvas.getContext("2d");
        if (!context) {
            throw new Error("canvas_2d_unavailable");
        }
        context.textBaseline = "top";
        context.font =
            "14px -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif";
        context.fillStyle = "rgba(0, 113, 227, 0.2)";
        context.fillRect(125, 1, 62, 20);
        context.fillStyle = "rgba(29, 29, 31, 0.8)";
        context.fillText("HybridGuard 2026", 2, 15);
        context.fillStyle = "rgba(52, 199, 89, 0.5)";
        context.fillText("HybridGuard 2026", 4, 17);
        context.font = "20px -apple-system";
        context.fillText("HG", 180, 10);
        if (container) {
            container.style.display = "block";
            container.appendChild(canvas);
        }
        return sha256(canvas.toDataURL());
    }

    function buildWebData(parts) {
        return {
            navigator_layer: parts.navigatorInfo,
            screen_layer: parts.screenInfo,
            graphics_layer: {
                webgl_vendor: parts.webglInfo.vendor,
                webgl_renderer: parts.webglInfo.renderer,
                webgl_extensions_count: parts.webglInfo.webgl_extensions_count,
                webgl2_supported: parts.webglInfo.webgl2_supported,
                webgl_max_texture_size: parts.webglInfo.max_texture_size,
                webgl_max_viewport_dims: parts.webglInfo.max_viewport_dims,
                webgl_aliased_line_width_range: parts.webglInfo.aliased_line_width_range,
                canvas_hash: parts.canvasHash
            },
            execution_layer: parts.executionInfo,
            network_api_layer: parts.connectionInfo,
            audio_layer: parts.audioInfo,
            font_layer: parts.fontInfo,
            permissions_layer: parts.permissionsInfo,
            automation_surface_layer: parts.automationInfo
        };
    }

    function defaultWebData() {
        return buildWebData({
            navigatorInfo: defaultNavigatorFeatures(),
            screenInfo: defaultScreenFeatures(),
            webglInfo: defaultWebGLInfo(),
            executionInfo: defaultExecutionFeatures(),
            connectionInfo: defaultConnectionFeatures(),
            audioInfo: defaultAudioFeatures(),
            fontInfo: defaultFontFeatures(),
            permissionsInfo: defaultPermissionsFeatures(),
            automationInfo: defaultAutomationFeatures(),
            canvasHash: ""
        });
    }

    function probeNameForField(fieldPath) {
        if (/\.canvas_hash$/.test(fieldPath)) {
            return "canvas";
        }
        if (fieldPath.indexOf("web_data.navigator_layer.") === 0) {
            return "navigator";
        }
        if (fieldPath.indexOf("web_data.screen_layer.") === 0) {
            return "screen";
        }
        if (fieldPath.indexOf("web_data.graphics_layer.") === 0) {
            return "webgl";
        }
        if (fieldPath.indexOf("web_data.execution_layer.") === 0) {
            return "execution";
        }
        if (fieldPath.indexOf("web_data.network_api_layer.") === 0) {
            return "connection";
        }
        if (fieldPath.indexOf("web_data.audio_layer.") === 0) {
            return "audio";
        }
        if (fieldPath.indexOf("web_data.font_layer.") === 0) {
            return "font";
        }
        if (fieldPath.indexOf("web_data.permissions_layer.") === 0) {
            return "permissions";
        }
        if (fieldPath.indexOf("web_data.automation_surface_layer.") === 0) {
            return "automation";
        }
        return "";
    }

    function hasPath(root, fieldPath) {
        var current = root;
        var parts = fieldPath.split(".");
        for (var index = 0; index < parts.length; index += 1) {
            if (
                current === null ||
                typeof current !== "object" ||
                !Object.prototype.hasOwnProperty.call(current, parts[index])
            ) {
                return false;
            }
            current = current[parts[index]];
        }
        return current !== null && typeof current !== "undefined";
    }

    function normalizeStatus(status) {
        return [
            "observed",
            "unsupported_by_os",
            "permission_denied",
            "runtime_error",
            "timeout",
            "not_applicable"
        ].indexOf(status) >= 0 ? status : "runtime_error";
    }

    function buildCollectionStatus(webData, probeStatuses) {
        var root = { web_data: webData };
        var fields = {};
        var counts = {
            observed: 0,
            unsupported_by_os: 0,
            permission_denied: 0,
            runtime_error: 0,
            timeout: 0,
            not_applicable: 0
        };
        FIELD_PATHS.forEach(function (fieldPath) {
            var probeStatus = probeStatuses[probeNameForField(fieldPath)] || "observed";
            var status = probeStatus === "observed" && hasPath(root, fieldPath) ?
                "observed" :
                normalizeStatus(probeStatus === "observed" ? "runtime_error" : probeStatus);
            fields[fieldPath] = status;
            counts[status] += 1;
        });
        return {
            status_schema_version: STATUS_SCHEMA_VERSION,
            fixed_signal_count: FIELD_PATHS.length,
            counts: counts,
            probe_statuses: probeStatuses,
            fields: fields
        };
    }

    function collect(options) {
        options = options || {};
        var probeStatuses = {};
        var logger = typeof options.onLog === "function" ? options.onLog : function () {};

        function probeKey(name) {
            return String(name || "unknown").toLowerCase().replace(/\s+/g, "_");
        }

        function safeSyncProbe(name, probe, fallbackFactory) {
            try {
                var result = probe();
                probeStatuses[probeKey(name)] = "observed";
                return result;
            } catch (error) {
                probeStatuses[probeKey(name)] = "runtime_error";
                logger(name + " probe degraded: " + describeError(error), "bad");
                return fallbackFactory();
            }
        }

        function safeAsyncProbe(name, probe, fallbackFactory, timeoutMs) {
            var timeoutId;
            var timeout = new Promise(function (_resolve, reject) {
                timeoutId = setTimeout(function () {
                    reject(new Error(name + " timeout"));
                }, timeoutMs);
            });
            return Promise.race([Promise.resolve().then(probe), timeout]).then(
                function (value) {
                    clearTimeout(timeoutId);
                    probeStatuses[probeKey(name)] = "observed";
                    return value;
                },
                function (error) {
                    clearTimeout(timeoutId);
                    probeStatuses[probeKey(name)] =
                        /timeout/i.test(describeError(error)) ? "timeout" : "runtime_error";
                    logger(name + " probe degraded: " + describeError(error), "bad");
                    return fallbackFactory();
                }
            );
        }

        var webglInfo = safeSyncProbe("WebGL", getWebGLInfo, defaultWebGLInfo);
        if (!webglInfo.context_available) {
            probeStatuses.webgl = "not_applicable";
            logger("WebGL context unavailable; emitted canonical fallback values", "bad");
        }
        var navigatorInfo =
            safeSyncProbe("Navigator", getNavigatorFeatures, defaultNavigatorFeatures);
        var screenInfo = safeSyncProbe("Screen", getScreenFeatures, defaultScreenFeatures);
        var executionInfo =
            safeSyncProbe("Execution", getExecutionFeatures, defaultExecutionFeatures);
        var connectionInfo =
            safeSyncProbe("Connection", getConnectionFeatures, defaultConnectionFeatures);
        var fontInfo = safeSyncProbe("Font", getFontFeatures, defaultFontFeatures);
        var automationInfo =
            safeSyncProbe("Automation", getAutomationFeatures, defaultAutomationFeatures);
        var canvasHash = safeSyncProbe(
            "Canvas",
            function () {
                return getCanvasFingerprint(options.canvasContainer || null);
            },
            function () {
                return "";
            }
        );
        var audioPromise = safeAsyncProbe(
            "Audio",
            getAudioFeatures,
            function () {
                var fallback = defaultAudioFeatures();
                fallback.audio_error = "probe_timeout_or_error";
                return fallback;
            },
            2500
        );
        var permissionsPromise = safeAsyncProbe(
            "Permissions",
            getPermissionsFeatures,
            defaultPermissionsFeatures,
            1500
        );

        return Promise.all([audioPromise, permissionsPromise]).then(function (asyncValues) {
            var webData = buildWebData({
                navigatorInfo: navigatorInfo,
                screenInfo: screenInfo,
                webglInfo: webglInfo,
                executionInfo: executionInfo,
                connectionInfo: connectionInfo,
                audioInfo: asyncValues[0],
                fontInfo: fontInfo,
                permissionsInfo: asyncValues[1],
                automationInfo: automationInfo,
                canvasHash: canvasHash
            });
            return {
                web_data: webData,
                probe_statuses: probeStatuses,
                collection_status: buildCollectionStatus(webData, probeStatuses)
            };
        });
    }

    global.HybridGuardWebProbe = Object.freeze({
        REVISION: REVISION,
        STATUS_SCHEMA_VERSION: STATUS_SCHEMA_VERSION,
        FIELD_PATHS: Object.freeze(FIELD_PATHS.slice(0)),
        sha256: sha256,
        collect: collect,
        defaultWebData: defaultWebData,
        buildCollectionStatus: buildCollectionStatus,
        describeError: describeError
    });
})(window);
