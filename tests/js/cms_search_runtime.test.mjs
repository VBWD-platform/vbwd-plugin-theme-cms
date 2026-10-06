// S152-06b — the quick-search keyboard/mouse runtime of the themed Search box,
// run with `node --test 'plugins/theme_cms/tests/js/*.test.mjs'`. Mirrors
// PostSearch.vue: ArrowDown/ArrowUp wrap through the options
// (`.post-search__option--active`, aria-selected, aria-activedescendant), Escape
// and a click outside close the dropdown, Enter on an active row / a mousedown
// opens `/<slug>`, Enter with no active row submits the GET form (?q=).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const SCRIPT = readFileSync(
  fileURLToPath(new URL('../../theme_cms/templates/cms/partials/cms_search_runtime.js', import.meta.url)),
  'utf8',
);

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
    classList: {
      contains: (name) => element.classes.has(name),
      toggle(name, force) {
        if (force) element.classes.add(name); else element.classes.delete(name);
      },
    },
    getAttribute: (name) => (element.attributes.has(name) ? element.attributes.get(name) : null),
    setAttribute: (name, value) => element.attributes.set(name, String(value)),
    removeAttribute: (name) => element.attributes.delete(name),
    replaceChildren: () => { element.children = []; },
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

function searchBox(optionSlugs = ['/alpha', '/beta']) {
  const options = optionSlugs.map((href, index) =>
    el('post-search__option', {
      id: `lb-option-${index}`,
      'aria-selected': 'false',
      'data-testid': 'post-search-option',
      'data-href': href,
    }));
  const dropdown = el(
    'post-search__dropdown',
    optionSlugs.length ? { id: 'lb', 'data-testid': 'post-search-dropdown' } : { id: 'lb', hidden: '' },
    options,
  );
  const input = el('post-search__input', { 'aria-controls': 'lb', 'aria-expanded': 'false' });
  const form = el('post-search__form', {}, [input]);
  const root = el('post-search', {}, [form, dropdown]);
  return { root, form, input, dropdown, options };
}

function load(box = searchBox()) {
  const outside = el('outside');
  const body = el('body', {}, [box.root, outside]);
  const listeners = {};
  const assigned = [];
  const document = {
    body,
    querySelectorAll: (selector) => body.querySelectorAll(selector),
    addEventListener: (type, listener) => (listeners[type] = listeners[type] || []).push(listener),
  };
  const context = { document, location: { assign: (href) => assigned.push(href) } };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SCRIPT, context, { filename: 'cms_search_runtime.js' });
  const fire = (type, target, extra = {}) => {
    const event = { type, target, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...extra };
    (listeners[type] || []).forEach((listener) => listener(event));
    return event;
  };
  return { box, outside, fire, assigned };
}

const activeIndexes = (box) =>
  box.options.flatMap((option, index) => (option.classes.has('post-search__option--active') ? [index] : []));

test('ArrowDown and ArrowUp move the active option and wrap around', () => {
  const { box, fire } = load();

  const down = fire('keydown', box.input, { key: 'ArrowDown' });
  assert.equal(down.defaultPrevented, true);
  assert.deepEqual(activeIndexes(box), [0]);
  assert.equal(box.options[0].getAttribute('aria-selected'), 'true');
  assert.equal(box.input.getAttribute('aria-activedescendant'), 'lb-option-0');

  fire('keydown', box.input, { key: 'ArrowDown' });
  fire('keydown', box.input, { key: 'ArrowDown' });
  assert.deepEqual(activeIndexes(box), [0]);

  fire('keydown', box.input, { key: 'ArrowUp' });
  assert.deepEqual(activeIndexes(box), [1]);
  assert.equal(box.options[0].getAttribute('aria-selected'), 'false');
});

test('Enter on an active option opens that result instead of submitting', () => {
  const { box, fire, assigned } = load();
  fire('keydown', box.input, { key: 'ArrowDown' });
  fire('keydown', box.input, { key: 'ArrowDown' });

  const submit = fire('submit', box.form);

  assert.equal(submit.defaultPrevented, true);
  assert.deepEqual(assigned, ['/beta']);
});

test('Enter without an active option submits the GET form as usual', () => {
  const { box, fire, assigned } = load();

  const submit = fire('submit', box.form);

  assert.equal(submit.defaultPrevented, false);
  assert.deepEqual(assigned, []);
});

test('a mousedown on an option opens it', () => {
  const { box, fire, assigned } = load();

  const mousedown = fire('mousedown', box.options[1]);

  assert.equal(mousedown.defaultPrevented, true);
  assert.deepEqual(assigned, ['/beta']);
});

test('Escape closes the dropdown back to the empty placeholder', () => {
  const { box, fire } = load();

  fire('keydown', box.input, { key: 'Escape' });

  assert.equal(box.dropdown.hidden, true);
  assert.equal(box.dropdown.getAttribute('data-testid'), null);
  assert.equal(box.dropdown.children.length, 0);
  assert.equal(box.input.getAttribute('aria-expanded'), 'false');
});

test('a click outside the search box closes it, a click inside does not', () => {
  const { box, outside, fire } = load();

  fire('click', box.input);
  assert.equal(box.dropdown.hidden, false);

  fire('click', outside);
  assert.equal(box.dropdown.hidden, true);
});

test('hovering an option makes it the active one', () => {
  const { box, fire } = load();

  fire('mouseover', box.options[1]);

  assert.deepEqual(activeIndexes(box), [1]);
});

test('after htmx swaps the dropdown the input reports whether it is expanded', () => {
  const open = load();
  open.fire('htmx:afterSwap', open.box.input);
  assert.equal(open.box.input.getAttribute('aria-expanded'), 'true');

  const closed = load(searchBox([]));
  closed.fire('htmx:afterSwap', closed.box.input);
  assert.equal(closed.box.input.getAttribute('aria-expanded'), 'false');
});

test('arrow keys on a closed dropdown do nothing', () => {
  const { box, fire } = load(searchBox([]));

  const down = fire('keydown', box.input, { key: 'ArrowDown' });

  assert.equal(down.defaultPrevented, false);
});
