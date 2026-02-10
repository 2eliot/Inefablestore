document.addEventListener('DOMContentLoaded', () => {
  const siteHeader = document.querySelector('.site-header');
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

  // Lightweight session check to avoid 401s on public pages
  async function getSessionUser() {
    try {
      const res = await fetch('/auth/session');
      const data = await res.json();
      if (res.ok && data && data.ok && data.user) return data.user;
      return null;
    } catch (e) {
      return null;
    }
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
    const railMobile = document.getElementById('rail-mobile');
    const railGift = document.getElementById('rail-gift');
    const resetRails = () => {
      try { if (railMobile) { railMobile.scrollLeft = 0; railMobile.style.scrollBehavior = 'auto'; } } catch(_){}
      try { if (railGift) { railGift.scrollLeft = 0; railGift.style.scrollBehavior = 'auto'; } } catch(_){}
      // Next frame restore smooth scroll for future interactions
      requestAnimationFrame(() => {
        try { if (railMobile) railMobile.style.scrollBehavior = ''; } catch(_){}
        try { if (railGift) railGift.style.scrollBehavior = ''; } catch(_){}
      });
    };
    if (c === 'gift') {
      if (secGift) { secGift.hidden = false; secGift.style.display = ''; }
      if (secMobile) { secMobile.hidden = true; secMobile.style.display = 'none'; }
      if (secHero) { secHero.hidden = true; secHero.style.display = 'none'; }
      if (secBest) { secBest.hidden = true; secBest.style.display = 'none'; }
      document.body.classList.add('cat-filtered');
      const target = document.querySelector('#pkgs-gift');
      resetRails();
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (c === 'mobile') {
      if (secMobile) { secMobile.hidden = false; secMobile.style.display = ''; }
      if (secGift) { secGift.hidden = true; secGift.style.display = 'none'; }
      if (secHero) { secHero.hidden = true; secHero.style.display = 'none'; }
      if (secBest) { secBest.hidden = true; secBest.style.display = 'none'; }
      document.body.classList.add('cat-filtered');
      const target = document.querySelector('#pkgs-mobile');
      resetRails();
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      if (secMobile) { secMobile.hidden = false; secMobile.style.display = ''; }
      if (secGift) { secGift.hidden = false; secGift.style.display = ''; }
      if (secHero) { secHero.hidden = false; secHero.style.display = ''; }
      if (secBest) { secBest.hidden = false; secBest.style.display = ''; }
      document.body.classList.remove('cat-filtered');
      resetRails();
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
      const u = await getSessionUser();
      if (u && u.email) {
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
    // Click on menu items: if on homepage filter; otherwise redirect to index with anchor
    menu.addEventListener('click', (e) => {
      const a = e.target.closest('a.dd-item');
      if (!a) return;
      const href = a.getAttribute('href') || '';
      const cat = (a.getAttribute('data-cat') || '').toLowerCase();
      // Always filter by category when clicking
      e.preventDefault();
      if (cat === 'gift' || cat === 'mobile') {
        const onHome = !!(secMobile || secGift);
        const targetHash = cat === 'gift' ? '#pkgs-gift' : '#pkgs-mobile';
        if (!onHome) {
          window.location.href = '/' + targetHash;
          return;
        }
        showCategory(cat);
        // Update URL hash to aid bookmarking/back nav
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
      // If already logged in, go to /user (session check avoids 401)
      const u = await getSessionUser();
      if (u && u.email) {
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

  // Sticky header visual on scroll
  function updateHeaderOnScroll() {
    if (!siteHeader) return;
    const y = window.scrollY || document.documentElement.scrollTop || 0;
    if (y > 6) siteHeader.classList.add('scrolled');
    else siteHeader.classList.remove('scrolled');
  }
  updateHeaderOnScroll();
  window.addEventListener('scroll', updateHeaderOnScroll, { passive: true });

  // =====================
  // Header search
  // =====================
  const headerSearch = document.getElementById('header-search');
  const isHome = !!document.getElementById('rail-best');

  function norm(s) {
    return String(s || '').toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '');
  }

  function applySearchFilter(qRaw) {
    if (!isHome) return;
    const q = norm(qRaw).trim();
    const rails = ['#rail-best', '#rail-mobile', '#rail-gift']
      .map(sel => document.querySelector(sel))
      .filter(Boolean);
    rails.forEach(r => {
      r.querySelectorAll('.pkg-card').forEach(card => {
        const name = norm(card.querySelector('.pkg-name')?.textContent || card.textContent || '');
        const show = !q || name.includes(q);
        card.style.display = show ? '' : 'none';
      });
    });
  }

  if (headerSearch) {
    const headerSearchWrap = headerSearch.closest('.header-search');
    const isPhone = () => window.matchMedia('(max-width: 520px)').matches;

    // Suggestions dropdown
    let sg = null;
    let sgItems = []; // { id, name, href, category }
    let sgActiveIndex = -1;
    let sgCache = null;
    let sgCachePromise = null;

    function ensureSuggestEl() {
      if (!headerSearchWrap) return null;
      if (sg) return sg;
      sg = document.createElement('div');
      sg.className = 'search-suggest';
      sg.setAttribute('hidden', '');
      headerSearchWrap.appendChild(sg);
      return sg;
    }

    function collectFromDom() {
      if (!isHome) return [];
      const seen = new Set();
      const out = [];
      ['#rail-best', '#rail-mobile', '#rail-gift'].forEach(sel => {
        const r = document.querySelector(sel);
        if (!r) return;
        r.querySelectorAll('.pkg-card').forEach(card => {
          const name = (card.querySelector('.pkg-name')?.textContent || '').trim();
          const href = (card && card.onclick) ? '' : '';
          // home.js binds click to navigate using id; we can parse from dataset if present.
          // As fallback we build /store/package/<id> only if we can infer id.
          // But cards do not store id in DOM; so we keep name-only for filtering.
          if (!name) return;
          const key = norm(name);
          if (seen.has(key)) return;
          seen.add(key);
          out.push({ id: null, name, href: null, category: '' });
        });
      });
      return out;
    }

    async function fetchAllPackages() {
      if (sgCache) return sgCache;
      if (sgCachePromise) return sgCachePromise;
      sgCachePromise = (async () => {
        const res = [];
        try {
          const [m, g] = await Promise.all([
            fetch('/store/packages?category=mobile').then(r => r.json()).catch(() => ({})),
            fetch('/store/packages?category=gift').then(r => r.json()).catch(() => ({})),
          ]);
          (m && m.packages || []).forEach(p => res.push({ id: p.id, name: p.name, category: p.category || '', href: `/store/package/${p.id}` }));
          (g && g.packages || []).forEach(p => res.push({ id: p.id, name: p.name, category: p.category || '', href: `/store/package/${p.id}` }));
        } catch (_) {}
        // Dedup by normalized name
        const seen = new Set();
        const out = [];
        res.forEach(p => {
          const key = norm(p.name);
          if (!key || seen.has(key)) return;
          seen.add(key);
          out.push(p);
        });
        sgCache = out;
        return out;
      })();
      return sgCachePromise;
    }

    function scoreCandidate(q, cand) {
      const name = norm(cand.name);
      if (!q) return 0;
      if (name === q) return 100;
      if (name.startsWith(q)) return 80;
      if (name.includes(q)) return 60;
      // token overlap
      const qt = q.split(/\s+/).filter(Boolean);
      const nt = name.split(/\s+/).filter(Boolean);
      let hit = 0;
      qt.forEach(t => { if (t.length >= 2 && nt.some(x => x.startsWith(t))) hit++; });
      return hit ? 40 + hit * 5 : 0;
    }

    function renderSuggest(list, qRaw) {
      const el = ensureSuggestEl();
      if (!el) return;
      const q = norm(qRaw).trim();
      if (!q || !list || list.length === 0) {
        el.innerHTML = '';
        el.setAttribute('hidden', '');
        sgItems = [];
        sgActiveIndex = -1;
        return;
      }
      const ranked = list
        .map(x => ({ x, s: scoreCandidate(q, x) }))
        .filter(o => o.s > 0)
        .sort((a,b) => b.s - a.s)
        .slice(0, 6)
        .map(o => o.x);

      sgItems = ranked;
      sgActiveIndex = -1;
      el.innerHTML = '';
      ranked.forEach((it, idx) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'sg-item';
        const icon = document.createElement('div');
        icon.className = 'sg-icon';
        icon.textContent = (it.name || '?').trim().slice(0, 1).toUpperCase();
        const txt = document.createElement('div');
        txt.innerHTML = `<div class="sg-title"></div><div class="sg-sub"></div>`;
        txt.querySelector('.sg-title').textContent = it.name || '';
        const sub = it.category ? String(it.category) : 'Ver juego';
        txt.querySelector('.sg-sub').textContent = sub;
        b.appendChild(icon);
        b.appendChild(txt);
        b.addEventListener('click', () => {
          if (it.href) {
            window.location.href = it.href;
          } else {
            // On home without href: keep filtering
            headerSearch.value = it.name || '';
            applySearchFilter(it.name || '');
            el.setAttribute('hidden', '');
          }
        });
        el.appendChild(b);
      });
      if (ranked.length) el.removeAttribute('hidden');
      else el.setAttribute('hidden', '');
    }

    async function updateSuggest() {
      const q = (headerSearch.value || '').trim();
      if (!q) {
        const el = ensureSuggestEl();
        if (el) { el.innerHTML = ''; el.setAttribute('hidden', ''); }
        return;
      }
      if (isHome) {
        // home cards may load async; re-collect each time
        renderSuggest(collectFromDom(), q);
      } else {
        const all = await fetchAllPackages();
        renderSuggest(all, q);
      }
    }

    // Apply from URL (home only)
    try {
      const url = new URL(window.location.href);
      const q = url.searchParams.get('q') || '';
      if (q) {
        headerSearch.value = q;
        // Filter after home.js injected cards
        setTimeout(() => applySearchFilter(q), 0);
      }
    } catch (_) {}

    function openMobileSearch() {
      if (!headerSearchWrap) return;
      headerSearchWrap.classList.add('open');
      // Focus after layout
      setTimeout(() => {
        try { headerSearch.focus(); } catch (_) {}
      }, 0);
    }

    function closeMobileSearch() {
      if (!headerSearchWrap) return;
      headerSearchWrap.classList.remove('open');
    }

    // Tap on icon wrapper opens the dropdown on phone
    if (headerSearchWrap) {
      headerSearchWrap.addEventListener('click', (e) => {
        if (!isPhone()) return;
        // If it's closed, first tap opens and prevents typing/navigating side effects
        if (!headerSearchWrap.classList.contains('open')) {
          e.preventDefault();
          e.stopPropagation();
          openMobileSearch();
        }
      });
    }

    // Close on outside click (phone only)
    document.addEventListener('click', (e) => {
      if (!isPhone()) return;
      if (!headerSearchWrap) return;
      if (!headerSearchWrap.classList.contains('open')) return;
      if (headerSearchWrap.contains(e.target)) return;
      closeMobileSearch();
    });

    // Close suggestions on outside click
    document.addEventListener('click', (e) => {
      if (!headerSearchWrap) return;
      const el = ensureSuggestEl();
      if (!el || el.hasAttribute('hidden')) return;
      if (headerSearchWrap.contains(e.target)) return;
      el.setAttribute('hidden', '');
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      if (!headerSearchWrap) return;
      if (!headerSearchWrap.classList.contains('open')) return;
      closeMobileSearch();
    });

    headerSearch.addEventListener('input', () => {
      if (isHome) {
        applySearchFilter(headerSearch.value);
      }
      updateSuggest();
    });

    headerSearch.addEventListener('keydown', (e) => {
      // Arrow navigation for suggestions
      const el = ensureSuggestEl();
      const open = el && !el.hasAttribute('hidden');
      if (open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        e.preventDefault();
        const btns = Array.from(el.querySelectorAll('.sg-item'));
        if (!btns.length) return;
        if (e.key === 'ArrowDown') sgActiveIndex = Math.min(btns.length - 1, sgActiveIndex + 1);
        else sgActiveIndex = Math.max(0, sgActiveIndex - 1);
        btns.forEach((b, i) => b.classList.toggle('active', i === sgActiveIndex));
        return;
      }
      if (open && e.key === 'Enter' && sgActiveIndex >= 0) {
        e.preventDefault();
        const btns = Array.from(el.querySelectorAll('.sg-item'));
        const b = btns[sgActiveIndex];
        if (b) b.click();
        return;
      }
      if (open && e.key === 'Escape') {
        el.setAttribute('hidden', '');
        return;
      }

      if (e.key !== 'Enter') return;
      const q = (headerSearch.value || '').trim();
      if (!q) return;
      if (!isHome) {
        const url = new URL(window.location.href);
        window.location.href = '/?q=' + encodeURIComponent(q);
      } else {
        applySearchFilter(q);
        try { headerSearch.blur(); } catch (_) {}
      }
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
    const u = await getSessionUser();
    if (u && u.email) setUserLabel(u.email);
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
