export const WEBVIEW_AUTOMATION_PROFILES = Object.freeze({
  cdp: Object.freeze({
    webdriver: true,
    platform: "Win32",
    hardwareConcurrency: 48,
    deviceMemory: 16,
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  }),
  stealth: Object.freeze({
    hardwareConcurrency: 12,
    webglVendor: "Google Inc. (NVIDIA)",
    webglRenderer: "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)",
  }),
  playwright: Object.freeze({
    webdriver: true,
    platform: "Linux x86_64",
    hardwareConcurrency: 16,
    deviceMemory: 8,
    userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  }),
  puppeteer: Object.freeze({
    webdriver: true,
    platform: "MacIntel",
    hardwareConcurrency: 10,
    deviceMemory: 8,
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  }),
  selenium: Object.freeze({
    webdriver: true,
    platform: "Win32",
    hardwareConcurrency: 24,
    deviceMemory: 8,
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  }),
  cdp_webdriver_only_v1: Object.freeze({ webdriver: true }),
  cdp_ua_only_v1: Object.freeze({
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  }),
  cdp_platform_only_v1: Object.freeze({ platform: "Win32" }),
  cdp_ua_platform_desktop_v1: Object.freeze({
    platform: "Win32",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  }),
  cdp_resource_pair_v1: Object.freeze({ hardwareConcurrency: 48, deviceMemory: 16 }),
  cdp_timezone_only_v1: Object.freeze({
    timezoneId: "America/Los_Angeles",
    timezoneOffset: 420,
  }),
  cdp_screen_metrics_only_v1: Object.freeze({
    availWidth: 393,
    availHeight: 851,
    devicePixelRatio: 2.75,
    innerWidth: 393,
    innerHeight: 851,
    outerWidth: 393,
    outerHeight: 851,
    screenResolutionLogical: "393x851",
    visualViewportWidth: 393.1428527832031,
    visualViewportHeight: 851.047607421875,
  }),
  stealth_webgl_pair_v1: Object.freeze({
    webglVendor: "Google Inc. (NVIDIA)",
    webglRenderer: "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)",
  }),
  stealth_languages_only_v1: Object.freeze({ languages: Object.freeze(["fr-FR", "fr"]) }),
  stealth_plugins_mime_v1: Object.freeze({
    pluginsCount: 3,
    mimeTypesCount: 4,
    pluginsHash: "95021813daab933c013871840f5980b90fc8907d274e73f3782c8ec023da8fe8",
    mimeTypesHash: "319c9298870d25c3b513bbc46733c786d1ebb3fa21b784ee4a8d88540a9a93e5",
  }),
});

const PROFILE_FIELD_BINDINGS = Object.freeze({
  webdriver: "webdriver",
  platform: "platform",
  hardwareConcurrency: "hardware_concurrency",
  deviceMemory: "device_memory",
  userAgent: "user_agent",
  webglVendor: "webgl_vendor",
  webglRenderer: "webgl_renderer",
  languages: "languages",
  pluginsCount: "plugins_count",
  mimeTypesCount: "mime_types_count",
  pluginsHash: "plugins_hash",
  mimeTypesHash: "mime_types_hash",
  timezoneId: "timezone_id",
  timezoneOffset: "timezone_offset",
  availWidth: "avail_width",
  availHeight: "avail_height",
  devicePixelRatio: "device_pixel_ratio",
  innerWidth: "inner_width",
  innerHeight: "inner_height",
  outerWidth: "outer_width",
  outerHeight: "outer_height",
  screenResolutionLogical: "screen_resolution_logical",
  visualViewportWidth: "visual_viewport_width",
  visualViewportHeight: "visual_viewport_height",
});

// Only the two pre-registered screen observations accept a numeric tolerance.
// The bounds are frozen in the V5 campaign before collection, rather than
// inferred from the active payload after an experiment completes.
const OBSERVABLE_TOLERANCES = Object.freeze({
  cdp_screen_metrics_only_v1: Object.freeze({
    device_pixel_ratio: 0.01,
    visual_viewport_width: 1,
    visual_viewport_height: 1,
  }),
});

export function webviewAutomationProfile(configurationId, toolName) {
  const fixed = WEBVIEW_AUTOMATION_PROFILES[configurationId];
  if (fixed) return cloneValue(fixed);
  throw new Error("No pinned WebView automation profile for " + String(configurationId || toolName || "unknown"));
}

export function webviewAutomationObservables(web = {}) {
  const navigator = web?.navigator_layer && typeof web.navigator_layer === "object" ? web.navigator_layer : web;
  const graphics = web?.graphics_layer && typeof web.graphics_layer === "object" ? web.graphics_layer : web;
  const automation = web?.automation_surface_layer && typeof web.automation_surface_layer === "object" ? web.automation_surface_layer : web;
  const execution = web?.execution_layer && typeof web.execution_layer === "object" ? web.execution_layer : web;
  const screen = web?.screen_layer && typeof web.screen_layer === "object" ? web.screen_layer : web;
  return {
    webdriver: automation?.webdriver,
    platform: navigator?.platform,
    hardware_concurrency: navigator?.hardware_concurrency,
    device_memory: navigator?.device_memory,
    user_agent: navigator?.user_agent,
    webgl_vendor: graphics?.webgl_vendor,
    webgl_renderer: graphics?.webgl_renderer,
    languages: navigator?.languages,
    plugins_count: automation?.plugins_count,
    mime_types_count: automation?.mime_types_count,
    plugins_hash: automation?.plugins_hash,
    mime_types_hash: automation?.mime_types_hash,
    timezone_id: execution?.timezone_id,
    timezone_offset: execution?.timezone_offset,
    avail_width: screen?.avail_width,
    avail_height: screen?.avail_height,
    device_pixel_ratio: screen?.device_pixel_ratio,
    inner_width: screen?.inner_width,
    inner_height: screen?.inner_height,
    outer_width: screen?.outer_width,
    outer_height: screen?.outer_height,
    screen_resolution_logical: screen?.screen_resolution_logical,
    visual_viewport_width: screen?.visual_viewport_width,
    visual_viewport_height: screen?.visual_viewport_height,
  };
}

export function expectedWebviewObservableValue(configurationId, field, profile = webviewAutomationProfile(configurationId)) {
  const profileField = Object.entries(PROFILE_FIELD_BINDINGS).find(([, observableField]) => observableField === field)?.[0];
  return profileField ? profile?.[profileField] : undefined;
}

export function webviewObservableTolerance(configurationId, field) {
  return Number(OBSERVABLE_TOLERANCES[configurationId]?.[field] || 0);
}

export function matchesWebviewAutomationObservable(configurationId, field, actual, profile = webviewAutomationProfile(configurationId)) {
  const expected = expectedWebviewObservableValue(configurationId, field, profile);
  if (expected === undefined) return false;
  const tolerance = webviewObservableTolerance(configurationId, field);
  if (tolerance > 0 && typeof actual === "number" && typeof expected === "number") {
    return Number.isFinite(actual) && Math.abs(actual - expected) <= tolerance;
  }
  return sameValue(actual, expected);
}

export function matchesWebviewAutomationProfile(configurationId, toolName, web = {}) {
  const profile = webviewAutomationProfile(configurationId, toolName);
  const observed = webviewAutomationObservables(web);
  if (configurationId === "stealth") {
    return observed.hardware_concurrency === profile.hardwareConcurrency &&
      observed.webgl_vendor === profile.webglVendor &&
      observed.webgl_renderer === profile.webglRenderer &&
      Array.isArray(observed.languages) && observed.languages.includes("en-US") && observed.languages.includes("en") &&
      Number(observed.plugins_count || 0) > 0;
  }
  const declared = Object.entries(PROFILE_FIELD_BINDINGS)
    .filter(([profileField]) => Object.hasOwn(profile, profileField));
  return declared.length > 0 && declared.every(([, observableField]) => (
    matchesWebviewAutomationObservable(configurationId, observableField, observed[observableField], profile)
  ));
}

function sameValue(left, right) {
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, index) => value === right[index]);
  }
  return left === right;
}

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}