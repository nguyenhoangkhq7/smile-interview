// Run with: node --test scripts/auth-session.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const src = path.resolve(import.meta.dirname, '../src');

function setup() {
  const modules = new Map();
  const storage = new Map();
  const timers = new Map();
  const listeners = new Map();
  const redirects = [];
  let effect;
  let timerId = 0;
  const sandbox = {
    atob, Date, process,
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    window: {
      location: { pathname: '/profile', replace: url => redirects.push(url) },
      addEventListener: (name, callback) => listeners.set(name, callback),
      removeEventListener: name => listeners.delete(name),
    },
    document: {
      addEventListener: (name, callback) => listeners.set(name, callback),
      removeEventListener: name => listeners.delete(name),
    },
    setTimeout: (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout: id => timers.delete(id),
  };
  function load(file) {
    if (modules.has(file)) return modules.get(file).exports;
    const module = { exports: {} };
    modules.set(file, module);
    const output = ts.transpileModule(readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText;
    const localRequire = name => {
      if (name === 'react') return { useEffect: callback => { effect = callback; } };
      if (name.startsWith('.') || name.startsWith('@/')) {
        const base = name.startsWith('@/') ? path.join(src, name.slice(2)) : path.resolve(path.dirname(file), name);
        return load(base + '.ts');
      }
      // Ensure Zustand persistence uses this isolated localStorage as well.
      if (name === 'zustand/middleware') {
        const middleware = require(name);
        return { ...middleware, createJSONStorage: () => middleware.createJSONStorage(() => sandbox.localStorage) };
      }
      return require(name);
    };
    vm.runInNewContext(`(function(require, module, exports) { ${output}\n})`, sandbox)(localRequire, module, module.exports);
    return module.exports;
  }
  const store = load(path.join(src, 'store/authStore.ts')).useAuthStore;
  const session = load(path.join(src, 'lib/authSession.ts'));
  const client = load(path.join(src, 'lib/axiosClient.ts')).default;
  const monitor = load(path.join(src, 'components/auth/AuthSessionMonitor.tsx')).default;
  return { store, session, client, timers, listeners, redirects, storage,
    mount: () => { monitor(); return effect(); } };
}

const token = (exp, sub = 'user') => `e30.${Buffer.from(JSON.stringify({ exp, sub })).toString('base64url')}.signature`;
const login = (app, jwt) => app.store.getState().login({ id: '1', role: 'USER' }, jwt);

test('expiry decoding rejects malformed/missing expiry and honors the exact boundary', () => {
  const app = setup();
  for (const jwt of ['bad', 'a.@@.b', token(undefined), token('123')]) {
    assert.equal(app.session.getTokenExpiresAt(jwt), null);
  }
  assert.equal(app.session.getTokenExpiresAt(token(123)), 123000);
});

test('restored expired token logs out immediately and clears persisted credentials', () => {
  const app = setup();
  login(app, token(1));
  const cleanup = app.mount();
  assert.equal(app.store.getState().isAuthenticated, false);
  assert.equal(JSON.parse(app.storage.get('auth-storage')).state.token, null);
  assert.deepEqual(app.redirects, ['/login']);
  cleanup();
});

test('idle expiry, wakeup checks, login changes and cleanup work without API calls', () => {
  const app = setup();
  login(app, token(Math.floor(Date.now() / 1000) + 60));
  const cleanup = app.mount();
  assert.equal(app.timers.size, 1);
  assert.ok([...app.timers.values()][0].delay <= 60000);
  app.listeners.get('focus')();
  app.listeners.get('visibilitychange')();
  assert.equal(app.timers.size, 1);
  // Model the clock advancing to the expiration boundary.
  const realNow = Date.now;
  Date.now = () => realNow() + 61000;
  try { [...app.timers.values()][0].callback(); } finally { Date.now = realNow; }
  assert.equal(app.store.getState().token, null);
  login(app, token(Math.floor(Date.now() / 1000) + 120));
  assert.equal(app.timers.size, 1);
  cleanup();
  assert.equal(app.timers.size, 0);
  assert.equal(app.listeners.size, 0);
});

test('expired requests are canceled before reaching the server', async () => {
  const app = setup();
  login(app, token(1));
  let requests = 0;
  await assert.rejects(app.client.get('/api/v1/resumes', { adapter: async () => { requests++; } }));
  assert.equal(requests, 0);
  assert.equal(app.store.getState().token, null);
});

test('401 logs out, 403 preserves login, and a late 401 cannot clear a new login', async () => {
  const app = setup();
  const first = token(Math.floor(Date.now() / 1000) + 60);
  const second = token(Math.floor(Date.now() / 1000) + 120, 'other-user');
  const fail = status => config => Promise.reject({ config, response: { status } });
  login(app, first);
  await assert.rejects(app.client.get('/api/hr/test', { adapter: fail(403) }));
  assert.equal(app.store.getState().token, first);
  await assert.rejects(app.client.get('/api/v1/resumes', { adapter: fail(401) }));
  assert.equal(app.store.getState().token, null);
  login(app, first);
  await assert.rejects(app.client.get('/api/v1/resumes', { adapter: config => {
    login(app, second);
    return fail(401)(config);
  } }));
  assert.equal(app.store.getState().token, second);
  app.store.getState().logout();
  await assert.rejects(app.client.post('/api/auth/login', {}, { adapter: fail(401) }));
  assert.equal(app.redirects.length, 1);
});
