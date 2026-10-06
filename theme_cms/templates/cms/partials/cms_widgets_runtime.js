/* theme_cms widget runtime (S152-06a): burger menu, sub-menus and slideshow
   controls of server-rendered CMS widgets. Delegated on the document, so it keeps
   working after /regions swaps an area. Same classes the SPA toggles. */
(function (root) {
  'use strict';
  function toggle(element, className, force) {
    if (element) element.classList.toggle(className, force);
  }
  function setMenuOpen(menu, open) {
    toggle(menu.querySelector('.cms-burger'), 'cms-burger--open', open);
    toggle(menu.querySelector('.cms-menu-overlay'), 'cms-menu-overlay--open', open);
    toggle(menu.querySelector('.cms-menu'), 'cms-menu--open', open);
  }
  function closeAll(document) {
    document.querySelectorAll('.cms-widget--menu').forEach(function (menu) {
      setMenuOpen(menu, false);
      menu.querySelectorAll('.cms-menu__sub--open').forEach(function (sub) {
        sub.classList.remove('cms-menu__sub--open');
      });
    });
  }
  function showSlide(slideshow, step) {
    var slides = slideshow.querySelectorAll('.cms-slide');
    var active = 0;
    slides.forEach(function (slide, index) {
      if (slide.classList.contains('cms-slide--active')) active = index;
    });
    var next = (active + step + slides.length) % slides.length;
    slides.forEach(function (slide, index) {
      slide.classList.toggle('cms-slide--active', index === next);
    });
  }
  function handleClick(event, document) {
    var target = event.target;
    var menu = target.closest('.cms-widget--menu');
    if (!menu) {
      closeAll(document);
    } else if (target.closest('.cms-burger')) {
      setMenuOpen(menu, !menu.querySelector('.cms-menu').classList.contains('cms-menu--open'));
    } else if (target.closest('.cms-menu-overlay')) {
      setMenuOpen(menu, false);
    } else {
      var parentLink = target.closest('.cms-menu__item--has-children > .cms-menu__link');
      if (parentLink) {
        event.preventDefault();
        var item = parentLink.closest('.cms-menu__item');
        toggle(item.querySelector('.cms-menu__sub'), 'cms-menu__sub--open');
        toggle(item.querySelector('.cms-menu__arrow'), 'cms-menu__arrow--open');
      }
    }
    var control = target.closest('.cms-slide__prev, .cms-slide__next');
    if (control) {
      showSlide(control.closest('.cms-slideshow'), control.classList.contains('cms-slide__prev') ? -1 : 1);
    }
  }
  function install(document) {
    document.addEventListener('click', function (event) { handleClick(event, document); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeAll(document);
    });
  }
  root.VbwdThemeCms = Object.freeze({ install: install, handleClick: handleClick, closeAll: closeAll });
  if (root.document) install(root.document);
})(typeof window !== 'undefined' ? window : globalThis);
