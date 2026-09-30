import { WEBVIEW_AUTOMATION_PROFILES } from "./webview_automation_profiles.mjs";

const STANDARD_WEB_MUTATIONS = Object.freeze([
  "web_data.automation_surface_layer.webdriver",
  "web_data.navigator_layer.platform",
  "web_data.navigator_layer.hardware_concurrency",
  "web_data.navigator_layer.device_memory",
  "web_data.navigator_layer.user_agent",
]);

const STEALTH_WEB_MUTATIONS = Object.freeze([
  "web_data.navigator_layer.hardware_concurrency",
  "web_data.graphics_layer.webgl_vendor",
  "web_data.graphics_layer.webgl_renderer",
  "web_data.navigator_layer.languages",
  "web_data.automation_surface_layer.plugins_count",
]);

const STANDARD_OBSERVABLE_FIELDS = Object.freeze([
  "webdriver", "platform", "hardware_concurrency", "device_memory", "user_agent",
]);

const STEALTH_OBSERVABLE_FIELDS = Object.freeze([
  "hardware_concurrency", "webgl_vendor", "webgl_renderer", "languages", "plugins_count",
]);

const CDP_SOURCE = "https://developer.chrome.com/docs/devtools/protocol/";
const CDP_BOUNDARY = Object.freeze({
  executionClientId: "cdp",
  name: "Chrome DevTools Protocol",
  sourceReference: CDP_SOURCE,
  attackFamily: "web_automation_or_spoofing",
  attackType: "browser_api_spoof_boundary",
  targetLayers: Object.freeze(["Web"]),
  boundaryCampaign: "teacher-rule-boundary-api36-v1",
});

const CDP_EMULATION_BOUNDARY = Object.freeze({
  ...CDP_BOUNDARY,
  boundaryCampaign: "teacher-cdp-emulation-rule-boundary-api36-v5",
  attackType: "browser_cdp_emulation_boundary",
  automationRunner: "week10_cdp_emulation_runner_v5.mjs",
});

const CDP_EMULATION_TARGET_URL = "file:///android_asset/expanded_probe.html";
const CDP_EMULATION_ALLOWED_METHODS = Object.freeze([
  "Emulation.setTimezoneOverride",
  "Emulation.setDeviceMetricsOverride",
  "Emulation.clearDeviceMetricsOverride",
]);
const STEALTH_BOUNDARY = Object.freeze({
  executionClientId: "stealth",
  name: "puppeteer-extra-plugin-stealth",
  attackFamily: "web_automation_or_spoofing",
  attackType: "browser_fingerprint_evasion_boundary",
  targetLayers: Object.freeze(["Web"]),
  boundaryCampaign: "teacher-stealth-rule-boundary-api36-v4",
});

export const SUPPORTED_STEALTH_EVASION_IDS = Object.freeze([
  "navigator.webdriver",
  "navigator.hardwareConcurrency",
  "navigator.languages",
  "navigator.plugins",
  "webgl.vendor",
  "user-agent-override",
]);

export const CONTROLLED_WEBVIEW_METHOD_IDS = Object.freeze([
  "cdp", "playwright", "puppeteer", "selenium", "stealth",
]);

export const CONTROLLED_WEBVIEW_CONFIGURATIONS = Object.freeze({
  cdp: Object.freeze({
    id: "cdp",
    executionClientId: "cdp",
    name: "Chrome DevTools Protocol",
    configId: "w6-tool-056-legacy-default-v1",
    sourceReference: CDP_SOURCE,
    attackFamily: "web_automation_or_spoofing",
    attackType: "browser_api_spoof",
    targetLayers: Object.freeze(["Web"]),
    expectedMutations: STANDARD_WEB_MUTATIONS,
    observableFields: STANDARD_OBSERVABLE_FIELDS,
  }),
  playwright: Object.freeze({
    id: "playwright",
    executionClientId: "playwright",
    name: "Playwright",
    configId: "w6-tool-054-legacy-default-v1",
    sourceReference: "https://playwright.dev/docs/api/class-android",
    attackFamily: "web_automation_or_spoofing",
    attackType: "browser_automation_controlled_profile",
    targetLayers: Object.freeze(["Web"]),
    expectedMutations: STANDARD_WEB_MUTATIONS,
    observableFields: STANDARD_OBSERVABLE_FIELDS,
  }),
  puppeteer: Object.freeze({
    id: "puppeteer",
    executionClientId: "puppeteer",
    name: "Puppeteer",
    configId: "w6-tool-055-legacy-default-v1",
    sourceReference: "https://pptr.dev/",
    attackFamily: "web_automation_or_spoofing",
    attackType: "browser_automation_controlled_profile",
    targetLayers: Object.freeze(["Web"]),
    expectedMutations: STANDARD_WEB_MUTATIONS,
    observableFields: STANDARD_OBSERVABLE_FIELDS,
  }),
  selenium: Object.freeze({
    id: "selenium",
    executionClientId: "selenium",
    name: "Selenium",
    configId: "w6-tool-053-legacy-default-v1",
    sourceReference: "https://www.selenium.dev/documentation/webdriver/",
    attackFamily: "web_automation_or_spoofing",
    attackType: "browser_automation_controlled_profile",
    targetLayers: Object.freeze(["Web"]),
    expectedMutations: STANDARD_WEB_MUTATIONS,
    observableFields: STANDARD_OBSERVABLE_FIELDS,
  }),
  stealth: Object.freeze({
    id: "stealth",
    executionClientId: "stealth",
    name: "puppeteer-extra-plugin-stealth",
    configId: "w6-tool-058-legacy-default-v1",
    sourceReference: "https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth",
    attackFamily: "web_automation_or_spoofing",
    attackType: "browser_fingerprint_evasion",
    targetLayers: Object.freeze(["Web"]),
    expectedMutations: STEALTH_WEB_MUTATIONS,
    observableFields: STEALTH_OBSERVABLE_FIELDS,
  }),
  cdp_webdriver_only_v1: Object.freeze({
    id: "cdp_webdriver_only_v1",
    ...CDP_BOUNDARY,
    configId: "w9-rule-boundary-cdp-webdriver-only-v1",
    expectedMutations: Object.freeze(["web_data.automation_surface_layer.webdriver"]),
    observableFields: Object.freeze(["webdriver"]),
  }),
  cdp_ua_only_v1: Object.freeze({
    id: "cdp_ua_only_v1",
    ...CDP_BOUNDARY,
    configId: "w9-rule-boundary-cdp-ua-only-v1",
    expectedMutations: Object.freeze(["web_data.navigator_layer.user_agent"]),
    observableFields: Object.freeze(["user_agent"]),
  }),
  cdp_platform_only_v1: Object.freeze({
    id: "cdp_platform_only_v1",
    ...CDP_BOUNDARY,
    configId: "w9-rule-boundary-cdp-platform-only-v1",
    expectedMutations: Object.freeze(["web_data.navigator_layer.platform"]),
    observableFields: Object.freeze(["platform"]),
  }),
  cdp_ua_platform_desktop_v1: Object.freeze({
    id: "cdp_ua_platform_desktop_v1",
    ...CDP_BOUNDARY,
    configId: "w9-rule-boundary-cdp-ua-platform-desktop-v1",
    expectedMutations: Object.freeze([
      "web_data.navigator_layer.platform",
      "web_data.navigator_layer.user_agent",
    ]),
    observableFields: Object.freeze(["platform", "user_agent"]),
  }),
  cdp_resource_pair_v1: Object.freeze({
    id: "cdp_resource_pair_v1",
    ...CDP_BOUNDARY,
    configId: "w9-rule-boundary-cdp-resource-pair-v1",
    expectedMutations: Object.freeze([
      "web_data.navigator_layer.hardware_concurrency",
      "web_data.navigator_layer.device_memory",
    ]),
    observableFields: Object.freeze(["hardware_concurrency", "device_memory"]),
  }),
  cdp_timezone_only_v1: Object.freeze({
    id: "cdp_timezone_only_v1",
    ...CDP_EMULATION_BOUNDARY,
    configId: "w10-cdp-emulation-timezone-only-v1",
    sourceReference: "https://chromedevtools.github.io/devtools-protocol/tot/Emulation/#method-setTimezoneOverride",
    expectedMutations: Object.freeze([
      "web_data.execution_layer.timezone_id",
      "web_data.execution_layer.timezone_offset",
    ]),
    observableFields: Object.freeze(["timezone_id", "timezone_offset"]),
    cdpEmulation: Object.freeze({
      contractVersion: "cdp-emulation-v1",
      applyCommands: Object.freeze([
        Object.freeze({ method: "Emulation.setTimezoneOverride", params: Object.freeze({ timezoneId: "America/Los_Angeles" }) }),
      ]),
      rollbackCommands: Object.freeze([
        Object.freeze({ method: "Emulation.setTimezoneOverride", params: Object.freeze({ timezoneId: "" }) }),
      ]),
      targetUrl: CDP_EMULATION_TARGET_URL,
    }),
  }),
  cdp_screen_metrics_only_v1: Object.freeze({
    id: "cdp_screen_metrics_only_v1",
    ...CDP_EMULATION_BOUNDARY,
    configId: "w10-cdp-emulation-screen-metrics-only-v1",
    sourceReference: "https://chromedevtools.github.io/devtools-protocol/tot/Emulation/#method-setDeviceMetricsOverride",
    expectedMutations: Object.freeze([
      "web_data.screen_layer.avail_width",
      "web_data.screen_layer.avail_height",
      "web_data.screen_layer.device_pixel_ratio",
      "web_data.screen_layer.inner_width",
      "web_data.screen_layer.inner_height",
      "web_data.screen_layer.outer_width",
      "web_data.screen_layer.outer_height",
      "web_data.screen_layer.screen_resolution_logical",
      "web_data.screen_layer.visual_viewport_width",
      "web_data.screen_layer.visual_viewport_height",
    ]),
    observableFields: Object.freeze([
      "avail_width", "avail_height", "device_pixel_ratio", "inner_width", "inner_height",
      "outer_width", "outer_height", "screen_resolution_logical", "visual_viewport_width", "visual_viewport_height",
    ]),
    cdpEmulation: Object.freeze({
      contractVersion: "cdp-emulation-v1",
      applyCommands: Object.freeze([
        Object.freeze({
          method: "Emulation.setDeviceMetricsOverride",
          params: Object.freeze({
            width: 393,
            height: 851,
            deviceScaleFactor: 2.75,
            mobile: true,
            screenWidth: 393,
            screenHeight: 851,
            positionX: 0,
            positionY: 0,
          }),
        }),
      ]),
      rollbackCommands: Object.freeze([
        Object.freeze({ method: "Emulation.clearDeviceMetricsOverride", params: Object.freeze({}) }),
      ]),
      targetUrl: CDP_EMULATION_TARGET_URL,
    }),
  }),  stealth_webgl_pair_v1: Object.freeze({
    id: "stealth_webgl_pair_v1",
    ...STEALTH_BOUNDARY,
    configId: "w9-stealth-boundary-webgl-pair-v1",
    sourceReference: "https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth/evasions/webgl.vendor",
    expectedMutations: Object.freeze([
      "web_data.graphics_layer.webgl_vendor",
      "web_data.graphics_layer.webgl_renderer",
    ]),
    observableFields: Object.freeze(["webgl_vendor", "webgl_renderer"]),
    stealthEvasions: Object.freeze([
      Object.freeze({
        id: "webgl.vendor",
        options: Object.freeze({
          vendor: "Google Inc. (NVIDIA)",
          renderer: "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660, Direct3D11)",
        }),
      }),
    ]),
  }),
  stealth_languages_only_v1: Object.freeze({
    id: "stealth_languages_only_v1",
    ...STEALTH_BOUNDARY,
    configId: "w9-stealth-boundary-languages-only-v1",
    sourceReference: "https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth/evasions/navigator.languages",
    expectedMutations: Object.freeze(["web_data.navigator_layer.languages"]),
    observableFields: Object.freeze(["languages"]),
    stealthEvasions: Object.freeze([
      Object.freeze({ id: "navigator.languages", options: Object.freeze({ languages: Object.freeze(["fr-FR", "fr"]) }) }),
    ]),
  }),
  stealth_plugins_mime_v1: Object.freeze({
    id: "stealth_plugins_mime_v1",
    ...STEALTH_BOUNDARY,
    configId: "w9-stealth-boundary-plugins-mime-v1",
    sourceReference: "https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth/evasions/navigator.plugins",
    expectedMutations: Object.freeze([
      "web_data.automation_surface_layer.plugins_count",
      "web_data.automation_surface_layer.mime_types_count",
      "web_data.automation_surface_layer.plugins_hash",
      "web_data.automation_surface_layer.mime_types_hash",
    ]),
    observableFields: Object.freeze([
      "plugins_count", "mime_types_count", "plugins_hash", "mime_types_hash",
    ]),
    stealthEvasions: Object.freeze([
      Object.freeze({ id: "navigator.plugins", options: Object.freeze({}) }),
    ]),
  }),
});

export const CONTROLLED_WEBVIEW_CONFIGURATION_IDS = Object.freeze(Object.keys(CONTROLLED_WEBVIEW_CONFIGURATIONS));

export function controlledWebviewConfiguration(configurationId) {
  const configuration = CONTROLLED_WEBVIEW_CONFIGURATIONS[configurationId];
  if (!configuration) throw new Error(`Unsupported controlled WebView configuration: ${String(configurationId)}`);
  if (!WEBVIEW_AUTOMATION_PROFILES[configurationId]) {
    throw new Error(`Controlled WebView configuration ${configurationId} has no pinned observable profile`);
  }
  const stealthEvasions = cloneStealthEvasions(configuration, configurationId);
  const cdpEmulation = cloneCdpEmulation(configuration, configurationId);
  return {
    ...configuration,
    targetLayers: [...configuration.targetLayers],
    expectedMutations: [...configuration.expectedMutations],
    observableFields: [...configuration.observableFields],
    ...(stealthEvasions ? { stealthEvasions } : {}),
    ...(cdpEmulation ? { cdpEmulation } : {}),
  };
}

function cloneCdpEmulation(configuration, configurationId) {
  const contract = configuration.cdpEmulation;
  if (contract === undefined) return null;
  if (configuration.executionClientId !== "cdp" || configuration.boundaryCampaign !== "teacher-cdp-emulation-rule-boundary-api36-v5") {
    throw new Error(`Only V5 CDP configurations may declare cdpEmulation: ${configurationId}`);
  }
  if (!contract || contract.contractVersion !== "cdp-emulation-v1" || contract.targetUrl !== CDP_EMULATION_TARGET_URL) {
    throw new Error(`Invalid CDP emulation contract in ${configurationId}`);
  }
  for (const key of ["applyCommands", "rollbackCommands"]) {
    if (!Array.isArray(contract[key]) || contract[key].length !== 1) {
      throw new Error(`CDP emulation ${key} must contain exactly one command in ${configurationId}`);
    }
    for (const command of contract[key]) {
      if (!command || !CDP_EMULATION_ALLOWED_METHODS.includes(command.method) || !command.params || typeof command.params !== "object" || Array.isArray(command.params)) {
        throw new Error(`CDP emulation command is not allowlisted in ${configurationId}`);
      }
    }
  }
  const apply = contract.applyCommands[0];
  const rollback = contract.rollbackCommands[0];
  if (configurationId === "cdp_timezone_only_v1" && (
    !sameJson(apply, { method: "Emulation.setTimezoneOverride", params: { timezoneId: "America/Los_Angeles" } }) ||
    !sameJson(rollback, { method: "Emulation.setTimezoneOverride", params: { timezoneId: "" } })
  )) {
    throw new Error("Timezone V5 configuration must use the frozen apply and rollback commands");
  }
  if (configurationId === "cdp_screen_metrics_only_v1" && (
    !sameJson(apply, {
      method: "Emulation.setDeviceMetricsOverride",
      params: {
        width: 393,
        height: 851,
        deviceScaleFactor: 2.75,
        mobile: true,
        screenWidth: 393,
        screenHeight: 851,
        positionX: 0,
        positionY: 0,
      },
    }) ||
    !sameJson(rollback, { method: "Emulation.clearDeviceMetricsOverride", params: {} })
  )) {
    throw new Error("Screen V5 configuration must use the frozen apply and rollback commands");
  }  return JSON.parse(JSON.stringify(contract));
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function cloneStealthEvasions(configuration, configurationId) {
  const evasions = configuration.stealthEvasions;
  if (evasions === undefined) return null;
  if (configuration.executionClientId !== "stealth") {
    throw new Error(`Only stealth configurations may declare stealth evasions: ${configurationId}`);
  }
  if (!Array.isArray(evasions) || evasions.length === 0) {
    throw new Error(`Stealth configuration ${configurationId} must declare at least one evasion`);
  }
  if (configuration.boundaryCampaign === "teacher-stealth-rule-boundary-api36-v4" && evasions.length !== 1) {
    throw new Error(`V4 Stealth configuration ${configurationId} must select exactly one evasion`);
  }
  const seen = new Set();
  return evasions.map((evasion) => {
    if (!evasion || typeof evasion.id !== "string" || !SUPPORTED_STEALTH_EVASION_IDS.includes(evasion.id)) {
      throw new Error(`Unsupported Stealth evasion in ${configurationId}: ${String(evasion?.id)}`);
    }
    if (seen.has(evasion.id)) throw new Error(`Duplicate Stealth evasion in ${configurationId}: ${evasion.id}`);
    seen.add(evasion.id);
    if (!evasion.options || typeof evasion.options !== "object" || Array.isArray(evasion.options)) {
      throw new Error(`Stealth evasion options must be an object in ${configurationId}: ${evasion.id}`);
    }
    return { id: evasion.id, options: JSON.parse(JSON.stringify(evasion.options)) };
  });
}

export function controlledWebviewMethod(methodId) {
  if (!CONTROLLED_WEBVIEW_METHOD_IDS.includes(methodId)) {
    throw new Error(`Unsupported controlled WebView method: ${String(methodId)}`);
  }
  return controlledWebviewConfiguration(methodId);
}