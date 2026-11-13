/**
 * APPLE-STYLE NAVIGATION & SCROLL CONTROLLER
 * Manages sticky frosted-glass header, active link scroll spy, and mobile drawer.
 */

window.RAG_NAVIGATION = {
  init: function () {
    this.initScrollSpy();
    this.initMobileMenu();
    this.initSmoothScroll();
  },

  initScrollSpy: function () {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-anchor');
    if (!sections.length || !navLinks.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            navLinks.forEach((link) => {
              if (link.getAttribute('href') === `#${id}`) {
                link.classList.add('text-brand', 'font-semibold');
                link.classList.remove('text-ink-secondary');
              } else {
                link.classList.remove('text-brand', 'font-semibold');
                link.classList.add('text-ink-secondary');
              }
            });
          }
        });
      },
      {
        rootMargin: '-20% 0px -70% 0px'
      }
    );

    sections.forEach((section) => observer.observe(section));
  },

  initMobileMenu: function () {
    const toggle = document.getElementById('mobile-menu-btn');
    const menu = document.getElementById('mobile-nav-menu');
    if (!toggle || !menu) return;

    toggle.addEventListener('click', () => {
      menu.classList.toggle('active');
    });

    menu.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        menu.classList.remove('active');
      });
    });
  },

  initSmoothScroll: function () {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          const headerOffset = 70;
          const elementPosition = targetEl.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });
        }
      });
    });
  }
};
