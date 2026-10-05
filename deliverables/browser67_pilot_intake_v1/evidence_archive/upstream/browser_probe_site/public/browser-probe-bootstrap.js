(function (global) {
  "use strict";

  var STORAGE_KEY = "hybridguard-browser-probe-v1";

  function isAllowedEndpoint(value) {
    try {
      if (!/^(https?):\/\//i.test(value) || /^[a-z]+:\/\/[^/?#]*@/i.test(value)) {
        return false;
      }
      var parsed = document.createElement("a");
      parsed.href = value;
      return (
        parsed.protocol === "https:" ||
        (parsed.protocol === "http:" &&
          (parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost"))
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
        try {
          var key = decodeURIComponent(encodedKey.replace(/\+/g, " "));
          var decodedValue = decodeURIComponent(encodedValue.replace(/\+/g, " "));
          if (!Object.prototype.hasOwnProperty.call(result, key)) {
            result[key] = decodedValue;
          }
        } catch (_error) {}
      });
    return result;
  }

  function validContext(context) {
    return Boolean(
      context &&
        context.pair_id &&
        context.browser_ticket &&
        isAllowedEndpoint(context.browser_upload_url) &&
        isAllowedEndpoint(context.browser_stage_url)
    );
  }

  function readContext() {
    var fragment = parseFragment(global.location.hash);
    var launchAttempt = parseInt(fragment.launch_attempt || "1", 10);
    var fromFragment = {
      pair_id: fragment.pair_id || "",
      browser_ticket: fragment.browser_ticket || "",
      browser_upload_url: fragment.browser_upload_url || "",
      browser_stage_url: fragment.browser_stage_url || "",
      launch_attempt: launchAttempt === 2 ? 2 : 1
    };
    if (validContext(fromFragment)) {
      try {
        global.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fromFragment));
      } catch (_error) {}
      return fromFragment;
    }
    try {
      var stored = JSON.parse(global.sessionStorage.getItem(STORAGE_KEY) || "{}");
      if (validContext(stored)) {
        return stored;
      }
    } catch (_error) {}
    return null;
  }

  function reportPageLoaded(context) {
    if (!context || typeof global.XMLHttpRequest !== "function") {
      return;
    }
    try {
      var xhr = new global.XMLHttpRequest();
      xhr.open("POST", context.browser_stage_url, true);
      xhr.timeout = 5000;
      xhr.setRequestHeader("Authorization", "Bearer " + context.browser_ticket);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.setRequestHeader("ngrok-skip-browser-warning", "1");
      xhr.send(
        JSON.stringify({
          pair_id: context.pair_id,
          stage: "page_loaded",
          launch_attempt: context.launch_attempt,
          client_stage_at_ms: Date.now()
        })
      );
    } catch (_error) {}
  }

  var launchContext = readContext();
  if (launchContext) {
    global.HybridGuardBrowserLaunchContext = launchContext;
    reportPageLoaded(launchContext);
  }
})(window);
