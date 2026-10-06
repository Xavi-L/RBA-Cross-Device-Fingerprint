import fs from 'node:fs';
import {positions} from './collect.mjs';
const [destination,id,mode]=process.argv.slice(2);
const p={schema_version:'cross-endpoint-matched-controls-plan-v1',run_id:id,mode,
  created_at:new Date().toISOString(),serial:'emulator-5580',device_manifest_id:'b2b-api36p1-arm64-chrome134',
  adb:'/Users/xavier/Library/Android/sdk/platform-tools/adb',browser_package:'com.android.chrome',
  app_package:'com.example.hybridguard.featureapp',app_activity:'com.example.hybridguard.featureapp/.MainActivity',
  static_origin:'http://127.0.0.1:8001',collect_endpoint:'http://127.0.0.1:8000/api/collect/fingerprint',
  cdp_origin:'http://127.0.0.1:9340',debug_wait_ms:30000,collection_wait_ms:60000,
  fixed_targets:{language:'fr-FR',languages:['fr-FR'],timezone:'Asia/Tokyo'},
  original:{system_language:'en-US',timezone:'Asia/Shanghai',auto_time_zone:'1',browser_preferred_languages:['en-US','en']},
  positions:positions(id,mode==='formal'?2:1,mode==='formal'?undefined:['A_APP_LANG','A_APP_TZ','A_BROWSER_LANG','A_BROWSER_TZ']),
  sampling:'One formal pass, failures retained. Engineering corrections only; no detector-driven resampling.',
  label_policy:'Execution, observed scope, control interval, and restoration; never a detector result.',
  candidate_status:'B2-A fixed diagnostics; no training, no eligibility upgrade.',
  publication:'New raw fingerprints, pair tickets, and traces are local-only pending separate authorization.'};
fs.writeFileSync(destination,JSON.stringify(p,null,2)+'\n',{flag:'wx'});
