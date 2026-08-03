(function (global) {
    "use strict";

    var statusEl = document.getElementById("status");
    var subtitleEl = document.getElementById("subtitle");
    var logEl = document.getElementById("log");
    var canvasBox = document.getElementById("canvasBox");

    function setStatus(text) {
        statusEl.textContent = text;
    }

    function log(text, cls) {
        var paragraph = document.createElement("p");
        paragraph.className = "line" + (cls ? " " + cls : "");
        paragraph.textContent = text;
        logEl.appendChild(paragraph);
        logEl.scrollTop = logEl.scrollHeight;
    }

    function sleep(milliseconds) {
        return new Promise(function (resolve) {
            setTimeout(resolve, milliseconds);
        });
    }

    function assignObject(target, source) {
        Object.keys(source || {}).forEach(function (key) {
            target[key] = source[key];
        });
        return target;
    }

    function defaultHostData() {
        return {
            webview_provider_package: "",
            webview_provider_version: "",
            webview_provider_version_code: -1,
            webview_provider_major: -1,
            system_http_agent: "",
            default_ua_native: "",
            is_debuggable: false,
            app_package_name: "",
            app_version_name: "",
            app_version_code: -1,
            installer_package: "unknown",
            is_cleartext_traffic_permitted: false,
            first_install_time: -1,
            last_update_time: -1,
            target_sdk_version: -1,
            min_sdk_version: -1,
            java_script_enabled: true,
            dom_storage_enabled: true,
            database_enabled: false,
            allow_file_access: false,
            allow_content_access: false,
            mixed_content_mode: -1,
            safe_browsing_enabled: false,
            settings_user_agent: ""
        };
    }

    function buildWebViewData(hostData, bridgeLatencyMs) {
        return {
            bridge_routing_layer: {
                jsbridge_injected: true,
                bridge_latency_ms: bridgeLatencyMs
            },
            kernel_container_layer: {
                webview_provider_package: hostData.webview_provider_package,
                webview_provider_version: hostData.webview_provider_version,
                webview_provider_version_code: hostData.webview_provider_version_code,
                webview_provider_major: hostData.webview_provider_major,
                system_http_agent: hostData.system_http_agent,
                default_ua_native: hostData.default_ua_native
            },
            host_security_layer: {
                is_debuggable: hostData.is_debuggable,
                app_package_name: hostData.app_package_name,
                app_version_name: hostData.app_version_name,
                app_version_code: hostData.app_version_code,
                installer_package: hostData.installer_package,
                is_cleartext_traffic_permitted: hostData.is_cleartext_traffic_permitted
            },
            temporal_build_layer: {
                first_install_time: hostData.first_install_time,
                last_update_time: hostData.last_update_time,
                target_sdk_version: hostData.target_sdk_version,
                min_sdk_version: hostData.min_sdk_version
            },
            webview_settings_layer: {
                java_script_enabled: hostData.java_script_enabled,
                dom_storage_enabled: hostData.dom_storage_enabled,
                database_enabled: hostData.database_enabled,
                allow_file_access: hostData.allow_file_access,
                allow_content_access: hostData.allow_content_access,
                mixed_content_mode: hostData.mixed_content_mode,
                safe_browsing_enabled: hostData.safe_browsing_enabled,
                settings_user_agent: hostData.settings_user_agent
            }
        };
    }

    function updateProbeUi(status, detail, cls) {
        setStatus(status);
        if (detail) {
            subtitleEl.textContent = detail;
            log(detail, cls);
        }
    }

    global.HybridGuardProbe = {
        updateResult: updateProbeUi
    };

    function handoffPayload(sessionId, webViewData, probeResult) {
        if (
            !global.AndroidBridge ||
            !global.AndroidBridge.submitExpandedPayload ||
            !sessionId
        ) {
            setStatus("Unable to hand payload to Android uploader");
            return;
        }
        var payload = {
            session_id: sessionId,
            timestamp: Math.floor(Date.now() / 1000),
            webview_data: webViewData,
            web_data: probeResult.web_data,
            collection_diagnostics: {
                diagnostics_schema_version: "web-probe-diagnostics-v1",
                web_probe_revision: global.HybridGuardWebProbe.REVISION,
                probe_statuses: probeResult.probe_statuses
            }
        };
        try {
            setStatus("Handing expanded payload to Android uploader...");
            global.AndroidBridge.submitExpandedPayload(JSON.stringify(payload));
            log("Expanded payload handed to uploader", "good");
        } catch (error) {
            log(
                "Android uploader handoff failed: " +
                    global.HybridGuardWebProbe.describeError(error),
                "bad"
            );
            setStatus("Android uploader handoff failed");
        }
    }

    function collectExpandedSignals() {
        var currentSessionId = "";
        var webViewData = buildWebViewData(defaultHostData(), -1);
        var fallbackProbeResult = {
            web_data: global.HybridGuardWebProbe.defaultWebData(),
            probe_statuses: {
                navigator: "runtime_error",
                screen: "runtime_error",
                webgl: "runtime_error",
                execution: "runtime_error",
                connection: "runtime_error",
                audio: "runtime_error",
                font: "runtime_error",
                permissions: "runtime_error",
                automation: "runtime_error",
                canvas: "runtime_error"
            }
        };

        setStatus("Establishing JSBridge connection...");
        return sleep(100).then(function () {
            if (
                !global.AndroidBridge ||
                !global.AndroidBridge.getSessionId ||
                !global.AndroidBridge.getWebViewHostFeatures ||
                !global.AndroidBridge.submitExpandedPayload
            ) {
                throw new Error("Android bridge missing");
            }
            var startedAt = performance.now();
            currentSessionId = global.AndroidBridge.getSessionId();
            var bridgeLatencyMs = parseFloat((performance.now() - startedAt).toFixed(3));
            var hostData = assignObject(
                defaultHostData(),
                JSON.parse(global.AndroidBridge.getWebViewHostFeatures())
            );
            webViewData = buildWebViewData(hostData, bridgeLatencyMs);
            log("JSBridge connected in " + bridgeLatencyMs + " ms", "good");
            log("Expanded WebView host signals collected");
            setStatus("Collecting expanded browser runtime signals...");
            return sleep(100);
        }).then(function () {
            return global.HybridGuardWebProbe.collect({
                canvasContainer: canvasBox,
                onLog: log
            });
        }).then(function (probeResult) {
            var navigatorInfo = probeResult.web_data.navigator_layer;
            var screenInfo = probeResult.web_data.screen_layer;
            var webglInfo = probeResult.web_data.graphics_layer;
            var audioInfo = probeResult.web_data.audio_layer;
            var fontInfo = probeResult.web_data.font_layer;
            var executionInfo = probeResult.web_data.execution_layer;
            log("UA: " + navigatorInfo.user_agent.substring(0, 68));
            log(
                "Logical screen: " +
                    screenInfo.screen_resolution_logical +
                    " DPR " +
                    screenInfo.device_pixel_ratio
            );
            log("WebGL renderer: " + webglInfo.webgl_renderer);
            log(
                "Audio supported: " +
                    audioInfo.audio_context_supported +
                    ", fonts: " +
                    fontInfo.font_probe_count
            );
            log("Compute challenge: " + executionInfo.compute_task_time_ms + " ms", "good");
            log("Canvas hash: " + webglInfo.canvas_hash.substring(0, 16));
            handoffPayload(currentSessionId, webViewData, probeResult);
        }, function (error) {
            log(
                "Expanded probe degraded: " +
                    global.HybridGuardWebProbe.describeError(error),
                "bad"
            );
            handoffPayload(currentSessionId, webViewData, fallbackProbeResult);
        });
    }

    global.addEventListener("load", collectExpandedSignals);
})(window);
