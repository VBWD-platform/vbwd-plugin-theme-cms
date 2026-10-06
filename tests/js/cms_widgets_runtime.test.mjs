// S152-06a — theme_cms widget runtime (burger, sub-menus, slideshow), run with
// `node --test 'plugins/theme_cms/tests/js/*.test.mjs'`. The script runs in a vm
// with a tiny class-selector DOM, so its delegated wiring is exercised as well.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const SCRIPT = readFileSync(
  fileURLToPath(new URL('../../theme_cms/templates/cms/partials/cms_widgets_runtime.js', import.meta.url)),
  'utf8',
);

function matchesSimple(element, selector) {
  return element.classes && element.classes.has(selector.replace(/^\./, ''));
}

function matches(element, selector) {
  return selector.split(',').some((part) => {
    const steps = part.trim().split(/\s*>\s*/);
    let current = element;
    for (let index = steps.length - 1; index >= 0; index -= 1) {
      if (!current || !matchesSimple(current, steps[index])) return false;
      current = current.parent;
    }
    return true;
  });
}

function el(classNames, children = []) {
  const element = {
    classes: new Set(classNames.split(' ').filter(Boolean)),
    children,
    parent: null,
    classList: {
      contains: (name) => element.classes.has(name),
      remove: (name) => element.classes.delete(name),
      toggle(name, force) {
        const on = force === undefined ? !element.classes.has(name) : force;
        if (on) element.classes.add(name); else element.classes.delete(name);
        return on;
      },
    },
    closest(selector) {
      for (let current = element; current; current = current.parent) {
        if (matches(current, selector)) return current;
      }
      return null;
    },
    querySelectorAll(selector) {
      const found = [];
      const walk = (node) => node.children.forEach((child) => {
        if (matches(child, selector)) found.push(child);
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

function page() {
  const burger = el('cms-burger');
  const overlay = el('cms-menu-overlay');
  const parentLink = el('cms-menu__link', [el('cms-menu__arrow')]);
  const sub = el('cms-menu__sub', [el('cms-menu__item', [el('cms-menu__link')])]);
  const parentItem = el('cms-menu__item cms-menu__item--has-children', [parentLink, sub]);
  const menuList = el('cms-menu', [parentItem]);
  const menu = el('cms-widget cms-widget--menu', [burger, overlay, menuList]);
  const slides = [el('cms-slide cms-slide--active'), el('cms-slide'), el('cms-slide')];
  const prev = el('cms-slide__prev');
  const next = el('cms-slide__next');
  const slideshow = el('cms-slideshow', [...slides, prev, next]);
  const outside = el('outside');
  const body = el('body', [menu, slideshow, outside]);
  const listeners = {};
  const document = {
    querySelectorAll: (selector) => body.querySelectorAll(selector),
    addEventListener: (type, listener) => { (listeners[type] = listeners[type] || []).push(listener); },
  };
  const fire = (type, target, extra = {}) => {
    const event = { type, target, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...extra };
    (listeners[type] || []).forEach((listener) => listener(event));
    return event;
  };
  vm.runInNewContext(SCRIPT, { window: { document } });
  return { burger, overlay, menuList, parentLink, sub, slides, prev, next, outside, fire };
}

const activeIndex = (slides) => slides.findIndex((slide) => slide.classList.contains('cms-slide--active'));

test('the burger toggles the drawer, overlay and burger state', () => {
  const dom = page();
  dom.fire('click', dom.burger);
  assert.ok(dom.menuList.classList.contains('cms-menu--open'));
  assert.ok(dom.overlay.classList.contains('cms-menu-overlay--open'));
  assert.ok(dom.burger.classList.contains('cms-burger--open'));
  dom.fire('click', dom.burger);
  assert.ok(!dom.menuList.classList.contains('cms-menu--open'));
});

test('the overlay, Escape and an outside click close the menu', () => {
  for (const close of ['overlay', 'escape', 'outside']) {
    const dom = page();
    dom.fire('click', dom.burger);
    if (close === 'overlay') dom.fire('click', dom.overlay);
    if (close === 'escape') dom.fire('keydown', dom.outside, { key: 'Escape' });
    if (close === 'outside') dom.fire('click', dom.outside);
    assert.ok(!dom.menuList.classList.contains('cms-menu--open'), close);
  }
});

test('a parent link toggles its sub-menu and never navigates', () => {
  const dom = page();
  const event = dom.fire('click', dom.parentLink);
  assert.ok(event.defaultPrevented);
  assert.ok(dom.sub.classList.contains('cms-menu__sub--open'));
  dom.fire('click', dom.outside);
  assert.ok(!dom.sub.classList.contains('cms-menu__sub--open'));
});

test('slideshow next/prev rotate the active slide with wrap-around', () => {
  const dom = page();
  dom.fire('click', dom.next);
  assert.equal(activeIndex(dom.slides), 1);
  dom.fire('click', dom.prev);
  dom.fire('click', dom.prev);
  assert.equal(activeIndex(dom.slides), 2);
});
