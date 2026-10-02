import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('./diagnostic/diagnostic.js', import.meta.url), 'utf8');
function run(fault) {
  const window = {location: {href: 'about:blank'}, AndroidBridge: {getSessionId: () => 'synthetic'},
    document: {createElement: () => ({getContext: () => {
      const queue = fault === 'creation' ? [1280] : [];
      return {getError: () => queue.shift() || 0,
        isContextLost: () => {if (fault === 'state') queue.push(1280); return false;},
        getExtension: () => {if (fault === 'extension') queue.push(1280);
          return {UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446};},
        getParameter: value => Number(value) === 34921 ? 16 : 'synthetic string'};
    }})}};
  vm.runInNewContext(source, {window});
  return JSON.parse(JSON.stringify(window.HybridGuardWebGLDiagnostic.run(['error_first'])));
}
for (const [fault, firstOperation] of [['creation', 'after_context_creation'],
                                    ['state', 'after_isContextLost'],
                                    ['extension', 'after_getExtension_and_constants']]) {
  test(`localize synthetic ${fault} error without assigning it to later queries`, () => {
    const result = run(fault);
    assert.equal(result.contexts.length, 2);
    for (const context of result.contexts) {
      assert.equal(context.status, 'MEASURED');
      assert.equal(context.events.find(event => event.errors.length).operation, firstOperation);
      assert.ok(context.events.filter(event => event.operation === 'getParameter').every(event => event.errors.length === 0));
    }
  });
}
