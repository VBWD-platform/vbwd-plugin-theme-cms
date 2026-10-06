/* theme_cms CookieConsent runtime (S152-06b): the client half of the themed
   CookieConsent widget. Same localStorage record as fe-user consent/useConsent.ts
   (key vbwd_cookie_consent, {version, decidedAt, method, categories}) and the same
   Google Consent Mode v2 signals as consent/consentMode.ts. Delegated on the
   document; re-applied after a /regions swap. */
(function (root) {
  'use strict';
  var STORAGE_KEY = 'vbwd_cookie_consent';
  var OPEN_CONSENT_EVENT = 'vbwd:open-cookie-consent';
  var CONSENT_CHANGED_EVENT = 'vbwd:consent-changed';
  var REGIONS_SWAPPED_EVENT = 'vbwd:regions-swapped';
  var OPTIONAL_CATEGORIES = ['preferences', 'statistics', 'marketing'];
  var BACKDROP_SELECTOR = '.cookie-consent__backdrop';
  var SETTINGS_SELECTOR = '.cookie-consent__settings';
  var LAYER_ATTRIBUTE = 'data-cookie-consent-layer';
  var LAYER_TITLES = { summary: 'cookie-consent-title', customize: 'cookie-consent-customize-title' };
  var DEFAULT_VERSION = 1;
  var state = { reopened: false };

  function categoriesWith(optionalValue) {
    return { necessary: true, preferences: optionalValue, statistics: optionalValue, marketing: optionalValue };
  }

  function loadRecord(storage) {
    try {
      var parsed = JSON.parse(storage.getItem(STORAGE_KEY) || 'null');
      return parsed && typeof parsed.version === 'number' && parsed.categories ? parsed : null;
    } catch (parseError) {
      return null;
    }
  }

  function grant(on) { return on ? 'granted' : 'denied'; }

  function pushConsent(window, command, signals) {
    window.dataLayer = window.dataLayer || [];
    if (typeof window.gtag === 'function') window.gtag('consent', command, signals);
    else window.dataLayer.push(['consent', command, signals]);
  }

  function emitConsentDefault(window) {
    pushConsent(window, 'default', {
      ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied',
      analytics_storage: 'denied', functionality_storage: 'denied',
      personalization_storage: 'denied', security_storage: 'granted'
    });
  }

  function emitConsentUpdate(window, categories) {
    pushConsent(window, 'update', {
      analytics_storage: grant(categories.statistics),
      ad_storage: grant(categories.marketing),
      ad_user_data: grant(categories.marketing),
      ad_personalization: grant(categories.marketing),
      functionality_storage: grant(categories.preferences),
      personalization_storage: grant(categories.preferences),
      security_storage: 'granted'
    });
    window.dispatchEvent(new window.CustomEvent(CONSENT_CHANGED_EVENT, { detail: { categories: categories } }));
  }

  function consentVersion(backdrop) {
    var version = Number(backdrop.getAttribute('data-consent-version'));
    return version > 0 ? version : DEFAULT_VERSION;
  }

  function isDecided(storage, backdrop) {
    var record = loadRecord(storage);
    return Boolean(record) && record.version >= consentVersion(backdrop);
  }

  function showLayer(backdrop, layer) {
    backdrop.querySelectorAll('[' + LAYER_ATTRIBUTE + ']').forEach(function (element) {
      element.hidden = element.getAttribute(LAYER_ATTRIBUTE) !== layer;
    });
    backdrop.querySelector('.cookie-consent').setAttribute('aria-labelledby', LAYER_TITLES[layer]);
  }

  function apply(document, storage) {
    var anyDecided = false;
    var anyOpen = false;
    document.querySelectorAll(BACKDROP_SELECTOR).forEach(function (backdrop) {
      var decided = isDecided(storage, backdrop);
      var open = !decided || state.reopened;
      anyDecided = anyDecided || decided;
      anyOpen = anyOpen || open;
      var wasHidden = backdrop.hidden;
      backdrop.hidden = !open;
      if (open && wasHidden) {
        showLayer(backdrop, 'summary');
        var firstButton = backdrop.querySelector('.cookie-consent__btn');
        if (firstButton) firstButton.focus();
      }
    });
    document.querySelectorAll(SETTINGS_SELECTOR).forEach(function (button) {
      button.hidden = !(anyDecided && !anyOpen);
    });
  }

  function persist(window, storage, backdrop, method, categories) {
    var record = {
      version: consentVersion(backdrop),
      decidedAt: new window.Date().toISOString(),
      method: method,
      // Every category set this runtime builds keeps `necessary` on (categoriesWith).
      categories: categories
    };
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(record));
    } catch (storageError) {
      /* storage unavailable: the decision still applies to this page */
    }
    state.reopened = false;
    emitConsentUpdate(window, record.categories);
  }

  function seedToggles(storage, backdrop) {
    var record = loadRecord(storage);
    var categories = record ? record.categories : categoriesWith(false);
    backdrop.querySelectorAll('.cookie-consent__toggle').forEach(function (toggle) {
      var category = toggle.getAttribute('data-cookie-category');
      if (category !== 'necessary') toggle.checked = categories[category] === true;
    });
  }

  function selectedCategories(backdrop) {
    var selected = categoriesWith(false);
    backdrop.querySelectorAll('.cookie-consent__toggle').forEach(function (toggle) {
      var category = toggle.getAttribute('data-cookie-category');
      if (OPTIONAL_CATEGORIES.indexOf(category) !== -1) selected[category] = toggle.checked === true;
    });
    return selected;
  }

  function handleAction(window, document, storage, target) {
    if (target.closest(SETTINGS_SELECTOR)) {
      state.reopened = true;
      apply(document, storage);
      return;
    }
    var backdrop = target.closest(BACKDROP_SELECTOR);
    var button = backdrop ? target.closest('.cookie-consent__btn') : null;
    var action = button ? button.getAttribute('data-testid') : null;
    if (action === 'cookie-customize') {
      seedToggles(storage, backdrop);
      showLayer(backdrop, 'customize');
      return;
    }
    if (action === 'cookie-accept-all') persist(window, storage, backdrop, 'accept_all', categoriesWith(true));
    else if (action === 'cookie-reject-all') persist(window, storage, backdrop, 'reject_all', categoriesWith(false));
    else if (action === 'cookie-save') persist(window, storage, backdrop, 'custom', selectedCategories(backdrop));
    else return;
    apply(document, storage);
  }

  function install(window, document, storage) {
    var backdrops = document.querySelectorAll(BACKDROP_SELECTOR);
    if (!backdrops.length) return;
    emitConsentDefault(window);
    var record = loadRecord(storage);
    if (record && isDecided(storage, backdrops[0])) emitConsentUpdate(window, record.categories);
    apply(document, storage);
    document.addEventListener('click', function (event) {
      handleAction(window, document, storage, event.target);
    });
    document.addEventListener('keydown', function (event) {
      // A decision is required: Escape never dismisses the dialog.
      if (event.key === 'Escape' && event.target.closest('.cookie-consent')) event.preventDefault();
    });
    document.addEventListener(REGIONS_SWAPPED_EVENT, function () { apply(document, storage); });
    window.addEventListener(OPEN_CONSENT_EVENT, function () {
      state.reopened = true;
      apply(document, storage);
    });
  }

  root.VbwdThemeCookieConsent = Object.freeze({ STORAGE_KEY: STORAGE_KEY, loadRecord: loadRecord });
  if (root.document) install(root, root.document, root.localStorage);
})(typeof window !== 'undefined' ? window : globalThis);
