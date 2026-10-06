/* theme_cms quick-search runtime (S152-06b): the keyboard and mouse behaviour of
   the htmx quick-search dropdown, as PostSearch.vue has it. Arrow keys wrap through
   the options, Escape / a click outside close the dropdown, Enter on an active row
   or a mousedown opens it; Enter without an active row submits the GET form.
   Delegated on the document, so it survives htmx and /regions swaps. */
(function (root) {
  'use strict';
  var BOX_SELECTOR = '.post-search';
  var INPUT_SELECTOR = '.post-search__input';
  var DROPDOWN_SELECTOR = '.post-search__dropdown';
  var OPTION_SELECTOR = '.post-search__option';
  var ACTIVE_CLASS = 'post-search__option--active';
  var OPEN_MARKER = 'data-testid';
  var OPEN_MARKER_VALUE = 'post-search-dropdown';

  function partsOf(element) {
    var box = element.closest(BOX_SELECTOR);
    if (!box) return null;
    var dropdown = box.querySelector(DROPDOWN_SELECTOR);
    return { input: box.querySelector(INPUT_SELECTOR), dropdown: dropdown };
  }

  function isOpen(dropdown) {
    return Boolean(dropdown) && dropdown.getAttribute(OPEN_MARKER) === OPEN_MARKER_VALUE;
  }

  function options(dropdown) {
    return isOpen(dropdown) ? dropdown.querySelectorAll(OPTION_SELECTOR) : [];
  }

  function activeIndex(dropdown) {
    var found = -1;
    options(dropdown).forEach(function (option, index) {
      if (option.classList.contains(ACTIVE_CLASS)) found = index;
    });
    return found;
  }

  function setActive(parts, index) {
    options(parts.dropdown).forEach(function (option, optionIndex) {
      option.classList.toggle(ACTIVE_CLASS, optionIndex === index);
      option.setAttribute('aria-selected', optionIndex === index ? 'true' : 'false');
      if (optionIndex === index) parts.input.setAttribute('aria-activedescendant', option.getAttribute('id'));
    });
  }

  function close(parts) {
    if (!parts.dropdown) return;
    parts.dropdown.replaceChildren();
    parts.dropdown.removeAttribute(OPEN_MARKER);
    parts.dropdown.hidden = true;
    parts.input.setAttribute('aria-expanded', 'false');
    parts.input.removeAttribute('aria-activedescendant');
  }

  function syncExpanded(document) {
    document.querySelectorAll(BOX_SELECTOR).forEach(function (box) {
      var parts = partsOf(box);
      if (parts && parts.input) parts.input.setAttribute('aria-expanded', isOpen(parts.dropdown) ? 'true' : 'false');
    });
  }

  function handleKeydown(event) {
    if (!event.target.closest(INPUT_SELECTOR)) return;
    var parts = partsOf(event.target);
    var count = options(parts.dropdown).length;
    if (event.key === 'Escape') {
      close(parts);
    } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && count > 0) {
      event.preventDefault();
      var step = event.key === 'ArrowDown' ? 1 : -1;
      setActive(parts, (activeIndex(parts.dropdown) + step + count) % count);
    }
  }

  function handleSubmit(event, location) {
    var parts = partsOf(event.target);
    var index = parts ? activeIndex(parts.dropdown) : -1;
    if (index >= 0) {
      event.preventDefault();
      location.assign(options(parts.dropdown)[index].getAttribute('data-href'));
    }
  }

  function install(document, location) {
    document.addEventListener('keydown', handleKeydown);
    document.addEventListener('submit', function (event) { handleSubmit(event, location); });
    document.addEventListener('mousedown', function (event) {
      var option = event.target.closest(OPTION_SELECTOR);
      if (option) {
        event.preventDefault();
        location.assign(option.getAttribute('data-href'));
      }
    });
    document.addEventListener('mouseover', function (event) {
      var option = event.target.closest(OPTION_SELECTOR);
      if (option) {
        var parts = partsOf(option);
        var index = -1;
        options(parts.dropdown).forEach(function (candidate, candidateIndex) {
          if (candidate === option) index = candidateIndex;
        });
        setActive(parts, index);
      }
    });
    document.addEventListener('click', function (event) {
      if (event.target.closest(BOX_SELECTOR)) return;
      document.querySelectorAll(BOX_SELECTOR).forEach(function (box) {
        var parts = partsOf(box);
        if (isOpen(parts.dropdown)) close(parts);
      });
    });
    document.addEventListener('htmx:afterSwap', function () { syncExpanded(document); });
  }

  if (root.document) install(root.document, root.location);
})(typeof window !== 'undefined' ? window : globalThis);
