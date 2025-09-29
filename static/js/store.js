document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.getElementById('overlay');
  const leftDrawer = document.getElementById('left-drawer');
  const btnHamburger = document.querySelector('.icon-btn.hamburger');
  const btnCloseLeft = document.querySelector('.close-left');
  const btnLogin = document.querySelector('.icon-btn.login');
  const authModal = document.getElementById('auth-modal');
  const authCard = authModal ? authModal.querySelector('.auth-card') : null;
  const btnAuthClose = authModal ? authModal.querySelector('.auth-close') : null;

  function openOverlay() {
    overlay && overlay.removeAttribute('hidden');
  }
  function closeOverlay() {
    overlay && overlay.setAttribute('hidden', '');
  }
  function openDrawer(drawer) {
    if (!drawer) return;
    drawer.removeAttribute('hidden');
    openOverlay();
  }
  function closeDrawer(drawer) {
    if (!drawer) return;
    drawer.setAttribute('hidden', '');
    closeOverlay();
  }
  function openAuthModal() {
    if (!authModal) return;
    authModal.removeAttribute('hidden');
    document.addEventListener('keydown', onEscForModal);
  }
  function closeAuthModal() {
    if (!authModal) return;
    authModal.setAttribute('hidden', '');
    document.removeEventListener('keydown', onEscForModal);
  }
  function onEscForModal(e) {
    if (e.key === 'Escape') closeAuthModal();
  }

  // =====================
  // Category filtering helpers (homepage)
  // =====================
  const secMobile = document.getElementById('pkgs-mobile');
  const secGift = document.getElementById('pkgs-gift');
  const secHero = document.getElementById('hero');
  const secBest = document.getElementById('best-sellers');
  function showCategory(cat) {
    const c = (cat || '').toLowerCase();
    if (!secMobile && !secGift) return; // not on homepage
    if (c === 'gift') {
      if (secGift) { secGift.hidden = false; secGift.style.display = ''; }
      if (secMobile) { secMobile.hidden = true; secMobile.style.display = 'none'; }
      if (secHero) { secHero.hidden = true; secHero.style.display = 'none'; }
      if (secBest) { secBest.hidden = true; secBest.style.display = 'none'; }
      document.body.classList.add('cat-filtered');
      const target = document.querySelector('#pkgs-gift');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (c === 'mobile') {
      if (secMobile) { secMobile.hidden = false; secMobile.style.display = ''; }
      if (secGift) { secGift.hidden = true; secGift.style.display = 'none'; }
      if (secHero) { secHero.hidden = true; secHero.style.display = 'none'; }
      if (secBest) { secBest.hidden = true; secBest.style.display = 'none'; }
      document.body.classList.add('cat-filtered');
      const target = document.querySelector('#pkgs-mobile');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      if (secMobile) { secMobile.hidden = false; secMobile.style.display = ''; }
      if (secGift) { secGift.hidden = false; secGift.style.display = ''; }
      if (secHero) { secHero.hidden = false; secHero.style.display = ''; }
      if (secBest) { secBest.hidden = false; secBest.style.display = ''; }
      document.body.classList.remove('cat-filtered');
    }
  }
  (function applyInitialCategoryFromUrl(){
    const hash = (location.hash || '').toLowerCase();
    const url = new URL(window.location.href);
    const qcat = (url.searchParams.get('cat') || '').toLowerCase();
    if (hash === '#pkgs-gift' || qcat === 'gift') showCategory('gift');
    else if (hash === '#pkgs-mobile' || qcat === 'mobile') showCategory('mobile');
  })();

  // Header user label
  const userLabel = document.getElementById('user-label');
  function setUserLabel(email) {
    if (!userLabel) return;
    if (email) {
      userLabel.textContent = email;
      userLabel.removeAttribute('hidden');
    } else {
      userLabel.textContent = '';
      userLabel.setAttribute('hidden', '');
    }
  }

  // Clicking on user label opens Profile tab or login modal
  if (userLabel) {
    userLabel.addEventListener('click', async () => {
      const data = await fetchAndFillProfile();
      if (data && data.ok && data.profile && data.profile.email) {
        window.location.href = '/user';
      } else {
        openAuthModal();
      }
    });
  }

  // Hamburger open/close
  if (btnHamburger) {
    btnHamburger.addEventListener('click', () => openDrawer(leftDrawer));
  }
  if (btnCloseLeft) {
    btnCloseLeft.addEventListener('click', () => closeDrawer(leftDrawer));
  }

  // Desktop categories dropdown
  (function wireCategoriesDropdown() {
    const dd = document.getElementById('dd-cats');
    const toggle = dd.querySelector('.dd-toggle');
    const menu = dd.querySelector('.dd-menu');
    if (!toggle || !menu) return;

    let open = false;
    let hideTimer = null;
    const show = () => { if (menu.hasAttribute('hidden')) menu.removeAttribute('hidden'); toggle.setAttribute('aria-expanded', 'true'); open = true; };
    const hide = () => { if (!menu.hasAttribute('hidden')) menu.setAttribute('hidden', ''); toggle.setAttribute('aria-expanded', 'false'); open = false; };
    const isDesktop = () => window.matchMedia('(min-width: 900px)').matches;

    // Hover open on desktop
    dd.addEventListener('mouseenter', () => {
      if (!isDesktop()) return;
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
      show();
    });
    dd.addEventListener('mouseleave', () => {
      if (!isDesktop()) return;
      if (hideTimer) clearTimeout(hideTimer);
      hideTimer = setTimeout(() => { hide(); hideTimer = null; }, 220);
    });
    // Keep open while hovering the menu panel itself
    menu.addEventListener('mouseenter', () => {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    });
    menu.addEventListener('mouseleave', () => {
      if (!isDesktop()) return;
      if (hideTimer) clearTimeout(hideTimer);
      hideTimer = setTimeout(() => { hide(); hideTimer = null; }, 220);
    });

    // Click toggle
    toggle.addEventListener('click', (e) => {
      e.preventDefault();
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
      if (open) hide(); else show();
    });
    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!open) return;
      if (!dd.contains(e.target)) hide();
    });
    // Close on Esc
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hide();
    });
    // Click on menu items: filter + smooth-scroll + update URL hash, then close
    menu.addEventListener('click', (e) => {
      const a = e.target.closest('a.dd-item');
      if (!a) return;
      const href = a.getAttribute('href') || '';
      const cat = (a.getAttribute('data-cat') || '').toLowerCase();
      // Always filter by category when clicking
      e.preventDefault();
      if (cat === 'gift' || cat === 'mobile') {
        showCategory(cat);
        // Update URL hash to aid bookmarking/back nav
        const targetHash = cat === 'gift' ? '#pkgs-gift' : '#pkgs-mobile';
        if (history && history.replaceState) {
          history.replaceState(null, '', targetHash);
        } else {
          location.hash = targetHash;
        }
      }
      if (href.startsWith('#')) {
        const target = document.querySelector(href);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      hide();
    });
  })();

  // Auth modal open/close
  if (btnLogin) {
    btnLogin.addEventListener('click', async () => {
      // If already logged in, go to /user
      const data = await fetchAndFillProfile();
      if (data && data.ok && data.profile && data.profile.email) {
        window.location.href = '/user';
        return;
      }
      // Otherwise open login modal
      openAuthModal();
    });
  }
  if (btnAuthClose) {
    btnAuthClose.addEventListener('click', () => closeAuthModal());
  }
  if (authModal) {
    authModal.addEventListener('click', (e) => {
      if (authCard && !authCard.contains(e.target)) closeAuthModal();
    });
  }

  // Close when clicking on overlay
  if (overlay) {
    overlay.addEventListener('click', () => {
      closeDrawer(leftDrawer);
    });
  }

  // Drawer: mobile categories
  (function wireDrawerCategories(){
    if (!leftDrawer) return;
    leftDrawer.addEventListener('click', (e) => {
      const btn = e.target.closest('.drawer-item[data-cat]');
      if (!btn) return;
      const cat = (btn.getAttribute('data-cat') || '').toLowerCase();
      if (cat === 'gift' || cat === 'mobile') {
        showCategory(cat);
        closeDrawer(leftDrawer);
        // Ensure URL shows the selected category anchor
        const targetHash = cat === 'gift' ? '#pkgs-gift' : '#pkgs-mobile';
        if (history && history.replaceState) history.replaceState(null, '', targetHash);
      }
    });
  })();

  // Auth tabs (inside modal)
  (function wireAuthModalTabs() {
    if (!authModal) return;
    const tabs = authModal.querySelectorAll('.tab-auth');
    const panels = authModal.querySelectorAll('.panel-auth');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        panels.forEach(p => { p.classList.remove('active'); p.setAttribute('hidden', ''); });
        const target = authModal.querySelector(tab.dataset.target);
        if (target) { target.classList.add('active'); target.removeAttribute('hidden'); }
      });
    });
  })();

  // Register submit in modal
  (function wireRegisterSubmitModal() {
    if (!authModal) return;
    const panel = authModal.querySelector('#md-register');
    if (!panel) return;
    const btn = panel.querySelector('.btn.primary');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const name = panel.querySelector('input[type="text"]')?.value.trim() || '';
      const email = panel.querySelector('input[type="email"]')?.value.trim() || '';
      const phone = panel.querySelector('input[type="tel"]')?.value.trim() || '';
      // last input is password
      const passInputs = panel.querySelectorAll('input[type="password"]');
      const password = passInputs.length ? passInputs[passInputs.length - 1].value : '';
      try {
        const res = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, phone, password })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          showAlert(panel, 'error', data.error || 'No se pudo registrar');
          return;
        }
        // Registro OK: ir al perfil
        window.location.href = '/user';
      } catch (e) {
        showAlert(panel, 'error', 'No se pudo registrar');
      }
    });
  })();

  // Try to load profile on page load to show user email if already logged in
  (async function initUserLabel() {
    const data = await fetchAndFillProfile();
    if (data && data.ok && data.profile && data.profile.email) {
      setUserLabel(data.profile.email);
    }
  })();

  // Helper: alerts
  function showAlert(panel, type, msg) {
    if (!panel) return;
    const el = panel.querySelector('.alert');
    if (!el) return;
    el.textContent = msg || '';
    el.className = 'alert ' + (type || '');
    el.removeAttribute('hidden');
  }
  function clearAlert(panel) {
    if (!panel) return;
    const el = panel.querySelector('.alert');
    if (!el) return;
    el.setAttribute('hidden', '');
    el.textContent = '';
  }

  // Fetch profile and fill modal fields; returns response JSON or null
  async function fetchAndFillProfile() {
    try {
      const res = await fetch('/auth/profile');
      const data = await res.json();
      if (!res.ok || !data.ok) {
        return null;
      }
      const panel = authModal && authModal.querySelector('#md-profile');
      if (panel) {
        const { name, email, phone } = data.profile || {};
        const n = panel.querySelector('#profile-name');
        const e = panel.querySelector('#profile-email');
        const p = panel.querySelector('#profile-phone');
        if (n) n.value = name || '';
        if (e) e.value = email || '';
        if (p) p.value = phone || '';
        clearAlert(panel);
      }
      return data;
    } catch (e) {
      return null;
    }
  }

  // Wire save profile button in modal
  function wireSaveProfile() {
    if (!authModal) return;
    const panel = authModal.querySelector('#md-profile');
    if (!panel) return;
    const btn = panel.querySelector('#btn-save-profile');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const name = panel.querySelector('#profile-name')?.value.trim() || '';
      const email = panel.querySelector('#profile-email')?.value.trim() || '';
      const phone = panel.querySelector('#profile-phone')?.value.trim() || '';
      try {
        const res = await fetch('/auth/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, phone })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          showAlert(panel, 'error', data.error || 'No se pudo guardar');
          return;
        }
        showAlert(panel, 'success', 'Perfil guardado');
      } catch (e) {
        showAlert(panel, 'error', 'No se pudo guardar');
      }
    });
  }

  // Helper: switch to a given tab id within modal
  function switchToPanel(panelId) {
    if (!authModal) return;
    const tabs = authModal.querySelectorAll('.tab-auth');
    const panels = authModal.querySelectorAll('.panel-auth');
    panels.forEach(p => { p.classList.remove('active'); p.setAttribute('hidden', ''); });
    const target = authModal.querySelector(panelId);
    if (target) { target.classList.add('active'); target.removeAttribute('hidden'); }
    tabs.forEach(t => {
      t.classList.toggle('active', t.dataset.target === panelId);
    });
  }

  // Password toggles (login + register)
  (function wirePasswordToggles() {
    if (!authModal) return;
    authModal.querySelectorAll('.password-field .icon-eye').forEach(btn => {
      btn.addEventListener('click', () => {
        const input = btn.closest('.password-field').querySelector('input[type="password"], input[type="text"]');
        if (!input) return;
        if (input.type === 'password') { input.type = 'text'; } else { input.type = 'password'; }
      });
    });
  })();

  // Login submit in modal
  (function wireLoginSubmitModal() {
    if (!authModal) return;
    const panel = authModal.querySelector('#md-login');
    if (!panel) return;
    const btn = panel.querySelector('.btn.primary');
    const emailInput = panel.querySelector('input[type="email"]');
    const passInput = panel.querySelector('input[type="password"]');
    if (btn && emailInput && passInput) {
      btn.addEventListener('click', async () => {
        const email = emailInput.value.trim();
        const password = passInput.value;
        try {
          const res = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
          });
          const data = await res.json();
          if (!res.ok || !data.ok) {
            alert(data.error || 'Error al iniciar sesión');
            return;
          }
          // Login OK: go to /user
          window.location.href = '/user';
        } catch (e) {
          showAlert(panel, 'error', 'No se pudo iniciar sesión');
        }
      });
    }
  })();
});
