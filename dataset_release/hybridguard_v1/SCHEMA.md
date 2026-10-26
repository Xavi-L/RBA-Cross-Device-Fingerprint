# Schema and field dictionary

`schema.json` is a JSON Schema draft 2020-12 row union. The standard-library validator implements every keyword used in this file and rejects unsupported keywords. Structural and referential constraints between files are checked separately. The additional `reviewer_manifest_licensing` definition binds the Manifest to CC-BY-4.0 data resources and separately records the bundled scripts as NOT_SPECIFIED; it does not change any data-row contract. The authorized reviewer package contains 1,509 observations; no hosted publication is performed by this build.

## Files and top-level fields

| File | Fields and meaning |
|---|---|
| features.jsonl | `record_type=features`; random `sample_id`; `view=App177` or `Paired244`; `fields` keyed by canonical signal path; `supplemental` optional recorded geometry measurements |
| metadata.jsonl | `record_type=metadata`; `sample_id`; `source_id`; random nullable `group_id`; `group_basis`; `view`; source `cohort`, `environment`, schema versions and historical split/context where recorded; `android_api_level`; `qc`; `public_release_status=AUTHORIZED_FOR_PUBLIC_RELEASE` |
| annotations.jsonl | `record_type=annotations`; `sample_id`; `label`, `label_verification`, `label_scope`; independent `tool_execution_status`, `target_effect_status`, `detector_outcome`; recorded recipe/tool/scenario, restoration status, memory target and saved detector states where available; canonical `phase` for experiment groups |
| pairs.jsonl | `record_type=pairs`; random `pair_id`; `kind=experiment_triplet` (three distinct observations) or `linked_app_browser` (one observation containing two endpoints); `members` with sample IDs and phase |

Metadata additionally retains `representative_basis`, `physical_device_identity` and `historical_holdout_pristine` where recorded. They are provenance, not model inputs. Source-specific random group IDs preserve grouping within each study; cross-study physical identity is not established. `configuration_name` is the readable recorded recipe, `manipulation_type` the canonical recipe/task identifier, and `attack_tool` the separately recorded execution tool. `normal_scenario` explains legitimate controls; `target_memory_gib` describes the intended operation, not an observed feature.

`label` is one of modified, normal_control, no_effect, unlabeled, unknown. `label_verification` is verified_recorded_evidence, unverified or unknown. The scope is recorded target intervention before privacy redaction. `detector_outcome` and `recorded_detector_states` retain saved decisions, or explicit unknown/not_recomputed. They are never substituted for intervention ground truth.

## Feature cell

Each nominal slot has `value` (original typed value or null), `original_field_present` (boolean), `collection_status`, `status_origin` and `redaction`. Availability states: observed, unsupported_by_os, permission_denied, runtime_error, timeout, not_applicable, missing, unknown, present_status_unknown. `collector_emitted` and `not_recorded` distinguish original status from unrecorded status. A present value without a recorded state is not upgraded to observed. Original absence remains explicit even if a schema slot is materialized for representation.

Redaction values: none, remove_precise_time, remove_free_text_or_high_entropy_value, remove_unrecognized_semantic_value. A privacy-suppressed value is null but retains its original availability state. `false`, zero and minus one are not automatically missing. Historical sentinels and collector status may be insufficient to infer scientific usability.

App177 contains exactly 84 `android_native_data`, 26 `webview_data` and 67 `web_data` slots. Paired244 additionally has 67 `browser_web_data` slots only when a real Browser observation exists. Missing App fields in three genuine linked MTC records do not invalidate the endpoint association; they make the observation structurally incomplete. No Browser is synthesized from empty slots.

`qc` records original/expected slot counts, structural completeness, all-collector-observed and all-values-retained flags, upstream App QC errors/warnings, missing original paths and redacted-field count. Counts refer to the original field structure and the retained projection separately. The integer-only legacy viewport-scale field is explicitly corrected to numeric in both Web views; no other integer field is broadly widened or value converted.

## Relationships and geometry supplement

Experiment phases are normalized from recorded aliases to clean_pre, active, clean_post. Linked endpoints use linked_endpoints and one shared observation ID. Every reference must resolve; no observation belongs to two experiment triplets. Historical grouping/cohort metadata is not an independent-device or leakage-free split claim.

The geometry supplement is separate from the 177/244 counts. Host width/height, content width/height and four padding edges are physical pixels; Host density and Web DPR/viewport scale are dimensionless. Web screen/inner/visual-viewport dimensions are CSS pixels. `geometry_evidence.android_bracket_ms` is a relative acquisition duration, not an epoch timestamp; `geometry_evidence.usable_window` is the recorded boolean binding-window status. Host-before/after suffixes denote the actual synchronized bracket, not interpolation. Exact clocks, document IDs, URLs and diagnostic free text are absent.

Allowed supplemental keys:


- `host_before.width_px`
- `host_before.height_px`
- `host_before.content_width_px`
- `host_before.content_height_px`
- `host_before.density`
- `host_before.padding_left_px`
- `host_before.padding_top_px`
- `host_before.padding_right_px`
- `host_before.padding_bottom_px`
- `host_after.width_px`
- `host_after.height_px`
- `host_after.content_width_px`
- `host_after.content_height_px`
- `host_after.density`
- `host_after.padding_left_px`
- `host_after.padding_top_px`
- `host_after.padding_right_px`
- `host_after.padding_bottom_px`
- `web_geometry_values.screen_width`
- `web_geometry_values.screen_height`
- `web_geometry_values.inner_width`
- `web_geometry_values.inner_height`
- `web_geometry_values.device_pixel_ratio`
- `web_geometry_values.visual_viewport_width`
- `web_geometry_values.visual_viewport_height`
- `web_geometry_values.visual_viewport_scale`
- `geometry_evidence.usable_window`
- `geometry_evidence.android_bracket_ms`

## Complete signal dictionary

| Signal | Original types | Export types | Unit | Privacy policy |
|---|---|---|---|---|
| android_native_data.active_network_present | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.active_transport_types | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.avail_memory_gb | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.battery_health_code | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.battery_level_pct | number | number or null | percent | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.battery_plugged_code | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.battery_status_code | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.battery_technology | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.battery_temp_celsius | number | number or null | degrees Celsius | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.battery_voltage_mv | integer | integer or null | millivolts | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.build_bootloader | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.build_display | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.build_fingerprint | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.build_id | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.build_tags | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.build_time_ms | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| android_native_data.build_type | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.cpu_abi | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.data_storage_free_gb | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.data_storage_total_gb | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.developer_options_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.device_board | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.device_brand | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.device_hardware | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.device_manufacturer | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.device_model | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.device_product | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.egl_renderer | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.egl_vendor | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.elapsed_realtime_ms | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| android_native_data.font_scale | integer, number | integer, number or null | dimensionless ratio | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.gles_version | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.has_accelerometer | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_cellular_transport | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_gravity_sensor | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_gyroscope | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_light_sensor | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_magnetic_field | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_pressure_sensor | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_proximity_sensor | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_rotation_vector | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_step_counter | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_step_detector | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_vpn_transport | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.has_wifi_transport | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.http_proxy_setting | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.is_adb_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.is_charging | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.is_low_memory | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.java_http_proxy_host | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.java_http_proxy_port | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.kernel_arch | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.link_downstream_kbps | integer | integer or null | kilobits per second | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.link_upstream_kbps | integer | integer or null | kilobits per second | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.memory_threshold_gb | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.native_country | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.native_gpu_renderer | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.native_gpu_vendor | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.native_language | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.native_locale | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.native_timezone_id | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.native_timezone_offset_min | integer | integer or null | minutes; Android UTC-offset convention | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.network_metered | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.orientation_code | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.os_api_level | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.os_version | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.screen_density_dpi | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_mode_physical_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_mode_physical_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_mode_refresh_rate_hz | integer, number | integer, number or null | hertz | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_refresh_rate_hz | integer, number | integer, number or null | hertz | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_resolution_physical | string | string or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_validated_semantic_value |
| android_native_data.screen_scaled_density | number | number or null | dimensionless ratio | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_xdpi | number | number or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.screen_ydpi | number | number or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.security_patch | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| android_native_data.sensor_name_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.sensor_total_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.sensor_type_list | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.sensor_vendor_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.su_binary_present | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.supported_abis | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| android_native_data.total_memory_gb | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| android_native_data.uptime_ms | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| web_data.audio_context_supported | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.audio_error | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.audio_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.audio_output_latency | integer, number | integer, number or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.audio_sample_rate | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.avail_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.avail_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.available_font_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.camera_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.canvas_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.clipboard_read_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.color_depth | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.compute_task_time_ms | number | number or null | milliseconds; exact timestamps suppressed where applicable | retain_numeric_or_boolean_manual_privacy_review |
| web_data.cookie_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.device_memory | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| web_data.device_pixel_ratio | number | number or null | dimensionless ratio | retain_numeric_or_boolean_manual_privacy_review |
| web_data.do_not_track | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.downlink_mbps | integer, number | integer, number or null | megabits per second | retain_numeric_or_boolean_manual_privacy_review |
| web_data.effective_type | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.font_probe_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| web_data.font_probe_error | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.geolocation_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.hardware_concurrency | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| web_data.inner_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.inner_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.language | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.languages | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.local_storage_available | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.max_touch_points | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| web_data.microphone_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.mime_types_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| web_data.mime_types_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.notification_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.online | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.orientation_angle | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.orientation_type | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.outer_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.outer_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.performance_time_origin | integer, number | integer, number or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| web_data.permission_query_errors | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.permissions_api_supported | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.pixel_depth | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.platform | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.plugin_probe_error | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.plugins_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| web_data.plugins_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.product | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.product_sub | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.rtt_ms | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | retain_numeric_or_boolean_manual_privacy_review |
| web_data.save_data | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.screen_resolution_logical | string | string or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_validated_semantic_value |
| web_data.session_storage_available | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.timezone_id | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| web_data.timezone_offset | integer | integer or null | minutes; JavaScript getTimezoneOffset convention (opposite sign to UTC offset) | retain_numeric_or_boolean_manual_privacy_review |
| web_data.user_agent | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.vendor | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.visual_viewport_height | integer, number | integer, number or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.visual_viewport_scale | integer | integer, number or null | dimensionless ratio | retain_numeric_or_boolean_manual_privacy_review |
| web_data.visual_viewport_width | integer, number | integer, number or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| web_data.webdriver | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.webgl2_supported | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.webgl_aliased_line_width_range | string | string or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | remove_free_text_or_high_entropy_value |
| web_data.webgl_extensions_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| web_data.webgl_max_texture_size | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| web_data.webgl_max_viewport_dims | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.webgl_renderer | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| web_data.webgl_vendor | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.allow_content_access | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.allow_file_access | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.app_package_name | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.app_version_code | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.app_version_name | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.bridge_latency_ms | number | number or null | milliseconds; exact timestamps suppressed where applicable | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.database_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.default_ua_native | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.dom_storage_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.first_install_time | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| webview_data.installer_package | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.is_cleartext_traffic_permitted | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.is_debuggable | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.java_script_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.jsbridge_injected | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.last_update_time | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| webview_data.min_sdk_version | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.mixed_content_mode | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.safe_browsing_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.settings_user_agent | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.system_http_agent | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.target_sdk_version | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.webview_provider_major | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| webview_data.webview_provider_package | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.webview_provider_version | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| webview_data.webview_provider_version_code | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.audio_context_supported | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.audio_error | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.audio_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.audio_output_latency | integer, number | integer, number or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.audio_sample_rate | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.avail_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.avail_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.available_font_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.camera_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.canvas_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.clipboard_read_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.color_depth | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.compute_task_time_ms | number | number or null | milliseconds; exact timestamps suppressed where applicable | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.cookie_enabled | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.device_memory | number | number or null | GiB as reported by the collector | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.device_pixel_ratio | number | number or null | dimensionless ratio | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.do_not_track | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.downlink_mbps | integer, number | integer, number or null | megabits per second | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.effective_type | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.font_probe_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.font_probe_error | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.geolocation_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.hardware_concurrency | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.inner_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.inner_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.language | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.languages | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.local_storage_available | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.max_touch_points | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.microphone_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.mime_types_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.mime_types_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.notification_permission_state | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.online | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.orientation_angle | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.orientation_type | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.outer_height | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.outer_width | integer | integer or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.performance_time_origin | integer, number | integer, number or null | milliseconds; exact timestamps suppressed where applicable | remove_precise_time |
| browser_web_data.permission_query_errors | array | array or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.permissions_api_supported | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.pixel_depth | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.platform | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.plugin_probe_error | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.plugins_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.plugins_hash | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.product | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.product_sub | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.rtt_ms | integer | integer or null | milliseconds; exact timestamps suppressed where applicable | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.save_data | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.screen_resolution_logical | string | string or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_validated_semantic_value |
| browser_web_data.session_storage_available | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.timezone_id | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | retain_validated_semantic_value |
| browser_web_data.timezone_offset | integer | integer or null | minutes; JavaScript getTimezoneOffset convention (opposite sign to UTC offset) | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.user_agent | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.vendor | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.visual_viewport_height | integer, number | integer, number or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.visual_viewport_scale | integer | integer, number or null | dimensionless ratio | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.visual_viewport_width | integer, number | integer, number or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.webdriver | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.webgl2_supported | boolean | boolean or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.webgl_aliased_line_width_range | string | string or null | reported pixels; Web dimensions CSS pixels, Native physical dimensions physical pixels | remove_free_text_or_high_entropy_value |
| browser_web_data.webgl_extensions_count | integer | integer or null | count | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.webgl_max_texture_size | integer | integer or null | collector-native categorical, boolean or scalar; no conversion applied | retain_numeric_or_boolean_manual_privacy_review |
| browser_web_data.webgl_max_viewport_dims | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.webgl_renderer | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
| browser_web_data.webgl_vendor | string | string or null | collector-native categorical, boolean or scalar; no conversion applied | remove_free_text_or_high_entropy_value |
