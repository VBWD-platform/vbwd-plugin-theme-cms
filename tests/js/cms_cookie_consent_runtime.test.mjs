// S152-06b — the themed CookieConsent runtime, run with
// `node --test 'plugins/theme_cms/tests/js/*.test.mjs'`. It must write the SAME
// localStorage record as fe-user `consent/useConsent.ts` (key `vbwd_cookie_consent`,
// {version, decidedAt, method, categories}) and push the same Consent Mode v2
// signals as `consent/consentMode.ts`. The script runs in a vm on a tiny DOM.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const SCRIPT = readFileSync(
  fileURLToPath(
    new URL('../../theme_cms/templates/cms/partials/cms_cookie_consent_runtime.js', import.meta.url),
  ),
  'utf8',
);
const NOW = '2026-10-03T12:00:00.000Z';

function matchesSimple(element, selector) {
  const attribute = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(selector);
  if (attribute) {
    if (!element.attributes.has(attribute[1])) return false;
    return attribute[2] === undefined || element.attributes.get(attribute[1]) === attribute[2];
  }
  return element.classes.has(selector.replace(/^\./, ''));
}

function el(classNames, attributes = {}, children = []) {
  const element = {
    classes: new Set(classNames.split(' ').filter(Boolean)),
    attributes: new Map(Object.entries(attributes)),
    children,
    parent: null,
    hidden: 'hidden' in attributes,
    checked: 'checked' in attributes,
    disabled: 'disabled' in attributes,
    focused: false,
    getAttribute: (name) => (element.attributes.has(name) ? element.attributes.get(name) : null),
    setAttribute: (name, value) => element.attributes.set(name, String(value)),
    focus() { element.focused = true; },
    closest(selector) {
      for (let current = element; current; current = current.parent) {
        if (current.classes && matchesSimple(current, selector)) return current;
      }
      return null;
    },
    querySelectorAll(selector) {
      const found = [];
      const walk = (node) => node.children.forEach((child) => {
        if (matchesSimple(child, selector)) found.push(child);
        walk(child);
      });
      walk(element);
      return found;
    },
    querySelector(selector) { return element.querySelectorAll(selector)[0] || null; },
  };
  children.forEach((child) => { child.parent = element; });
  return element;
}

function consentWidget({ version = '1', categories = ['necessary', 'statistics', 'marketing'] } = {}) {
  const button = (testid) => el('cookie-consent__btn', { 'data-testid': testid });
  const toggles = categories.map((category) =>
    el('cookie-consent__toggle', {
      'data-cookie-category': category,
      ...(category === 'necessary' ? { checked: '', disabled: '' } : {}),
    }));
  const summary = [
    el('cookie-consent__title', { 'data-cookie-consent-layer': 'summary', id: 'cookie-consent-title' }),
    el('cookie-consent__actions', { 'data-cookie-consent-layer': 'summary' }, [
      button('cookie-accept-all'), button('cookie-reject-all'), button('cookie-customize'),
    ]),
  ];
  const customize = [
    el('cookie-consent__title', { 'data-cookie-consent-layer': 'customize', hidden: '', id: 'cookie-consent-customize-title' }),
    el('cookie-consent__categories', { 'data-cookie-consent-layer': 'customize', hidden: '' }, toggles),
    el('cookie-consent__actions', { 'data-cookie-consent-layer': 'customize', hidden: '' }, [button('cookie-save')]),
  ];
  const dialog = el('cookie-consent', { 'aria-labelledby': 'cookie-consent-title' }, [...summary, ...customize]);
  const backdrop = el('cookie-consent__backdrop', { 'data-consent-version': version, hidden: '' }, [dialog]);
  const settings = el('cookie-consent__settings', { 'data-testid': 'cookie-settings', hidden: '' });
  return { backdrop, settings, dialog, toggles, customize, summary };
}

function storage(initial = {}) {
  const entries = new Map(Object.entries(initial));
  return {
    getItem: (key) => (entries.has(key) ? entries.get(key) : null),
    setItem: (key, value) => entries.set(key, String(value)),
    entries,
  };
}

function load({ stored, widget = consentWidget(), gtag } = {}) {
  const body = el('body', {}, [widget.backdrop, widget.settings]);
  const documentListeners = {};
  const windowListeners = {};
  const dispatched = [];
  const document = {
    readyState: 'complete',
    body,
    querySelectorAll: (selector) => body.querySelectorAll(selector),
    addEventListener: (type, listener) => (documentListeners[type] = documentListeners[type] || []).push(listener),
  };
  const localStorage = storage(stored === undefined ? {} : { vbwd_cookie_consent: JSON.stringify(stored) });
  class FakeDate { toISOString() { return NOW; } }
  const context = {
    document,
    localStorage,
    Date: FakeDate,
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
    addEventListener: (type, listener) => (windowListeners[type] = windowListeners[type] || []).push(listener),
    dispatchEvent: (event) => { dispatched.push(event); (windowListeners[event.type] || []).forEach((l) => l(event)); },
  };
  if (gtag) context.gtag = gtag;
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SCRIPT, context, { filename: 'cms_cookie_consent_runtime.js' });
  const fire = (type, event) => (documentListeners[type] || []).forEach((listener) => listener(event));
  const click = (target) => fire('click', { target, preventDefault() {} });
  return { context, widget, localStorage, dispatched, fire, click, windowListeners };
}

const storedRecord = (runtime) => JSON.parse(runtime.localStorage.entries.get('vbwd_cookie_consent'));
const plain = (value) => JSON.parse(JSON.stringify(value));
const layerHidden = (widget, layer) =>
  [...widget.summary, ...widget.customize]
    .filter((element) => element.getAttribute('data-cookie-consent-layer') === layer)
    .every((element) => element.hidden);

test('a first visit opens the dialog on the summary layer and pushes the all-denied default', () => {
  const runtime = load();

  assert.equal(runtime.widget.backdrop.hidden, false);
  assert.equal(runtime.widget.settings.hidden, true);
  assert.equal(layerHidden(runtime.widget, 'customize'), true);
  assert.equal(layerHidden(runtime.widget, 'summary'), false);
  assert.deepEqual(plain(runtime.context.dataLayer[0]), [
    'consent',
    'default',
    {
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'denied',
      functionality_storage: 'denied',
      personalization_storage: 'denied',
      security_storage: 'granted',
    },
  ]);
  assert.equal(runtime.widget.summary[1].children[0].focused, true);
});

test('accept all writes the useConsent record shape and closes to the settings button', () => {
  const runtime = load();

  runtime.click(runtime.widget.summary[1].children[0]);

  assert.deepEqual(storedRecord(runtime), {
    version: 1,
    decidedAt: NOW,
    method: 'accept_all',
    categories: { necessary: true, preferences: true, statistics: true, marketing: true },
  });
  assert.equal(runtime.widget.backdrop.hidden, true);
  assert.equal(runtime.widget.settings.hidden, false);
  const update = plain(runtime.context.dataLayer.at(-1));
  assert.equal(update[1], 'update');
  assert.equal(update[2].analytics_storage, 'granted');
  assert.equal(update[2].ad_storage, 'granted');
  const changed = runtime.dispatched.find((event) => event.type === 'vbwd:consent-changed');
  assert.deepEqual(plain(changed.detail.categories), storedRecord(runtime).categories);
});

test('reject all stores only the necessary category', () => {
  const runtime = load();

  runtime.click(runtime.widget.summary[1].children[1]);

  assert.equal(storedRecord(runtime).method, 'reject_all');
  assert.deepEqual(storedRecord(runtime).categories, {
    necessary: true, preferences: false, statistics: false, marketing: false,
  });
});

test('customize shows the category layer seeded from the stored decision, save writes custom', () => {
  const stored = {
    version: 1, decidedAt: 'x', method: 'custom',
    categories: { necessary: true, preferences: false, statistics: false, marketing: true },
  };
  const runtime = load({ stored });
  runtime.click(runtime.widget.settings);
  runtime.click(runtime.widget.summary[1].children[2]);

  assert.equal(layerHidden(runtime.widget, 'summary'), true);
  assert.equal(layerHidden(runtime.widget, 'customize'), false);
  assert.equal(runtime.widget.dialog.getAttribute('aria-labelledby'), 'cookie-consent-customize-title');
  const [necessary, statistics, marketing] = runtime.widget.toggles;
  assert.deepEqual([necessary.checked, statistics.checked, marketing.checked], [true, false, true]);

  statistics.checked = true;
  marketing.checked = false;
  runtime.click(runtime.widget.customize[2].children[0]);

  assert.deepEqual(storedRecord(runtime), {
    version: 1,
    decidedAt: NOW,
    method: 'custom',
    categories: { necessary: true, preferences: false, statistics: true, marketing: false },
  });
  assert.equal(runtime.widget.backdrop.hidden, true);
});

test('a returning visitor stays closed and re-emits the stored decision', () => {
  const stored = {
    version: 2, decidedAt: 'x', method: 'reject_all',
    categories: { necessary: true, preferences: false, statistics: false, marketing: false },
  };
  const runtime = load({ stored, widget: consentWidget({ version: '2' }) });

  assert.equal(runtime.widget.backdrop.hidden, true);
  assert.equal(runtime.widget.settings.hidden, false);
  assert.deepEqual(
    plain(runtime.context.dataLayer.map((entry) => entry[1])),
    ['default', 'update'],
  );
});

test('a newer consent version asks again', () => {
  const stored = { version: 1, decidedAt: 'x', method: 'accept_all', categories: { necessary: true } };

  const runtime = load({ stored, widget: consentWidget({ version: '2' }) });

  assert.equal(runtime.widget.backdrop.hidden, false);
});

test('a corrupt record counts as no decision', () => {
  const runtime = load({ stored: { version: 'one' } });

  assert.equal(runtime.widget.backdrop.hidden, false);
});

test('the open-consent window event and a regions swap re-open / re-apply the state', () => {
  const stored = { version: 1, decidedAt: 'x', method: 'accept_all', categories: { necessary: true } };
  const runtime = load({ stored });

  runtime.windowListeners['vbwd:open-cookie-consent'][0]({});
  assert.equal(runtime.widget.backdrop.hidden, false);

  runtime.widget.backdrop.hidden = true;
  runtime.widget.settings.hidden = true;
  runtime.click(runtime.widget.summary[1].children[0]);
  runtime.widget.settings.hidden = true;
  runtime.fire('vbwd:regions-swapped', {});
  assert.equal(runtime.widget.settings.hidden, false);
});

test('escape never dismisses the dialog', () => {
  const runtime = load();
  let prevented = false;

  runtime.fire('keydown', {
    key: 'Escape',
    target: runtime.widget.summary[1].children[0],
    preventDefault() { prevented = true; },
  });

  assert.equal(prevented, true);
  assert.equal(runtime.widget.backdrop.hidden, false);
});

test('a present gtag receives the consent command instead of the dataLayer queue', () => {
  const calls = [];
  load({ gtag: (...args) => calls.push(args) });

  assert.equal(calls[0][0], 'consent');
  assert.equal(calls[0][1], 'default');
});

test('a page without the widget does nothing', () => {
  const context = {
    document: {
      readyState: 'complete',
      querySelectorAll: () => [],
      addEventListener() {},
    },
    localStorage: storage(),
    addEventListener() {},
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SCRIPT, context);

  assert.equal(context.dataLayer, undefined);
});
