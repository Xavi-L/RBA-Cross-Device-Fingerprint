import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {injectionSource} from './memory_only_cdp.mjs';

function context() {
  class Navigator {}
  Object.defineProperties(Navigator.prototype,{
    deviceMemory:{configurable:true,get:()=>2},
    hardwareConcurrency:{configurable:true,get:()=>8},
    userAgent:{configurable:true,get:()=>'original'},
    platform:{configurable:true,get:()=>'Linux armv8l'},
    webdriver:{configurable:true,get:()=>false},
  });
  return {Navigator,navigator:new Navigator(),screen:{width:720,height:1280},window:{}};
}
test('all targets modify only deviceMemory on the owned navigator',()=>{
  for (const value of [2,4,8,16]) {
    const c=context();vm.runInNewContext(injectionSource(value),c);
    assert.equal(c.navigator.deviceMemory,value);
    assert.equal(c.navigator.hardwareConcurrency,8);
    assert.equal(c.navigator.userAgent,'original');assert.equal(c.navigator.platform,'Linux armv8l');
    assert.equal(c.navigator.webdriver,false);
    assert.deepEqual(Object.keys(c.window),[]);assert.deepEqual(c.screen,{width:720,height:1280});
    assert.deepEqual(Object.getOwnPropertyNames(c.navigator),['deviceMemory']);
  }
});
test('same flow noop leaves every descriptor unchanged',()=>{
  const c=context(),before=Object.getOwnPropertyDescriptors(c.Navigator.prototype);
  vm.runInNewContext(injectionSource(null),c);
  assert.deepEqual(Object.getOwnPropertyDescriptors(c.Navigator.prototype),before);
  assert.deepEqual(Object.getOwnPropertyNames(c.navigator),[]);
});
test('only fixed numeric targets are accepted and fresh realm restores',()=>{
  for(const t of [0,-1,1,3,32,'8',NaN,Infinity,undefined])assert.throws(()=>injectionSource(t));
  const c=context();vm.runInNewContext(injectionSource(16),c);
  assert.equal(c.navigator.deviceMemory,16);assert.equal(context().navigator.deviceMemory,2);
});
