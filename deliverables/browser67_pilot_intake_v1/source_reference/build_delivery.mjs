import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, relative, dirname, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
const readJson = async (path) => JSON.parse(await readFile(resolve(root, path), 'utf8'));
const readRows = async (path) => (await readFile(resolve(root, path), 'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse);
const writeJson = async (path, value) => writeFile(resolve(root, path), `${JSON.stringify(value, null, 2)}\n`, { flag: 'wx' });
const writeRows = async (path, rows) => writeFile(resolve(root, path), rows.map((row) => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : ''), { flag: 'wx' });
const fieldPaths = {
  language: 'web_data.navigator_layer.language', languages: 'web_data.navigator_layer.languages',
  timezone_id: 'web_data.execution_layer.timezone_id', timezone_offset: 'web_data.execution_layer.timezone_offset',
};
function requireCondition(condition, code) { if (!condition) throw new Error(code); }
function getPath(value, path) { return path.split('.').reduce((current, key) => current?.[key], value); }
function observations(payload) { return Object.fromEntries(Object.entries(fieldPaths).map(([key, path]) => [key, getPath(payload, path)])); }
const portable = (path) => path.split('\\').join('/');

export function validateAttemptSummary(summary, captures) {
  requireCondition(Number.isInteger(summary.planned) && summary.planned === 18 && captures.length === summary.planned,
    'ATTEMPT_PLANNED_COUNT_MISMATCH');
  requireCondition(new Set(captures.map((capture) => capture.capture_id)).size === captures.length,
    'ATTEMPT_CAPTURE_ID_NOT_UNIQUE');
  requireCondition(captures.every((capture) => ['completed', 'failed', 'skipped'].includes(capture.result)),
    'ATTEMPT_RESULT_INVALID');
  for (const result of ['completed', 'failed', 'skipped']) {
    requireCondition(summary[result] === captures.filter((capture) => capture.result === result).length,
      'ATTEMPT_SUMMARY_COUNT_MISMATCH');
  }
}

export function validateVerifierSelfTest(report, pilot) {
  requireCondition(report.selected_pilot === pilot && report.real_data_baseline_passed === true
    && report.original_evidence_modified === false && Number.isInteger(report.tests) && report.tests >= 8
    && report.passed === report.tests && Array.isArray(report.rejected_mutations)
    && report.rejected_mutations.length === report.tests - 1, 'SELECTED_VERIFIER_SELF_TEST_REQUIRED');
}

async function requireCurrentVerification(pilot) {
  const report = await readJson('verification.json');
  requireCondition(report.verification === 'passed' && report.selected_pilot === pilot, 'SELECTED_INDEPENDENT_VERIFICATION_REQUIRED');
  requireCondition(report.input_file_sha256 && Object.keys(report.input_file_sha256).length >= 10, 'VERIFICATION_INPUT_LOCKS_REQUIRED');
  for (const [path, expected] of Object.entries(report.input_file_sha256)) {
    const absolute = resolve(root, path);
    const within = relative(root, absolute);
    requireCondition(!within.startsWith('..') && !isAbsolute(within), 'VERIFICATION_PATH_OUTSIDE_ROOT');
    requireCondition(digest(await readFile(absolute)) === expected, 'VERIFICATION_INPUT_CHANGED');
  }
  return report;
}

async function inventoryAttempts() {
  const attempts = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^pilot(?:_r\d+)?$/.test(entry.name)) continue;
    try {
      const summary = await readJson(`${entry.name}/summary.json`);
      const captures = await readRows(`${entry.name}/captures.jsonl`);
      validateAttemptSummary(summary, captures);
      attempts.push({ directory: entry.name, summary, captures });
    } catch (error) {
      if (error.code === 'ENOENT') throw new Error(`INCOMPLETE_ATTEMPT_INVENTORY: ${entry.name}`);
      throw error;
    }
  }
  return attempts.sort((a, b) => a.directory.localeCompare(b.directory, undefined, { numeric: true }));
}

async function prepare(pilot) {
  const verification = await requireCurrentVerification(pilot);
  const plan = await readJson('pilot_plan.json');
  const manifest = await readJson(`${pilot}/run_manifest.json`);
  requireCondition(manifest.plan_sha256 === digest(await readFile(resolve(root, 'pilot_plan.json'))), 'PLAN_LOCK_MISMATCH');
  const selected = await readRows(`${pilot}/captures.jsonl`);
  requireCondition(selected.length === 18 && selected.every((capture) => capture.result === 'completed'), 'COMPLETE_SELECTED_PILOT_REQUIRED');
  const bySession = new Map(selected.map((capture) => [capture.binding.app_session_id, capture]));
  requireCondition(bySession.size === 18, 'DUPLICATE_SELECTED_SESSION');
  const [apps, browsers, build, attempts, pairRows] = await Promise.all([
    readRows('data/raw_expanded_payloads.jsonl'), readRows('data/raw_browser_payloads.jsonl'),
    readJson('collector_build_manifest.json'), inventoryAttempts(), readRows('data/browser_pair_provenance.jsonl'),
  ]);
  const byBrowser = new Map(browsers.map((row) => [row.browser_session_id, row]));
  const facts = [];
  const sidecars = [];
  for (let index = 0; index < apps.length; index++) {
    const app = apps[index];
    const capture = bySession.get(app.session_id);
    const engineeringAttempt = attempts.find((attempt) => attempt.captures.some((slot) => slot.runtime_context === app.canonical_received_payload.collection_manifest.runtime_context));
    const engineeringPair = capture ? null : pairRows.find((pair) => pair.app_session_id === app.session_id && pair.pair_status === 'completed');
    const engineeringBrowser = engineeringPair ? byBrowser.get(engineeringPair.browser_session_id) : null;
    const active = capture?.stage === 'attack_active';
    const scenario = capture ? `${plan.device_manifest_id}:${capture.configuration_id}:r${capture.repeat}` : null;
    const evidence = [`data/raw_expanded_payloads.jsonl#L${index + 1}`];
    if (!capture && engineeringAttempt) evidence.push(`${engineeringAttempt.directory}/captures.jsonl`, `${engineeringAttempt.directory}/private_command_events.jsonl`);
    let browser = null;
    let control = null;
    let baseline = null;
    if (capture) {
      evidence.push(`${pilot}/captures.jsonl#${capture.capture_id}`, `${pilot}/private_command_events.jsonl#${capture.capture_id}`, 'verification.json');
      browser = byBrowser.get(capture.binding.browser_session_id);
      requireCondition(browser && browser.browser_payload_sha256 === capture.binding.browser_payload_sha256, 'BROWSER_BINDING_MISMATCH');
      control = plan.controls.find((item) => item.configuration_id === capture.configuration_id);
      baseline = selected.find((item) => item.configuration_id === capture.configuration_id && item.repeat === capture.repeat && item.stage === 'clean_pre');
      requireCondition(control && baseline, 'SCENARIO_BASELINE_MISSING');
    }
    const fact = {
      experiment_fact_version: 'latest-experiment-fact-v1', app_session_id: app.session_id,
      app_payload_sha256: app.payload_sha256, label_status: 'candidate', manipulation_present: capture ? active : null,
      evaluation_task: capture ? 'paired244_fingerprint_effect' : 'collection_reference',
      execution_status: capture ? (active ? 'succeeded' : 'not_applicable') : 'unknown',
      field_effect_status: capture ? (active ? 'observed' : 'no_configured_change') : 'unknown',
      stable_group_key_hash: null, identity_scope: 'run_profile', identity_stability: 'run_scoped_unverified',
      scenario_group_id: scenario, scenario_phase: capture?.stage ?? null, scenario_repetition: capture?.repeat ?? null,
      attack_family: capture ? 'browser_locale_timezone_control' : null, evidence_refs: evidence,
    };
    facts.push(fact);
    const appPayload = app.canonical_received_payload;
    const browserObserved = browser ? observations(browser.canonical_received_payload) : null;
    const mutations = active ? Object.keys(control.expected).map((name) => ({
      field: `browser.${fieldPaths[name]}`, before: baseline.observed[name], during: browserObserved[name],
      after: selected.find((item) => item.configuration_id === capture.configuration_id && item.repeat === capture.repeat && item.stage === 'clean_post').observed[name],
    })) : [];
    sidecars.push({
      manifest_version: 'sample-manifest-v1', sample_id: capture ? `${pilot}:${capture.capture_id}` : `engineering-reference:${index + 1}`,
      session_id_hash: digest(Buffer.from(app.session_id)), raw_payload_sha256: app.payload_sha256,
      capture: { source_type: 'local_emulator', provider: 'owned-api36-emulator', capture_batch_id: app.collection_batch_id,
        provider_run_id: capture ? pilot : engineeringAttempt?.directory ?? null },
      pair: capture ? { scenario_group_id: scenario, pair_role: capture.stage, sequence_index: ['clean_pre', 'attack_active', 'clean_post'].indexOf(capture.stage),
        browser_pair_id: capture.binding.pair_id, browser_session_id: capture.binding.browser_session_id, browser_payload_sha256: capture.binding.browser_payload_sha256 }
        : engineeringPair ? { scenario_group_id: null, pair_role: null, sequence_index: null, browser_pair_id: engineeringPair.pair_id,
          browser_session_id: engineeringPair.browser_session_id, browser_payload_sha256: engineeringPair.browser_payload_sha256 } : null,
      label: { environment_class: 'local_emulator', manipulation_present: capture ? active : null, violation_types: [],
        label_status: 'pending', label_provenance: capture ? 'controlled_browser_effect_verified_locally; upstream_label_review_pending' : 'engineering_attempt_not_selected; manipulation_and_effect_unknown' },
      attack: { intervention_scope: capture ? 'browser_only' : 'unknown', expected_external_browser_effect: capture ? 'configured_only_during_attack_active' : 'unknown',
        execution_status: fact.execution_status, feature_effect_status: capture ? (active ? 'not_observed' : 'not_applicable') : 'unknown',
        feature_effect_scope: capture ? 'App177_target_locale_timezone_fields' : 'unknown', browser_field_effect_status: fact.field_effect_status,
        attack_type: capture?.configuration_id ?? null, config_sha256: control ? digest(Buffer.from(JSON.stringify(control))) : null,
        tool_name: capture ? 'Chrome DevTools Protocol' : null, tool_version: capture?.browser_version?.product ?? null,
        tool_implementation_sha256: capture ? manifest.runner_sha256 : null, browser_package: capture ? plan.browser_package : null,
        target_layers: capture ? ['external_browser_web'] : [], expected_mutations: control ? Object.keys(control.expected).map((name) => `browser.${fieldPaths[name]}`) : [],
        observed_mutations: mutations, attribution: capture ? 'browser target controlled before original adapter execution; App target fields conserved' : 'incomplete engineering attempt',
        rollback_status: capture ? 'verified_command_and_clean_post' : 'unknown', success_evidence: evidence },
      device: { anonymous_device_instance_id: appPayload.collection_manifest.device_manifest_id,
        stable_device_key_hash: null, device_identity_stability: 'run_scoped_unverified', identity_scope: 'run_profile' },
      quality: { qc_status: capture ? 'passed_independent_pilot' : engineeringPair ? 'engineering_paired_reference_not_selected' : 'engineering_browser_incomplete', formal_experiment_eligible: false },
      raw_binding: { app_session_id: app.session_id, app_receipt_id: app.receipt_id, app_payload_sha256: app.payload_sha256,
        app_raw_reference: evidence[0], browser_raw_reference: capture ? `data/raw_browser_payloads.jsonl#L${capture.archives.browser.line}`
          : engineeringBrowser ? `data/raw_browser_payloads.jsonl#L${browsers.indexOf(engineeringBrowser) + 1}` : null },
    });
  }
  await mkdir(resolve(root, 'delivery'), { recursive: true });
  await writeRows('delivery/latest_experiment_facts.jsonl', facts);
  await writeRows('delivery/attack_sample_manifest.jsonl', sidecars);
  const sourceConfig = await readJson('upstream/hybridguard_agent/config/latest_paired244_sources.json');
  const lock = { ...sourceConfig,
    release: { ...sourceConfig.release, featureapp_version_code: build.version_code, featureapp_version_name: build.version_name,
      browser_probe_revision: build.configuration.WEB_PROBE_REVISION },
    sources: Object.fromEntries(Object.entries(sourceConfig.sources).map(([name, path]) => [name,
      name === 'feature_catalog' || name === 'browser_probe_manifest' ? path : resolve(root, 'data', path.split('/').at(-1))])),
  };
  await writeJson('delivery/latest_paired244_sources.local.json', lock);
  await writeJson('delivery/attempt_inventory.json', { selected_pilot: pilot,
    attempts: attempts.map(({ directory, summary }) => ({ directory, ...summary })),
    rule: 'All engineering failures/skipped slots retained separately; selected-pilot completion is not an unconditional collection success rate.' });
  console.log(`Prepared ${facts.length} candidate facts and ${sidecars.length} complete sidecars; selected ${pilot}`);
}

async function signature(path) {
  const bytes = await readFile(resolve(root, path));
  return { path: portable(path), bytes: bytes.length, sha256: digest(bytes),
    jsonl_rows: path.endsWith('.jsonl') ? bytes.toString('utf8').split('\n').filter((line) => line.trim()).length : null };
}

async function finalize(pilot) {
  const [qc, readiness, verification, attemptInventory, verifierTests] = await Promise.all([
    readJson('delivery/paired244_snapshot/qc_summary.json'), readJson('delivery/experiment_plan/experiment_readiness.json'),
    requireCurrentVerification(pilot), readJson('delivery/attempt_inventory.json'),
    readJson('verification_tests.json'),
  ]);
  validateVerifierSelfTest(verifierTests, pilot);
  requireCondition(verification.verification === 'passed' && attemptInventory.selected_pilot === pilot, 'SELECTED_VERIFIED_PILOT_REQUIRED');
  requireCondition(readiness.structural_ready === false && readiness.grouped_data_prerequisites_met === false, 'PILOT_MUST_NOT_UNLOCK_FORMAL_EVALUATION');
  const dataFiles = (await readdir(resolve(root, 'data'))).filter((name) => name.endsWith('.jsonl')).map((name) => `data/${name}`);
  const evidenceFiles = [
    ...dataFiles, `${pilot}/run_manifest.json`, `${pilot}/captures.jsonl`, `${pilot}/private_command_events.jsonl`, `${pilot}/session_provenance.jsonl`,
    `${pilot}/summary.json`, `${pilot}/post_run_cleanup.json`,
    'collector_build_manifest.json', 'pilot_plan.json', 'run_paired_browser_pilot.mjs', 'test_paired_browser_pilot.mjs', 'verify_pilot.py', 'build_delivery.mjs',
    'run_backend.py', 'backend_lifecycle_summary.json', 'verification.json', 'verification_tests.json', 'latest_experiment_fact_v1.schema.json',
    'source_git_blob_audit.json', 'engineering_history_summary.json', 'backend_origin_smoke.json',
    'delivery/latest_experiment_facts.jsonl', 'delivery/attack_sample_manifest.jsonl', 'delivery/latest_paired244_sources.local.json', 'delivery/attempt_inventory.json',
  ];
  for (const directory of ['delivery/paired244_snapshot', 'delivery/experiment_plan']) {
    for (const name of await readdir(resolve(root, directory))) evidenceFiles.push(`${directory}/${name}`);
  }
  for (const attempt of attemptInventory.attempts.filter((item) => item.directory !== pilot)) {
    for (const name of ['captures.jsonl', 'summary.json', 'run_manifest.json', 'private_command_events.jsonl']) evidenceFiles.push(`${attempt.directory}/${name}`);
  }
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (entry.isDirectory() && /^attempt(?:0|_r\d+)_sources$/.test(entry.name)) {
      for (const name of await readdir(resolve(root, entry.name))) evidenceFiles.push(`${entry.name}/${name}`);
    }
    if (entry.isFile() && /^(?:test_verify_pilot.*\.py|delivery_method\.md|run_backend_restricted\.py|test_run_backend_restricted\.py|backend_restricted_tests\.json|verifier_contract_tests\.json|source_current_git_audit\.json|upstream_contract_review\.md|node_collector_tests\.(?:json|tap)|observations_summary\.json)$/.test(entry.name)) {
      evidenceFiles.push(entry.name);
    }
  }
  const history = await readJson('engineering_history_summary.json');
  for (const item of history.predecessor_final_launch?.evidence ?? []) {
    requireCondition(/^predecessor_final_launch\/backend\.(?:stderr\.log|stdout\.log|pid)$/.test(item.path),
      'PREDECESSOR_EVIDENCE_PATH_NOT_ALLOWED');
    requireCondition(digest(await readFile(resolve(root, item.path))) === item.sha256,
      'PREDECESSOR_EVIDENCE_HASH_MISMATCH');
    evidenceFiles.push(item.path);
  }
  evidenceFiles.push(...Object.keys(verification.input_file_sha256));
  requireCondition(evidenceFiles.every((path) => !path.includes('private_profile_hmac') && !path.startsWith('device_backup/')), 'PRIVATE_SECRET_MUST_NOT_BE_PACKAGED');
  const files = await Promise.all([...new Set(evidenceFiles)].map(signature));
  const apps = await readRows('data/raw_expanded_payloads.jsonl');
  const pairs = await readRows('data/browser_pair_provenance.jsonl');
  const events = await readRows('data/browser_pair_events.jsonl');
  const attempts = new Set(events.filter((event) => ['ticket_issued', 'provisional_ticket_issued'].includes(event.event)).map((event) => event.pair_id));
  requireCondition(qc.counts.app177_valid_count >= 18 && qc.counts.paired244_completed_count >= 18, 'SELECTED_STAGES_MUST_PASS_SNAPSHOT_QC');
  const counts = { app_raw_archives: apps.length, app177_valid_count: qc.counts.app177_valid_count,
    browser_attempted_count: qc.counts.browser_attempted_count, paired244_completed_count: qc.counts.paired244_completed_count,
    browser_incomplete_count: qc.counts.browser_incomplete_count,
    raw_completed_pair_records: pairs.length, raw_ticketed_browser_attempts: attempts.size,
    selected_pilot_planned: 18, selected_pilot_completed: 18, selected_pilot_triplets: 6, configurations: 2,
    engineering_failed_slots: attemptInventory.attempts.filter((item) => item.directory !== pilot).reduce((sum, item) => sum + item.failed, 0),
    engineering_skipped_slots: attemptInventory.attempts.filter((item) => item.directory !== pilot).reduce((sum, item) => sum + item.skipped, 0) };
  await writeJson('delivery/delivery_manifest.json', { schema_version: 'browser67-pilot-delivery-v1', generated_at_utc: new Date().toISOString(),
    source_commit: verification.source_commit, selected_pilot: pilot, counts, independent_verification: 'passed',
    counts_scope: 'This corrected LF run only; all predecessor engineering attempts are separately retained in engineering_history_summary.json.',
    predecessor_engineering_history: 'engineering_history_summary.json',
    research_admission: { label_status: 'candidate', identity_stability: 'run_scoped_unverified', formal_experiment_eligible: false,
      grouped_data_prerequisites_met: false, held_out_performance_claim: false }, files,
    excluded_private_files: ['private_profile_hmac.key', 'device_backup/', 'Chrome/user data'],
    claim_boundary: 'Paired collection, locale/timezone effects, rollback, and QC only. No detector efficacy or old App177 denominator change.' });
  console.log(JSON.stringify({ counts, snapshot_qc: qc, experiment_readiness: readiness }));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [mode, pilot] = process.argv.slice(2);
  requireCondition(['--prepare', '--finalize'].includes(mode) && /^pilot(?:_r\d+)?$/.test(pilot ?? ''), 'USAGE: node build_delivery.mjs --prepare|--finalize pilot_rN');
  if (mode === '--prepare') await prepare(pilot); else await finalize(pilot);
}
