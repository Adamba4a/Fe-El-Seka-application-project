// Run from repository root: node specs/032-contact-support/catalog-check.cjs
const ts = require('../../apps/main/node_modules/typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const en = require('../../apps/main/messages/en.json');
const ar = require('../../apps/main/messages/ar.json');
const source = fs.readFileSync('apps/main/src/lib/i18n/messages-loader.ts', 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
} }).outputText;

function loader(fetch) {
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, fetch, process: { env: { R2_APP_CONTENT_PUBLIC_URL: 'https://catalog.test' } },
    require: (name) => name === './config' ? { locales: ['en', 'ar'] } : name.endsWith('ar.json') ? ar : en,
  });
  return exports;
}

function keys(object, prefix = '') {
  return Object.entries(object).flatMap(([key, value]) => typeof value === 'object'
    ? keys(value, `${prefix}${key}.`) : [`${prefix}${key}`]).sort();
}

(async () => {
  assert.deepEqual(keys(en), keys(ar), 'English and Arabic catalog keys must match');
  const offline = loader(async () => { throw new Error('offline'); });
  assert.equal((await offline.getMessages('ar')).support.trigger, ar.support.trigger);
  assert.equal((await offline.getMessages('en')).support.trigger, en.support.trigger);
  const partial = loader(async (url) => ({ ok: url.endsWith('/en.json'), json: async () => ({ locale: 'en', version: 'old', messages: {} }) }));
  assert.equal((await partial.getMessages('ar')).support.title, ar.support.title);
  const remote = loader(async (url) => ({ ok: true, json: async () => ({
    locale: url.endsWith('/ar.json') ? 'ar' : 'en', version: 'remote', messages: { common: { appName: 'Remote brand' } },
  }) }));
  assert.equal((await remote.getMessages('ar')).support.title, ar.support.title);
  assert.equal((await remote.getMessages('ar')).common.appName, 'Remote brand');
  console.log('PASS: catalog key parity, offline English/Arabic, missing Arabic catalog, stale remote catalog fallback and remote override.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
