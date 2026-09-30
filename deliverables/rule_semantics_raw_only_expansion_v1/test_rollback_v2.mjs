import assert from 'node:assert/strict';
import { summarizeScopedRollback } from './week10_cdp_emulation_runtime_v2.mjs';

const baseline={timezone:{id:'Asia/Shanghai',offset_minutes:-480},screen:{width:412,height:915,avail_width:412,avail_height:915,device_pixel_ratio:2.625,inner_height:639}};
const resized=structuredClone(baseline);resized.screen.inner_height=573;
for(const id of ['cdp_timezone_only_v1','cdp_screen_metrics_only_v1']){
  const result=summarizeScopedRollback(id,baseline,resized,[{ok:true}]);
  assert.equal(result.rollback_verified,true);
  assert.equal(result.full_runtime_equality_observed,false);
  assert.equal(result.full_runtime_restoration_claimed,false);
  assert.equal(result.paired_payload_restoration_required,true);
  assert.equal(summarizeScopedRollback(id,baseline,resized,[{ok:false}]).rollback_verified,false);
  assert.equal(summarizeScopedRollback(id,null,resized,[{ok:true}]).rollback_verified,false);
}
const wrongTimezone=structuredClone(resized);wrongTimezone.timezone.id='America/Los_Angeles';
assert.equal(summarizeScopedRollback('cdp_timezone_only_v1',baseline,wrongTimezone,[{ok:true}]).rollback_verified,false);
const wrongDpr=structuredClone(resized);wrongDpr.screen.device_pixel_ratio=2.75;
assert.equal(summarizeScopedRollback('cdp_screen_metrics_only_v1',baseline,wrongDpr,[{ok:true}]).rollback_verified,false);
assert.equal(summarizeScopedRollback('unknown',baseline,resized,[{ok:true}]).rollback_verified,false);
console.log('PASS: host viewport drift remains recorded; missing data, wrong target state and failed rollback commands rejected; paired restoration mandatory.');
