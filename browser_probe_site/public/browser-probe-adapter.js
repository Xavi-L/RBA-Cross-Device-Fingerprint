(function (global) {
  "use strict";

  var STORAGE_KEY = "hybridguard-browser-probe-v1";
  var UPLOAD_TIMEOUT_MS = 12000;
  var statusEl = document.getElementById("status");
  var logEl = document.getElementById("log");
  var canvasBox = document.getElementById("canvasBox");

  function setStatus(text, bad) {
    statusEl.textContent = text;
    statusEl.className = bad ? "bad" : "";
  }

  function log(text, cls) {
    var paragraph = document.createElement("p");
    paragraph.className = cls || "";
    paragraph.textContent = text;
    logEl.appendChild(paragraph);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function uuidV4() {
    if (global.crypto && typeof global.crypto.randomUUID === "function") {
      return global.crypto.randomUUID();
    }
    var bytes = new Uint8Array(16);
    if (global.crypto && typeof global.crypto.getRandomValues === "function") {
      global.crypto.getRandomValues(bytes);
    } else {
      for (var index = 0; index < bytes.length; index += 1) {
        bytes[index] = Math.floor(Math.random() * 256);
      }
    }
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    var hex = Array.prototype.map.call(bytes, function (value) {
      return (value + 256).toString(16).slice(1);
    }).join("");
    return [
      hex.slice(0, 8),
      hex.slice(8, 12),
      hex.slice(12, 16),
      hex.slice(16, 20),
      hex.slice(20),
    ].join("-");
  }

  function isAllowedUploadUrl(value) {
    try {
      if (
        !/^(https?):\/\//i.test(value) ||
        /^[a-z]+:\/\/[^/?#]*@/i.test(value)
      ) {
        return false;
      }
      var parsed = document.createElement("a");
      parsed.href = value;
      return (
        parsed.protocol === "https:" ||
        (
          parsed.protocol === "http:" &&
          (parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost")
        )
      );
    } catch (_error) {
      return false;
    }
  }

  function parseFragment(value) {
    var result = {};
    String(value || "")
      .replace(/^#/, "")
      .split("&")
      .forEach(function (entry) {
        if (!entry) {
          return;
        }
        var separator = entry.indexOf("=");
        var encodedKey = separator >= 0 ? entry.slice(0, separator) : entry;
        var encodedValue = separator >= 0 ? entry.slice(separator + 1) : "";
        var key;
        var decodedValue;
        try {
          key = decodeURIComponent(encodedKey.replace(/\+/g, " "));
          decodedValue = decodeURIComponent(encodedValue.replace(/\+/g, " "));
        } catch (_error) {
          return;
        }
        if (!Object.prototype.hasOwnProperty.call(result, key)) {
          result[key] = decodedValue;
        }
      });
    return result;
  }

  function readLaunchContext() {
    if (
      global.HybridGuardBrowserLaunchContext &&
      global.HybridGuardBrowserLaunchContext.pair_id &&
      global.HybridGuardBrowserLaunchContext.browser_ticket &&
      isAllowedUploadUrl(global.HybridGuardBrowserLaunchContext.browser_upload_url) &&
      isAllowedUploadUrl(global.HybridGuardBrowserLaunchContext.browser_stage_url)
    ) {
      global.history.replaceState(null, "", global.location.pathname + global.location.search);
      return global.HybridGuardBrowserLaunchContext;
    }
    // URLSearchParams is absent from the Chromium generation used by some
    // Android 5.x system browsers. Keep ticket parsing ES5-only.
    var fragment = parseFragment(global.location.hash);
    var launchAttempt = parseInt(fragment.launch_attempt || "1", 10);
    var fromFragment = {
      pair_id: fragment.pair_id || "",
      browser_ticket: fragment.browser_ticket || "",
      browser_upload_url: fragment.browser_upload_url || "",
      browser_stage_url: fragment.browser_stage_url || "",
      launch_attempt: launchAttempt === 2 ? 2 : 1
    };
    if (
      fromFragment.pair_id &&
      fromFragment.browser_ticket &&
      isAllowedUploadUrl(fromFragment.browser_upload_url) &&
      isAllowedUploadUrl(fromFragment.browser_stage_url)
    ) {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fromFragment));
      } catch (_error) {}
      global.history.replaceState(null, "", global.location.pathname + global.location.search);
      return fromFragment;
    }
    try {
      var stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
      if (
        stored.pair_id &&
        stored.browser_ticket &&
        isAllowedUploadUrl(stored.browser_upload_url) &&
        isAllowedUploadUrl(stored.browser_stage_url)
      ) {
        return stored;
      }
    } catch (_error) {}
    throw new Error("missing_or_invalid_launch_context");
  }

  function xhrJsonRequest(url, method, headers, body, timeoutMs) {
    return new Promise(function (resolve, reject) {
      if (typeof global.XMLHttpRequest !== "function") {
        reject(new Error("no_supported_http_transport"));
        return;
      }
      var xhr = new global.XMLHttpRequest();
      var settled = false;

      function rejectOnce(error) {
        if (!settled) {
          settled = true;
          reject(error);
        }
      }

      try {
        xhr.open(method, url, true);
        xhr.timeout = timeoutMs;
        Object.keys(headers || {}).forEach(function (name) {
          xhr.setRequestHeader(name, headers[name]);
        });
      } catch (error) {
        rejectOnce(error);
        return;
      }

      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4 || settled) {
          return;
        }
        var responseText = xhr.responseText || "";
        var responseBody = {};
        try {
          responseBody = responseText ? JSON.parse(responseText) : {};
        } catch (_error) {}
        if (xhr.status < 200 || xhr.status >= 300) {
          var detail =
            responseBody.detail || responseBody.status || ("http_" + xhr.status);
          rejectOnce(new Error(detail));
          return;
        }
        settled = true;
        resolve(responseBody);
      };
      xhr.onerror = function () {
        rejectOnce(new Error("xhr_network_error"));
      };
      xhr.ontimeout = function () {
        rejectOnce(new Error("xhr_timeout"));
      };
      xhr.onabort = function () {
        rejectOnce(new Error("xhr_aborted"));
      };
      try {
        xhr.send(body || null);
      } catch (error) {
        rejectOnce(error);
      }
    });
  }

  function reportStage(launchContext, stage) {
    if (!launchContext || !launchContext.browser_stage_url) {
      return;
    }
    xhrJsonRequest(
      launchContext.browser_stage_url,
      "POST",
      {
        "Authorization": "Bearer " + launchContext.browser_ticket,
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "1"
      },
      JSON.stringify({
        pair_id: launchContext.pair_id,
        stage: stage,
        launch_attempt: launchContext.launch_attempt || 1,
        client_stage_at_ms: Date.now()
      }),
      5000
    ).then(
      function () {},
      function () {}
    );
  }

  function loadBundleMetadata() {
    if (typeof global.fetch === "function") {
      return global.fetch("probe/manifest.json", {
        cache: "no-store",
        credentials: "omit",
        referrerPolicy: "no-referrer"
      }).then(
        function (response) {
          return response.ok ? response.json() : {};
        },
        function () {
          return {};
        }
      );
    }
    return xhrJsonRequest("probe/manifest.json", "GET", {}, null, 5000).then(
      function (metadata) {
        return metadata;
      },
      function () {
        return {};
      }
    );
  }

  function createPayload(launchContext, probeResult, bundleMetadata) {
    return {
      pair_id: launchContext.pair_id,
      browser_session_id: uuidV4(),
      timestamp: Math.floor(Date.now() / 1000),
      collector_app: "browserprobe",
      schema_version: "browser-web-v1-status",
      web_probe_revision: global.HybridGuardWebProbe.REVISION,
      web_data: probeResult.web_data,
      collection_diagnostics: {
        diagnostics_schema_version: "browser-web-probe-diagnostics-v1",
        probe_statuses: probeResult.probe_statuses,
        collection_finished_at_ms: Date.now(),
      },
      collection_status: probeResult.collection_status,
      field_statuses: probeResult.collection_status.fields,
      probe_metadata: {
        metadata_schema_version: "browser-probe-metadata-v1",
        page_origin: global.location.origin,
        page_path: global.location.pathname,
        core_revision: global.HybridGuardWebProbe.REVISION,
        core_bundle_sha256: bundleMetadata.sha256 || "",
        expected_signal_count: global.HybridGuardWebProbe.FIELD_PATHS.length,
      },
    };
  }

  function upload(launchContext, serializedPayload, attempt) {
    setStatus("Uploading verified browser feature payload…", false);
    var controller = null;
    var timeoutId = null;
    var requestHeaders = {
      "Authorization": "Bearer " + launchContext.browser_ticket,
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "1",
    };
    var requestPromise;
    if (typeof global.fetch === "function") {
      var requestOptions = {
        method: "POST",
        mode: "cors",
        cache: "no-store",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        headers: requestHeaders,
        body: serializedPayload
      };
      if (typeof global.AbortController === "function") {
        controller = new global.AbortController();
        requestOptions.signal = controller.signal;
        timeoutId = global.setTimeout(function () {
          controller.abort();
        }, UPLOAD_TIMEOUT_MS);
      }
      requestPromise = global.fetch(
        launchContext.browser_upload_url,
        requestOptions
      ).then(function (response) {
        return response.text().then(function (text) {
          var body = {};
          try {
            body = text ? JSON.parse(text) : {};
          } catch (_error) {}
          if (!response.ok) {
            var detail = body.detail || body.status || ("http_" + response.status);
            throw new Error(detail);
          }
          return body;
        });
      });
    } else {
      requestPromise = xhrJsonRequest(
        launchContext.browser_upload_url,
        "POST",
        requestHeaders,
        serializedPayload,
        UPLOAD_TIMEOUT_MS
      );
    }

    return requestPromise.then(
      function (body) {
        if (timeoutId !== null) {
          global.clearTimeout(timeoutId);
        }
        return body;
      },
      function (error) {
        if (timeoutId !== null) {
          global.clearTimeout(timeoutId);
        }
        throw error;
      }
    ).catch(function (error) {
      if (attempt >= 3) {
        throw error;
      }
      var delayMs = attempt * 700;
      log("Upload retry " + attempt + " scheduled after network error", "bad");
      return new Promise(function (resolve) {
        setTimeout(resolve, delayMs);
      }).then(function () {
        return upload(launchContext, serializedPayload, attempt + 1);
      });
    });
  }

  function run() {
    var launchContext;
    if (!global.HybridGuardWebProbe) {
      setStatus("Canonical Web probe failed to load.", true);
      return;
    }
    try {
      launchContext = readLaunchContext();
    } catch (_error) {
      setStatus("No valid one-time collection ticket. Please launch this page from the app.", true);
      return;
    }
    reportStage(launchContext, "adapter_started");

    function finishUpload(receipt) {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem(STORAGE_KEY + ":payload");
      } catch (_error) {}
      var receiptId = receipt.receipt_id ? " Receipt " + receipt.receipt_id + "." : "";
      if (
        receipt.pair_status === "awaiting_app" ||
        receipt.pair_status === "awaiting_app_receipt"
      ) {
        setStatus(
          "Browser payload saved, waiting for app binding." + receiptId,
          false
        );
        log("Backend saved the browser payload; app binding is still pending.", "good");
        return;
      }
      setStatus("Browser collection complete." + receiptId + " You may close this tab.", false);
      log("Backend receipt verified", "good");
    }

    function failUpload(error) {
      reportStage(launchContext, "upload_failed");
      setStatus(
        "Browser collection could not be uploaded: " +
          global.HybridGuardWebProbe.describeError(error),
        true
      );
      log("The Android app can keep its own completed collection.", "bad");
    }

    try {
      var cachedPayload = sessionStorage.getItem(STORAGE_KEY + ":payload");
      if (cachedPayload) {
        var cachedObject = JSON.parse(cachedPayload);
        if (cachedObject.pair_id === launchContext.pair_id) {
          log("Retrying the exact cached browser payload");
          upload(launchContext, cachedPayload, 1).then(finishUpload).catch(failUpload);
          return;
        }
        sessionStorage.removeItem(STORAGE_KEY + ":payload");
      }
    } catch (_error) {}

    setStatus("Collecting 67 browser environment features…", false);
    reportStage(launchContext, "collection_started");
    Promise.all([
      global.HybridGuardWebProbe.collect({
        canvasContainer: canvasBox,
        onLog: log
      }),
      loadBundleMetadata()
    ]).then(function (values) {
      reportStage(launchContext, "collection_finished");
      var payload = createPayload(launchContext, values[0], values[1]);
      var serializedPayload = JSON.stringify(payload);
      try {
        sessionStorage.setItem(STORAGE_KEY + ":payload", serializedPayload);
      } catch (_error) {}
      log(
        values[0].collection_status.counts.observed +
          "/" +
          values[0].collection_status.fixed_signal_count +
          " fields observed"
      );
      reportStage(launchContext, "upload_started");
      return upload(launchContext, serializedPayload, 1);
    }).then(finishUpload).catch(failUpload);
  }

  global.addEventListener("DOMContentLoaded", run);
})(window);
