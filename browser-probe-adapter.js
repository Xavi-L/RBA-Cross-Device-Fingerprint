(function (global) {
  "use strict";

  var STORAGE_KEY = "hybridguard-browser-probe-v1";
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
      var parsed = new URL(value);
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

  function readLaunchContext() {
    var fragment = new URLSearchParams(global.location.hash.replace(/^#/, ""));
    var fromFragment = {
      pair_id: fragment.get("pair_id") || "",
      browser_ticket: fragment.get("browser_ticket") || "",
      browser_upload_url: fragment.get("browser_upload_url") || "",
    };
    if (
      fromFragment.pair_id &&
      fromFragment.browser_ticket &&
      isAllowedUploadUrl(fromFragment.browser_upload_url)
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
        isAllowedUploadUrl(stored.browser_upload_url)
      ) {
        return stored;
      }
    } catch (_error) {}
    throw new Error("missing_or_invalid_launch_context");
  }

  function loadBundleMetadata() {
    return fetch("probe/manifest.json", {
      cache: "no-store",
      credentials: "omit",
      referrerPolicy: "no-referrer",
    }).then(
      function (response) {
        return response.ok ? response.json() : {};
      },
      function () {
        return {};
      },
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
    return fetch(launchContext.browser_upload_url, {
      method: "POST",
      mode: "cors",
      cache: "no-store",
      credentials: "omit",
      referrerPolicy: "no-referrer",
      headers: {
        "Authorization": "Bearer " + launchContext.browser_ticket,
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "1",
      },
      body: serializedPayload,
    }).then(function (response) {
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
    }).catch(function (error) {
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

    function finishUpload(receipt) {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem(STORAGE_KEY + ":payload");
      } catch (_error) {}
      var receiptId = receipt.receipt_id ? " Receipt " + receipt.receipt_id + "." : "";
      setStatus("Browser collection complete." + receiptId + " You may close this tab.", false);
      log("Backend receipt verified", "good");
    }

    function failUpload(error) {
      setStatus(
        "Browser collection could not be uploaded: " +
          global.HybridGuardWebProbe.describeError(error),
        true,
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
    Promise.all([
      global.HybridGuardWebProbe.collect({
        canvasContainer: canvasBox,
        onLog: log,
      }),
      loadBundleMetadata(),
    ]).then(function (values) {
      var payload = createPayload(launchContext, values[0], values[1]);
      var serializedPayload = JSON.stringify(payload);
      try {
        sessionStorage.setItem(STORAGE_KEY + ":payload", serializedPayload);
      } catch (_error) {}
      log(
        values[0].collection_status.counts.observed +
          "/" +
          values[0].collection_status.fixed_signal_count +
          " fields observed",
      );
      return upload(launchContext, serializedPayload, 1);
    }).then(finishUpload).catch(failUpload);
  }

  global.addEventListener("DOMContentLoaded", run);
})(window);
