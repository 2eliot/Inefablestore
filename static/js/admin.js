document.addEventListener('DOMContentLoaded', () => {
  console.log('admin.js loaded v5');
  const tabs = document.querySelectorAll('#adminTabs .tab');
  const panels = document.querySelectorAll('.tab-panel');
  // Elements used across handlers (declare early)
  const btnUpload = document.getElementById('btn-upload');
  const btnRefresh = document.getElementById('btn-refresh');
  const fileInput = document.getElementById('file-input');
  const gallery = document.getElementById('gallery');
  const tpl = document.getElementById('image-card-tpl');
  // Client-side index to resolve IDs when dataset is missing
  const imgIndex = {
    byPath: new Map(), // '/static/uploads/..' => id
    byTitle: new Map(), // title => id
  };
  // Config elements
  const inputLogo = document.getElementById('logo-path');
  const btnSaveLogo = document.getElementById('btn-save-logo');
  const btnPasteLogo = document.getElementById('btn-paste-logo');
  const logoPreview = document.getElementById('logo-preview');
  // Mid banner config
  const inputMidBanner = document.getElementById('mid-banner-path');
  const btnSaveMidBanner = document.getElementById('btn-save-mid-banner');
  const btnPickMidBanner = document.getElementById('btn-pick-mid-banner');
  const midBannerPreview = document.getElementById('mid-banner-preview');
  // Hero config
  const hero1 = document.getElementById('hero-1');
  const hero2 = document.getElementById('hero-2');
  const hero3 = document.getElementById('hero-3');
  const btnPickHero1 = document.getElementById('btn-pick-hero-1');
  const btnPickHero2 = document.getElementById('btn-pick-hero-2');
  const btnPickHero3 = document.getElementById('btn-pick-hero-3');
  const btnSaveHero = document.getElementById('btn-save-hero');
  // Rate config
  const inputRate = document.getElementById('rate-bsd');
  const btnSaveRate = document.getElementById('btn-save-rate');
  // Payments config
  const pmBank = document.getElementById('pm-bank');
  const pmName = document.getElementById('pm-name');
  const pmPhone = document.getElementById('pm-phone');
  const pmId = document.getElementById('pm-id');
  const binEmail = document.getElementById('binance-email');
  const binPhone = document.getElementById('binance-phone');
  const btnSavePayments = document.getElementById('btn-save-payments');
  // Mail test elements
  const mailUser = document.getElementById('mail-user');
  const mailTo = document.getElementById('mail-to');
  const btnMailTest = document.getElementById('btn-mail-test');
  const btnMailSave = document.getElementById('btn-mail-save');
  const mailTestResult = document.getElementById('mail-test-result');
  const sessEmail = document.getElementById('sess-email');
  const sessRole = document.getElementById('sess-role');
  // Packages
  const pkgName = document.getElementById('pkg-name');
  const pkgImage = document.getElementById('pkg-image');
  const pkgCategory = document.getElementById('pkg-category');
  const pkgDesc = document.getElementById('pkg-desc');
  const pkgRequires = document.getElementById('pkg-requires-zone');
  const pkgRequiresZoneId = document.getElementById('pkg-requires-zone-id');
  const btnPickPkgImage = document.getElementById('btn-pick-pkg-image');
  const btnCreatePkg = document.getElementById('btn-create-pkg');
  const btnPackagesRefresh = document.getElementById('btn-packages-refresh');
  const pkgList = document.getElementById('pkg-list');
  // Orders elements
  const btnOrdersRefresh = document.getElementById('btn-orders-refresh');
  const ordersList = document.getElementById('orders-list');
  const btnOrdersWdRefresh = document.getElementById('btn-orders-wd-refresh');
  const ordersWdList = document.getElementById('orders-wd-list');
  // Affiliates elements
  const btnAffRefresh = document.getElementById('btn-aff-refresh');
  const affForm = document.getElementById('aff-form');
  const affName = document.getElementById('aff-name');
  const affEmail = document.getElementById('aff-email');
  const affCode = document.getElementById('aff-code');
  const affPass = document.getElementById('aff-pass');
  const affDisc = document.getElementById('aff-disc');
  const affScope = document.getElementById('aff-scope');
  const affPkgSelect = document.getElementById('aff-pkg-select');
  const affBalance = document.getElementById('aff-balance');
  const affActive = document.getElementById('aff-active');
  const btnAffCreate = document.getElementById('btn-aff-create');
  const affList = document.getElementById('aff-list');
  const btnAffWdRefresh = document.getElementById('btn-aff-wd-refresh');
  const affWdList = document.getElementById('aff-wd-list');
  // Logo picker modal elements
  const logoPicker = document.getElementById('logo-picker');
  const logoPickerGrid = document.getElementById('logo-picker-grid');
  const logoPickerTpl = document.getElementById('logo-picker-card-tpl');
  const btnPickLogo = document.getElementById('btn-pick-logo');
  const btnCloseModal = document.querySelector('#logo-picker .modal-close');
  // Mobile drawer elements
  const adminHamburger = document.getElementById('admin-hamburger');
  const adminDrawer = document.getElementById('admin-drawer');
  const adminDrawerTabs = document.getElementById('admin-drawer-tabs');

  // Clone sidebar tabs into mobile drawer
  function renderMobileTabs() {
    if (!adminDrawerTabs) return;
    adminDrawerTabs.innerHTML = '';
    const desktopTabs = document.querySelectorAll('#adminTabs .tab');
    desktopTabs.forEach(dt => {
      const btn = document.createElement('button');
      btn.className = 'tab';
      btn.textContent = dt.textContent;
      btn.dataset.target = dt.dataset.target;
      adminDrawerTabs.appendChild(btn);
    });
  }

  // Determine position to insert while dragging
  function getDragAfterElement(container, mouseY) {
    const els = [...container.querySelectorAll('.pkg-item:not(.dragging)')];
    let closest = { offset: Number.NEGATIVE_INFINITY, element: null };
    for (const el of els) {
      const box = el.getBoundingClientRect();
      const offset = mouseY - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        closest = { offset, element: el };
      }
    }
    return closest.element;
  }

  // Persist current order to backend
  async function savePkgOrder() {
    const ids = Array.from(document.querySelectorAll('#pkg-list .pkg-item'))
      .map(el => el && el.dataset && el.dataset.id)
      .filter(Boolean);
    if (!ids.length) return;
    const res = await fetch('/admin/packages/reorder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids })
    });
    if (!res.ok) {
      let msg = 'No se pudo guardar el orden';
      try { const d = await res.json(); msg = d.error || msg; } catch(_) {}
      throw new Error(msg);
    }
  }

  // =====================
  // Config: mid banner get/set
  // =====================
  async function fetchMidBanner() {
    try {
      const res = await fetch('/admin/config/mid_banner');
      const data = await res.json();
      if (inputMidBanner) {
        inputMidBanner.value = (data && data.mid_banner_path) || '';
        showMidBannerPreview();
      }
      window.fetchMidBanner = fetchMidBanner;
    } catch (_) { /* ignore */ }
  }

  function showMidBannerPreview() {
    if (!inputMidBanner || !midBannerPreview) return;
    const url = (inputMidBanner.value || '').trim();
    if (url) {
      midBannerPreview.src = url;
      midBannerPreview.style.display = 'inline-block';
    } else {
      midBannerPreview.style.display = 'none';
    }
  }

  async function saveMidBanner() {
    if (!inputMidBanner) return;
    const mid_banner_path = (inputMidBanner.value || '').trim();
    const res = await fetch('/admin/config/mid_banner', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mid_banner_path })
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar');
    }
    return res.json();
  }

  // Session: fetch and fill
  async function fetchSessionInfo() {
    try {
      const res = await fetch('/auth/session');
      const data = await res.json();
      const u = (data && data.user) || null;
      if (sessEmail) sessEmail.value = u && u.email ? u.email : 'No autenticado';
      if (sessRole) sessRole.value = u && u.role ? u.role : '-';
    } catch (_) {
      if (sessEmail) sessEmail.value = 'No autenticado';
      if (sessRole) sessRole.value = '-';
    }
  }

  // Mail: info + test
  async function fetchMailInfo() {
    try {
      const res = await fetch('/admin/config/mail');
      const data = await res.json();
      if (data && data.ok) {
        if (mailUser) mailUser.value = data.mail_user || '';
        if (mailTo && !(mailTo.value || '').trim()) mailTo.value = data.admin_notify_email || '';
      }
    } catch (_) { /* ignore */ }
  }
  async function saveMailDestination() {
    try {
      const email = mailTo ? (mailTo.value || '').trim() : '';
      if (!email) throw new Error('Ingrese un correo destino');
      const res = await fetch('/admin/config/mail', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ admin_notify_email: email }) });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo guardar');
      if (mailTestResult) { mailTestResult.style.color = '#86efac'; mailTestResult.textContent = `Destino guardado: ${data.admin_notify_email}`; }
    } catch (e) {
      if (mailTestResult) { mailTestResult.style.color = '#fca5a5'; mailTestResult.textContent = e.message || 'Error'; }
    }
  }
  async function sendMailTest() {
    try {
      if (mailTestResult) { mailTestResult.style.color = '#94a3b8'; mailTestResult.textContent = 'Enviando...'; }
      const to = mailTo ? (mailTo.value || '').trim() : '';
      const subject = (document.getElementById('mail-subject')?.value || '').trim();
      const body = (document.getElementById('mail-body')?.value || '').trim();
      if (!to) throw new Error('Ingrese un correo de destino');
      const res = await fetch('/admin/config/mail/test', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ to, subject, body }) });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Fallo al enviar');
      if (mailTestResult) { mailTestResult.style.color = '#86efac'; mailTestResult.textContent = `Enviado a ${data.to}`; }
    } catch (e) {
      if (mailTestResult) { mailTestResult.style.color = '#fca5a5'; mailTestResult.textContent = e.message || 'Error'; }
    }
  }

  async function fetchAffWithdrawalsForOrders() {
    if (!ordersWdList) return;
    try {
      const res = await fetch('/admin/affiliate/withdrawals');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar retiros');
      renderAffWithdrawalsInOrders(data.items || []);
    } catch (e) {
      ordersWdList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
    }
  }

  function renderAffWithdrawalsInOrders(items) {
    if (!ordersWdList) return;
    ordersWdList.innerHTML = '';
    if (!items || items.length === 0) {
      ordersWdList.innerHTML = '<div class="empty-state"><h3>Sin solicitudes</h3><p>Cuando los afiliados pidan retiro aparecerÃ¡n aquÃ­.</p></div>';
      return;
    }
    const fmtUSD = (n) => {
      try { return Number(n||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); } catch(_) { return `$${n}`; }
    };
    items.forEach(r => {
      const tile = document.createElement('div');
      tile.className = 'order-tile';
      const when = new Date(r.created_at).toLocaleString();
      const statusIcon = r.status === 'approved' ? 'OK' : r.status === 'rejected' ? 'X' : '...';
      const statusClass = r.status === 'approved' ? 'ok' : r.status === 'rejected' ? 'rej' : 'pend';
      const payoutLine = (r.method === 'pm')
        ? `Pago MÃ³vil: ${r.pm_bank || ''} Â· ${r.pm_name || ''} Â· ${r.pm_phone || ''} Â· ${r.pm_id || ''}`
        : `Binance: ${r.binance_email || ''} Â· ${r.binance_phone || ''}`;
      tile.innerHTML = `
        <div class="row-head">
          <div>
            <div class="ref">RETIRO <span class="state ${statusClass}">${statusIcon}</span></div>
            <div class="sub">${r.affiliate_name || '#'}</div>
          </div>
          <div class="box-right">
            <div class="metric usd"><span>${fmtUSD(r.amount_usd)}</span></div>
          </div>
        </div>
        <div class="row-metrics">
          <div class="metric diam"><span>${r.method.toUpperCase()}</span></div>
          <div class="metric usd"><span>${fmtUSD(r.amount_usd)}</span></div>
        </div>
        <div class="row-foot">
          <div>${when}</div>
          <div class="customer">${payoutLine}</div>
        </div>
        <div class="row-actions">
          ${r.status === 'pending' ? `<button class="btn btn-wd-approve" data-id="${r.id}">Aprobar</button>
          <button class="btn btn-wd-reject" data-id="${r.id}">Rechazar</button>` : ''}
        </div>
      `;
      ordersWdList.appendChild(tile);
    });
  }

  {
  const _ordersWdList = document.getElementById('orders-wd-list');
  if (_ordersWdList) {
    _ordersWdList.addEventListener('click', async (e) => {
      const app = e.target.closest('.btn-wd-approve');
      const rej = e.target.closest('.btn-wd-reject');
      if (app || rej) {
        const id = (app || rej).getAttribute('data-id');
        try {
          (app || rej).disabled = true;
          const res = await fetch(`/admin/affiliate/withdrawals/${id}/status`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: app ? 'approved' : 'rejected' })
          });
          if (!res.ok) throw new Error('No se pudo actualizar');
          await fetchAffWithdrawalsForOrders();
}catch (err) {
          toast(err.message || 'Error');
        } finally {
          (app || rej).disabled = false;
        }
      }
    });
  }

  // =====================
  // Affiliates Withdrawals moderation
  // =====================
  async function fetchAffWithdrawals() {
    if (!affWdList) return;
    try {
      const res = await fetch('/admin/affiliate/withdrawals');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar retiros');
      renderAffWithdrawals(data.items || []);
    } catch (e) {
      affWdList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
    }
  }

  function renderAffWithdrawals(items) {
    if (!affWdList) return;
    affWdList.innerHTML = '';
    if (!items || items.length === 0) {
      affWdList.innerHTML = '<div class="empty-state"><h3>Sin solicitudes</h3><p>Cuando los afiliados pidan retiro aparecerÃ¡n aquÃ­.</p></div>';
      return;
    }
    const fmtUSD = (n) => {
      try { return Number(n||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); } catch(_) { return `$${n}`; }
    };
    items.forEach(r => {
      const tile = document.createElement('div');
      tile.className = 'order-tile';
      const when = new Date(r.created_at).toLocaleString();
      const statusIcon = r.status === 'approved' ? 'OK' : r.status === 'rejected' ? 'X' : '...';
      const statusClass = r.status === 'approved' ? 'ok' : r.status === 'rejected' ? 'rej' : 'pend';
      const payoutLine = (r.method === 'pm')
        ? `Pago MÃ³vil: ${r.pm_bank || ''} Â· ${r.pm_name || ''} Â· ${r.pm_phone || ''} Â· ${r.pm_id || ''}`
        : `Binance: ${r.binance_email || ''} Â· ${r.binance_phone || ''}`;
      tile.innerHTML = `
        <div class="row-head">
          <div>
            <div class="ref">RETIRO <span class="state ${statusClass}">${statusIcon}</span></div>
            <div class="sub">${r.affiliate_name || '#'}</div>
          </div>
          <div class="box-right">
            <div class="metric usd"><span>${fmtUSD(r.amount_usd)}</span></div>
          </div>
        </div>
        <div class="row-metrics">
          <div class="metric diam"><span>${r.method.toUpperCase()}</span></div>
          <div class="metric usd"><span>${fmtUSD(r.amount_usd)}</span></div>
        </div>
        <div class="row-foot">
          <div>${when}</div>
          <div class="customer">${payoutLine}</div>
        </div>
        <div class="row-actions">
          ${r.status === 'pending' ? `<button class="btn btn-wd-approve" data-id="${r.id}">Aprobar</button>
          <button class="btn btn-wd-reject" data-id="${r.id}">Rechazar</button>` : ''}
        </div>
      `;
      affWdList.appendChild(tile);
    });
  }

  if (affWdList) {
    affWdList.addEventListener('click', async (e) => {
      const app = e.target.closest('.btn-wd-approve');
      const rej = e.target.closest('.btn-wd-reject');
      if (app || rej) {
        const id = (app || rej).getAttribute('data-id');
        try {
          (app || rej).disabled = true;
          const res = await fetch(`/admin/affiliate/withdrawals/${id}/status`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: app ? 'approved' : 'rejected' })
          });
          if (!res.ok) throw new Error('No se pudo actualizar');
          await fetchAffWithdrawals();
          await fetchAffiliates(); // refresh balances if approved
        } catch (err) {
          toast(err.message || 'Error');
        } finally {
          (app || rej).disabled = false;
        }
      }
    });
  }

  // =====================
  // Config: payments get/set
  // =====================
  async function fetchPayments() {
    try {
      const res = await fetch('/admin/config/payments');
      const data = await res.json();
      if (data && data.ok) {
        if (pmBank) pmBank.value = data.pm_bank || '';
        if (pmName) pmName.value = data.pm_name || '';
        if (pmPhone) pmPhone.value = data.pm_phone || '';
        if (pmId) pmId.value = data.pm_id || '';
        if (binEmail) binEmail.value = data.binance_email || '';
        if (binPhone) binPhone.value = data.binance_phone || '';
      }
window.fetchPayments = fetchPayments;
    } catch (_) { /* ignore */ }
  }

  async function savePayments() {
    const payload = {
      pm_bank: pmBank ? pmBank.value.trim() : '',
      pm_name: pmName ? pmName.value.trim() : '',
      pm_phone: pmPhone ? pmPhone.value.trim() : '',
      pm_id: pmId ? pmId.value.trim() : '',
      binance_email: binEmail ? binEmail.value.trim() : '',
      binance_phone: binPhone ? binPhone.value.trim() : ''
    };
    const res = await fetch('/admin/config/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar mÃ©todos de pago');
    }
  }

  // Save rate
  if (btnSaveRate) {
    btnSaveRate.addEventListener('click', async () => {
      try {
        btnSaveRate.disabled = true;
        await saveRate();
        toast('Tasa guardada');
      } catch (e) {
        toast(e.message || 'No se pudo guardar la tasa');
      } finally {
        btnSaveRate.disabled = false;
      }
    });
  }

  function openDrawer() {
    if (!adminDrawer) return;
    renderMobileTabs();
    adminDrawer.removeAttribute('hidden');
  }
  function closeDrawer() {
    if (!adminDrawer) return;
    adminDrawer.setAttribute('hidden', '');
  }

  if (adminHamburger) {
    adminHamburger.addEventListener('click', openDrawer);
  }
  if (adminDrawer) {
    adminDrawer.addEventListener('click', (e) => {
      if (e.target.classList.contains('drawer-backdrop')) {
        closeDrawer();
      }
    });
  }
  if (adminDrawerTabs) {
    adminDrawerTabs.addEventListener('click', (e) => {
      const btn = e.target.closest('.tab');
      if (!btn) return;
      // switch to the same tab as desktop
      const target = btn.dataset.target;
      const desktopBtn = document.querySelector(`#adminTabs .tab[data-target="${target}"]`);
      if (desktopBtn) desktopBtn.click();
      closeDrawer();
    });
  }

  function activateTab(targetSelector) {
    tabs.forEach(btn => btn.classList.remove('active'));
    panels.forEach(panel => { panel.classList.remove('active'); panel.setAttribute('hidden', ''); });

    const target = document.querySelector(targetSelector);
    if (target) {
      target.classList.add('active');
      target.removeAttribute('hidden');
    }

  }

  // =====================
  // Config: logo get/set
  // =====================
  async function fetchLogo() {
    try {
      const res = await fetch('/admin/config/logo');
      const data = await res.json();
      if (inputLogo) {
        inputLogo.value = data.logo_path || '';
        showLogoPreview();
      }
window.fetchLogo = fetchLogo;
    } catch (_) { /* ignore */ }
  }

  function showLogoPreview() {
    if (!inputLogo || !logoPreview) return;
    const url = inputLogo.value.trim();
    if (url) {
      logoPreview.src = url;
      logoPreview.style.display = 'inline-block';
    } else {
      logoPreview.style.display = 'none';
    }
  }

  async function saveLogo() {
    if (!inputLogo) return;
    const logo_path = inputLogo.value.trim();
    const res = await fetch('/admin/config/logo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ logo_path })
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar');
    }
    return res.json();
  }

  if (btnSaveLogo) {
    btnSaveLogo.addEventListener('click', async () => {
      try {
        btnSaveLogo.disabled = true;
        await saveLogo();
        toast('Logo guardado');
      } catch (e) {
        toast(e.message);
      } finally {
        btnSaveLogo.disabled = false;
      }
    });
  }

  if (btnPasteLogo && inputLogo) {
    btnPasteLogo.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          inputLogo.value = text.trim();
          showLogoPreview();
        }
      } catch (_) {
        toast('No se pudo leer desde el portapapeles');
      }
    });
    inputLogo.addEventListener('input', showLogoPreview);
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.setAttribute('aria-selected', 'false'));
      tab.setAttribute('aria-selected', 'true');
      tab.classList.add('active');
      activateTab(tab.dataset.target);
      // If Images tab is opened, refresh gallery
      if (tab.dataset.target === '#tab-images') {
        refreshGallery();
      }
      // If Config tab is opened, refresh rate and payments forms
      if (tab.dataset.target === '#tab-config') {
        fetchRate();
        fetchPayments();
        fetchMailInfo();
        fetchSessionInfo();
        fetchMidBanner && fetchMidBanner();
      }
      // If Orders tab is opened, refresh orders
      if (tab.dataset.target === '#tab-orders') {
        fetchOrders();
      }
      // If Affiliates tab is opened, refresh affiliates
      if (tab.dataset.target === '#tab-affiliates') {
        populatePackagesSelect();
        updatePkgSelectEnabled();
        fetchAffiliates();
        fetchAffWithdrawals();
      }
    });
  });

  // Initial state
  const active = document.querySelector('#adminTabs .tab.active');
  if (active) activateTab(active.dataset.target);
  // If landing on Orders, fetch initially
  if (document.querySelector('#tab-orders.active')) { fetchOrders(); fetchAffWithdrawalsForOrders(); }

  // Wire mail test button
  if (btnMailTest) btnMailTest.addEventListener('click', sendMailTest);
  if (btnMailSave) btnMailSave.addEventListener('click', saveMailDestination);
  // If landing on Config, also fetch session/mail info immediately
  if (document.querySelector('#tab-config.active')) { fetchMailInfo(); fetchSessionInfo(); }

  // =====================
  // Images: upload + list
  // =====================
  // Lightweight toast notifications
  function ensureToastHost() {
    let host = document.getElementById('toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'toast-host';
      host.style.position = 'fixed';
      host.style.right = '12px';
      host.style.bottom = '12px';
      host.style.display = 'grid';
      host.style.gap = '8px';
      host.style.zIndex = '9999';
      document.body.appendChild(host);
    }
    return host;
  }
  function toast(msg, type = 'info') {
    console.log(msg);
    const host = ensureToastHost();
    const el = document.createElement('div');
    el.textContent = String(msg || '').slice(0, 300);
    el.style.maxWidth = '320px';
    el.style.padding = '10px 12px';
    el.style.borderRadius = '10px';
    el.style.fontWeight = '700';
    el.style.boxShadow = '0 6px 18px rgba(0,0,0,0.25)';
    el.style.border = '1px solid';
    el.style.background = type === 'error' ? 'rgba(239,68,68,0.15)' : type === 'success' ? 'rgba(14,165,233,0.15)' : 'rgba(2,6,23,0.7)';
    el.style.color = type === 'error' ? '#fecaca' : type === 'success' ? '#bae6fd' : '#e5e7eb';
    el.style.borderColor = type === 'error' ? 'rgba(239,68,68,0.35)' : type === 'success' ? 'rgba(14,165,233,0.35)' : 'rgba(148,163,184,0.35)';
    host.appendChild(el);
    setTimeout(() => { el.remove(); }, 3500);
  }

  async function fetchImages() {
    const res = await fetch('/admin/images/list');
    if (!res.ok) throw new Error('No se pudo listar imÃ¡genes');
    return res.json();
  }

  function renderGallery(items) {
    if (!gallery || !tpl) return;
    gallery.innerHTML = '';
    // reset index
    imgIndex.byPath.clear();
    imgIndex.byTitle.clear();
    if (!items || items.length === 0) {
      gallery.innerHTML = '<div class="empty-state"><h3>Sin imÃ¡genes</h3><p>Sube imÃ¡genes para usarlas en el sitio.</p></div>';
      return;
    }
    items.forEach(img => {
      const node = tpl.content.cloneNode(true);
      const card = node.querySelector('.image-card');
      const thumb = node.querySelector('.thumb');
      const title = node.querySelector('.title');
      const path = node.querySelector('.path');
      const delBtn = node.querySelector('.btn-del');
      const delOv = node.querySelector('.btn-del-ov');
      if (thumb) thumb.src = img.path;
      if (title) title.textContent = img.title || '';
      if (path) path.textContent = img.path || '';
      const idStr = String(img.id);
      // index
      if (img.path) imgIndex.byPath.set(String(img.path), idStr);
      if (img.title) imgIndex.byTitle.set(String(img.title), idStr);
      if (card) { card.dataset.id = idStr; }
      if (delBtn) { delBtn.dataset.id = idStr; }
      if (delOv) { delOv.dataset.id = idStr; }
      if (title && title.setAttribute) { title.setAttribute('data-id', idStr); }
      if (path && path.setAttribute) { path.setAttribute('data-id', idStr); }
      const wrap = node.querySelector('.thumb-wrap');
      if (wrap && wrap.setAttribute) { wrap.setAttribute('data-id', idStr); }
      if (card) {
        // Extra attributes for robustness and debugging
        card.setAttribute('data-image-id', idStr);
        const meta = node.querySelector('.meta');
        if (meta && !meta.querySelector('.img-id')) {
          const sm = document.createElement('small');
          sm.className = 'img-id';
          sm.textContent = `ID: ${idStr}`;
          sm.style.display = 'block';
          sm.style.color = '#64748b';
          sm.style.marginTop = '2px';
          meta.insertBefore(sm, meta.firstChild);
        }
      }
      if (delBtn) {
        // Direct listener as a fallback in case delegation is interfered with
        delBtn.addEventListener('click', async (e) => {
          e.preventDefault();
          const id = delBtn.dataset.id || (card && card.dataset.id);
          console.log('[images] direct btn-del click', { id });
          await deleteImage(card, id, delBtn);
        });
      }
      if (delOv) {
        delOv.addEventListener('click', async (e) => {
          e.preventDefault();
          e.stopPropagation();
          const id = delOv.dataset.id || (card && card.dataset.id);
          console.log('[images] direct btn-del-ov click', { id });
          await deleteImage(card, id, delOv);
        });
      }
      gallery.appendChild(node);
    });
  }

  async function deleteImage(card, id, buttonEl) {
    try {
      // Primary: delete by path (more reliable in this UI)
      const pElPrimary = card && card.querySelector && card.querySelector('.path');
      const cardPathPrimary = pElPrimary && (pElPrimary.textContent || '').trim();
      if (cardPathPrimary) {
        try {
          console.log('[images] delete_by_path', { path: cardPathPrimary });
          const resP = await fetch('/admin/images/delete_by_path', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: cardPathPrimary })
          });
          const dP = await resP.json().catch(()=>({}));
          if (resP.ok && dP && dP.ok) {
            if (card) card.remove();
            await refreshGallery();
            toast('Imagen eliminada', 'success');
            return;
          }
        } catch (_) { /* ignore */ }
      }
      // Fallback: try ID-based deletion
      // Resolve missing ID by matching metadata if not provided
      if (!id) {
        try {
          const pEl = card && card.querySelector && card.querySelector('.path');
          const tEl = card && card.querySelector && card.querySelector('.title');
          const cardPath = pEl && (pEl.textContent || '').trim();
          const cardTitle = tEl && (tEl.textContent || '').trim();
          if (cardPath && imgIndex.byPath.has(cardPath)) id = imgIndex.byPath.get(cardPath);
          if (!id && cardTitle && imgIndex.byTitle.has(cardTitle)) id = imgIndex.byTitle.get(cardTitle);
          if (!id) {
            const imgEl = card && card.querySelector && card.querySelector('img.thumb');
            const src = imgEl && imgEl.src;
            if (src) {
              for (const [p, v] of imgIndex.byPath.entries()) { if (src.endsWith(p)) { id = v; break; } }
            }
          }
          if (!id) {
            const resList = await fetch('/admin/images/list');
            const list = await resList.json();
            const hit = (list || []).find(x => (cardPath && x.path === cardPath) || (cardTitle && x.title === cardTitle) || (card && card.querySelector('img.thumb') && (card.querySelector('img.thumb').src || '').endsWith(x.path)));
            if (hit) { id = String(hit.id); if (card && card.setAttribute) card.setAttribute('data-id', id); }
          }
          if (!id) {
            const idLabel = card && card.querySelector && card.querySelector('.img-id');
            if (idLabel && idLabel.textContent) { const m = idLabel.textContent.match(/ID:\s*(\d+)/i); if (m) { id = m[1]; if (card && card.setAttribute) card.setAttribute('data-id', id); } }
          }
        } catch (_) { /* ignore */ }
      }
      if (!id) { console.warn('[images] cannot resolve id for delete'); toast('No se pudo resolver la imagen', 'error'); return; }
      // For overlay button, skip confirm to avoid blocked dialogs on some setups
      if (!(buttonEl && buttonEl.classList && buttonEl.classList.contains('btn-del-ov'))) {
        const ok = true;
        if (!ok) return;
      }
      if (buttonEl) buttonEl.disabled = true;
      console.log('[images] sending delete', { id });
      let res = await fetch(`/admin/images/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        // fallback via POST (some hosts block DELETE)
        res = await fetch(`/admin/images/${id}/delete`, { method: 'POST' });
      }
      if (!res.ok) {
        let msg = 'No se pudo eliminar';
        try { const d = await res.json(); msg = d.error || msg; } catch(_) { /* ignore */ }
        throw new Error(msg);
      }
      if (card) card.remove();
      await refreshGallery();
      toast('Imagen eliminada', 'success');
    } catch (err) {
      toast(err.message || 'Error al eliminar', 'error');
    } finally {
      if (buttonEl) buttonEl.disabled = false;
    }
  }

  async function refreshGallery() {
  const data = await fetchImages().catch(() => null);
  if (!data) {
    if (gallery) gallery.innerHTML = `<div class="empty-state"><p>Error</p></div>`;
    return;
  }
  renderGallery(data);
}
window.refreshGallery = refreshGallery;
window.refreshGallery = refreshGallery;

  async function uploadImage(file) {
    const fd = new FormData();
    fd.append('image', file);
    const res = await fetch('/admin/images/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo subir');
    return data.image;
  }

  if (btnUpload && fileInput) {
    let lastOpenAt = 0;
    let lastFilesSig = '';
    let isUploading = false;

    const openPicker = (e) => {
      e.preventDefault();
      e.stopPropagation();
      const now = Date.now();
      if (now - lastOpenAt < 800 || isUploading) {
        console.log('[images] picker suppressed (debounce/busy)');
        return;
      }
      lastOpenAt = now;
      btnUpload.disabled = true; // avoid double-open by extra clicks
      console.log('[images] opening file picker');
      fileInput.click();
      // Re-enable shortly in case user cancels dialog
      setTimeout(() => { btnUpload.disabled = false; }, 1000);
    };

    btnUpload.addEventListener('click', openPicker);

    const onFileChange = async () => {
      if (isUploading) { console.log('[images] change ignored: upload in progress'); return; }
      // Self-disable listener to prevent duplicate firing on some browsers
      fileInput.removeEventListener('change', onFileChange);
      const files = Array.from(fileInput.files || []);
      const sig = files.map(f => `${f.name}|${f.size}|${f.lastModified}`).join(',');
      if (sig && sig === lastFilesSig) {
        console.log('[images] duplicate change ignored (same selection)');
        fileInput.value = '';
        // Reattach listener
        setTimeout(() => fileInput.addEventListener('change', onFileChange), 0);
        return;
      }
      lastFilesSig = sig;
      if (!files.length) {
        setTimeout(() => fileInput.addEventListener('change', onFileChange), 0);
        return;
      }
      try {
        isUploading = true;
        btnUpload.disabled = true;
        const seen = new Set();
        const unique = files.filter(f => {
          const s = `${f.name}|${f.size}|${f.lastModified}`;
          if (seen.has(s)) return false;
          seen.add(s);
          return true;
        });
        for (let i = 0; i < unique.length; i++) {
          const f = unique[i];
          if (!f) continue;
          toast(`Subiendo ${i+1}/${unique.length}: ${f.name}`);
          await uploadImage(f);
        }
        await refreshGallery();
        toast(`Se subieron ${unique.length} archivo(s)`, 'success');
      } catch (e) {
        toast(e.message || 'Error al subir', 'error');
      } finally {
        btnUpload.disabled = false;
        fileInput.value = '';
        isUploading = false;
        setTimeout(() => { lastOpenAt = 0; lastFilesSig = ''; }, 200);
        // Reattach listener after finishing
        setTimeout(() => fileInput.addEventListener('change', onFileChange), 0);
      }
    };

    // Attach once at init
    fileInput.addEventListener('change', onFileChange);
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => window.refreshGallery && window.refreshGallery());
  }

  if (gallery) {
    gallery.addEventListener('click', async (e) => {
      const btnCopy = e.target.closest('.btn-copy');
      const btnDel = e.target.closest('.btn-del');
      const btnDelOv = e.target.closest('.btn-del-ov');
      const card = e.target.closest('.image-card') || e.target.closest('[data-id]');
      if (!card) return;
      const withId = e.target.closest('[data-id]');
      const id = (btnDel && btnDel.dataset.id) || (btnDelOv && btnDelOv.dataset.id) || (withId && withId.getAttribute('data-id')) || card.getAttribute('data-id');
      const pathEl = card.querySelector('.path');
      if (btnCopy && pathEl) {
        try { await navigator.clipboard.writeText(pathEl.textContent || ''); toast('Copiado', 'success'); } catch (_) { toast('No se pudo copiar', 'error'); }
      }
      if (btnDel || btnDelOv) {
        console.log('[images] delegated btn-del click', { id });
        await deleteImage(card, id, (btnDel || btnDelOv));
      }
    });
  }

  // Si la pestaÃƒÆ’Ã‚Â±a de ImÃƒÆ’Ã‚Â¡genes ya estÃƒÆ’Ã‚Â¡ activa al cargar, refrescar
  if (document.querySelector('#tab-images.active')) {
    refreshGallery();
  }

  // DelegaciÃƒÆ’Ã‚Â³n global (respaldo) para botones de imÃƒÆ’Ã‚Â¡genes
  document.body.addEventListener('click', async (e) => {
    const del = e.target.closest('.btn-del');
    const delOv = e.target.closest('.btn-del-ov');
    const copy = e.target.closest('.btn-copy');
    if (!del && !delOv && !copy) return;
    const idHost = e.target.closest('[data-id]');
    const card = e.target.closest('.image-card') || idHost;
    const id = (del && del.dataset.id) || (delOv && delOv.dataset.id) || (idHost && idHost.getAttribute('data-id')) || (card && card.getAttribute('data-id'));
    if (copy && card) {
      const pathEl = card.querySelector('.path');
      if (pathEl) {
        try { await navigator.clipboard.writeText(pathEl.textContent || ''); toast('Copiado', 'success'); } catch (_) { toast('No se pudo copiar', 'error'); }
      }
    }
    if (del || delOv) {
      console.log('[images] body delegated btn-del click', { id });
      await deleteImage(card, id, (del || delOv));
    }
  });

  // Capturing listener as last resort to catch clicks before others cancel them
  document.addEventListener('click', async (e) => {
    const del = e.target.closest && e.target.closest('.btn-del');
    const delOv = e.target.closest && e.target.closest('.btn-del-ov');
    if (!del && !delOv) return;
    const idHost = e.target.closest && e.target.closest('[data-id]');
    const card = e.target.closest('.image-card') || idHost;
    const id = (del && del.dataset.id) || (delOv && delOv.dataset.id) || (idHost && idHost.getAttribute('data-id')) || (card && card.getAttribute('data-id'));
    console.log('[images] CAPTURE btn-del click', { id, target: e.target && e.target.className });
    e.preventDefault();
    await deleteImage(card, id, (del || delOv));
  }, true);

  // =====================
  // Affiliates: list + CRUD
  // =====================
  async function populatePackagesSelect() {
    if (!affPkgSelect) return;
    try {
      // Get all packages (both categories)
      const res = await fetch('/store/packages');
      const data = await res.json();
      const pkgs = (data && data.packages) || [];
      // Reset options
      affPkgSelect.innerHTML = '<option value="">ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Selecciona un juego ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â</option>';
      pkgs.forEach(p => {
        const opt = document.createElement('option');
        opt.value = String(p.id);
        opt.textContent = `${p.name} ${p.category ? 'Ãƒâ€šÃ‚Â· '+p.category.toUpperCase() : ''}`;
        affPkgSelect.appendChild(opt);
      });
    } catch (_) {
      // keep minimal options
    }
  }

  function updatePkgSelectEnabled() {
    if (!affScope || !affPkgSelect) return;
    const need = (affScope.value === 'package');
    affPkgSelect.disabled = !need;
    if (!need) affPkgSelect.value = '';
  }
  if (affScope) affScope.addEventListener('change', updatePkgSelectEnabled);
  async function fetchAffiliates() {
    try {
      const res = await fetch('/admin/special/users');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar afiliados');
      renderAffiliates(data.users || []);
    } catch (e) {
      if (affList) affList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
    }
  }

  function renderAffiliates(items) {
    if (!affList) return;
    affList.innerHTML = '';
    affList.classList.add('pkg-accordion');
    if (!items || items.length === 0) {
      affList.innerHTML = '<div class="empty-state"><h3>Sin afiliados</h3><p>Crea uno nuevo para comenzar.</p></div>';
      return;
    }
    const fmtUSD = (n) => {
      try { return Number(n||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); } catch(_) { return `$${n}`; }
    };
    items.forEach(u => {
      const row = document.createElement('div');
      row.className = 'pkg-item open';
      row.innerHTML = `
        <div class="pkg-header">
          <div>
            <div class="name">${u.name || '-'} <span class="badge">${u.active ? 'ACTIVO' : 'INACTIVO'}</span></div>
            <div class="sub">CÃƒÆ’Ã‚Â³digo: <strong>${u.code}</strong> ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ Email: <strong>${u.email || '-'}</strong> ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ Saldo: <strong>${fmtUSD(u.balance)}</strong> ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ Desc: <strong>${(u.discount_percent||0)}%</strong> ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢ Alcance: <strong>${u.scope || 'all'}${u.scope === 'package' && u.scope_package_id ? ' #'+u.scope_package_id : ''}</strong></div>
          </div>
          <div class="head-actions">
            <button class="btn btn-aff-save" data-id="${u.id}" type="button">Guardar</button>
            <button class="btn btn-aff-del" data-id="${u.id}" type="button">Eliminar</button>
          </div>
        </div>
        <div class="pkg-content" style="display:grid; gap:6px;">
          <input class="aff-edit-name" type="text" value="${u.name || ''}" placeholder="Nombre" />
          <input class="aff-edit-code" type="text" value="${u.code || ''}" placeholder="CÃƒÆ’Ã‚Â³digo" />
          <input class="aff-edit-email" type="email" value="${u.email || ''}" placeholder="Email" />
          <input class="aff-edit-pass" type="password" value="" placeholder="Nueva contraseÃƒÆ’Ã‚Â±a (opcional)" />
          <div style="display:grid; gap:6px; grid-template-columns: 1fr 1fr;">
            <input class="aff-edit-disc" type="number" step="0.1" min="0" max="100" value="${u.discount_percent || 0}" placeholder="Descuento %" />
            <select class="aff-edit-scope">
              <option value="all" ${u.scope !== 'package' ? 'selected' : ''}>Todos</option>
              <option value="package" ${u.scope === 'package' ? 'selected' : ''}>Solo juego</option>
            </select>
          </div>
          <input class="aff-edit-pkgid" type="number" min="1" value="${u.scope_package_id || ''}" placeholder="ID de juego (si aplica)" />
          <input class="aff-edit-balance" type="number" step="0.01" min="0" value="${u.balance || 0}" placeholder="Saldo USD" />
          <label style="display:flex; align-items:center; gap:8px;"><input class="aff-edit-active" type="checkbox" ${u.active ? 'checked' : ''}/> Activo</label>
        </div>
      `;
      affList.appendChild(row);
    });
  }

  async function createAffiliate() {
    const payload = {
      name: (affName && affName.value.trim()) || '',
      email: (affEmail && affEmail.value.trim()) || '',
      code: (affCode && affCode.value.trim()) || '',
      password: (affPass && affPass.value) || '',
      discount_percent: (affDisc && parseFloat(affDisc.value || '0')) || 0,
      scope: (affScope && affScope.value) || 'all',
      scope_package_id: (affPkgSelect && affPkgSelect.value ? parseInt(affPkgSelect.value, 10) : null),
      balance: (affBalance && parseFloat(affBalance.value || '0')) || 0,
      active: affActive ? !!affActive.checked : true
    };
    if (!payload.code) { toast('CÃƒÆ’Ã‚Â³digo requerido'); return; }
    const res = await fetch('/admin/special/users', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text(); throw new Error(txt || 'No se pudo crear afiliado');
    }
    return res.json();
  }

  if (btnAffCreate) {
    btnAffCreate.addEventListener('click', async () => {
      try {
        btnAffCreate.disabled = true;
        await createAffiliate();
        toast('Afiliado creado');
        if (affName) affName.value = '';
        if (affEmail) affEmail.value = '';
        if (affCode) affCode.value = '';
        if (affPass) affPass.value = '';
        if (affDisc) affDisc.value = '10';
        if (affScope) affScope.value = 'all';
        if (affPkgSelect) affPkgSelect.value = '';
        if (affBalance) affBalance.value = '0';
        if (affActive) affActive.checked = true;
        await fetchAffiliates();
      } catch (e) {
        toast(e.message || 'Error');
      } finally {
        btnAffCreate.disabled = false;
      }
    });
  }
  if (btnAffRefresh) btnAffRefresh.addEventListener('click', fetchAffiliates);
  if (btnAffWdRefresh) btnAffWdRefresh.addEventListener('click', fetchAffWithdrawals);
  if (btnOrdersWdRefresh) btnOrdersWdRefresh.addEventListener('click', fetchAffWithdrawalsForOrders);
  if (affList) {
    affList.addEventListener('click', async (e) => {
      const btnSave = e.target.closest('.btn-aff-save');
      const btnDel = e.target.closest('.btn-aff-del');
      if (btnSave) {
        const id = btnSave.getAttribute('data-id');
        const container = btnSave.closest('.pkg-item');
        const name = container.querySelector('.aff-edit-name')?.value.trim() || '';
        const code = container.querySelector('.aff-edit-code')?.value.trim() || '';
        const email = container.querySelector('.aff-edit-email')?.value.trim() || '';
        const password = container.querySelector('.aff-edit-pass')?.value || '';
        const discount_percent = parseFloat(container.querySelector('.aff-edit-disc')?.value || '0') || 0;
        const scope = container.querySelector('.aff-edit-scope')?.value || 'all';
        const scope_package_id = container.querySelector('.aff-edit-pkgid')?.value ? parseInt(container.querySelector('.aff-edit-pkgid').value, 10) : null;
        const balance = parseFloat(container.querySelector('.aff-edit-balance')?.value || '0') || 0;
        const active = !!container.querySelector('.aff-edit-active')?.checked;
        try {
          btnSave.disabled = true;
          const res = await fetch(`/admin/special/users/${id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, code, email, password, discount_percent, scope, scope_package_id, balance, active })
          });
          if (!res.ok) throw new Error('No se pudo guardar');
          await fetchAffiliates();
        } catch (err) {
          toast(err.message || 'Error al guardar');
        } finally {
          btnSave.disabled = false;
        }
      }
      if (btnDel) {
        const id = btnDel.getAttribute('data-id');
        try {
          btnDel.disabled = true;
          const res = await fetch(`/admin/special/users/${id}`, { method: 'DELETE' });
          if (!res.ok) throw new Error('No se pudo eliminar');
          await fetchAffiliates();
        } catch (err) {
          toast(err.message || 'Error al eliminar');
        } finally {
          btnDel.disabled = false;
        }
      }
    });
  }

  // =====================
  // Orders: list + actions
  // =====================
  async function fetchOrders() {
    try {
      const res = await fetch('/admin/orders');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar');
      renderOrders(data.orders || []);
    } catch (e) {
      if (ordersList) ordersList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
    }
  }

  function renderOrders(items) {
  function fixMb(s){ s = String(s==null?'':s); return s.replace(/ÃƒÆ’Ã‚Â¡|ÃƒÂ¡/g,'Ã¡').replace(/ÃƒÆ’Ã‚Â©|ÃƒÂ©/g,'Ã©').replace(/ÃƒÆ’Ã‚Â­|ÃƒÂ­/g,'Ã­').replace(/ÃƒÆ’Ã‚Â³|ÃƒÂ³/g,'Ã³').replace(/ÃƒÆ’Ã‚Âº|ÃƒÂº/g,'Ãº').replace(/ÃƒÆ’Ã‚Â±|ÃƒÂ±/g,'Ã±').replace(/Ãƒâ€šÃ‚Â·/g,'Â·').replace(/ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ï¿½/g,'-').replace(/ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢/g,'â€¢'); }
    if (!ordersList) return;
    ordersList.innerHTML = '';
    if (!items || items.length === 0) {
      ordersList.innerHTML = '<div class="empty-state"><h3>Sin Ã³rdenes</h3><p>Cuando los clientes confirmen pagos, sus Ã³rdenes aparecerÃ¡n aquÃ­.</p></div>';
      return;
    }
    const fmtUSD = (amt) => {
      try { return Number(amt||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); }
      catch(_) { return `$${amt}`; }
    };
    const hex8 = (n) => {
      const x = Math.max(0, parseInt(n, 10) || 0) >>> 0;
      return x.toString(16).toUpperCase().padStart(8, '0');
    };
    items.forEach(o => {
      const tile = document.createElement('div');
      tile.className = 'order-tile';
      const when = new Date(o.created_at).toLocaleString();
      const juego = o.package_name || `#${o.store_package_id}`;
      const diam = fixMb(o.item_title) || '';
      const precioUSD = fmtUSD(o.item_price_usd || 0);
      const statusIcon = o.status === 'approved' ? 'OK' : o.status === 'rejected' ? 'X' : '...';
      const statusClass = o.status === 'approved' ? 'ok' : o.status === 'rejected' ? 'rej' : 'pend';
      const playerId = fixMb(o.customer_id || '-') ;
      const txRef = fixMb(o.reference || '-') ;
      const gameName = fixMb(o.package_name || '');
      const isGift = (o.package_category || '').toLowerCase() === 'gift';
      tile.innerHTML = `
        <div class=\"row-head\">
          <div>
            <div class=\"ref\">${txRef} <span class=\"state ${statusClass}\">${statusIcon}</span></div>
            <div class=\"sub\">${gameName}</div>
          </div>
          <div class=\"box-right\">
            <code class=\"hex\">${playerId}</code>
            <button class=\"btn-copy\" type=\"button\" data-copy=\"${playerId}\">Copiar</button>
          </div>
        </div>
        <div class=\"row-metrics\">
          <div class=\"metric diam\"><span>${diam || ''}</span> <span>DIAM</span></div>
          <div class=\"metric usd\"><span>${precioUSD}</span></div>
        </div>
        <div class=\"row-foot\">
          <div>${when}</div>
          <div class=\"customer\">ID: ${playerId} - ${o.name || o.email || 'Cliente'}</div>
        </div>
        ${isGift ? `
        <div class=\"row-actions\">
          <input class=\"input gift-code\" data-id=\"${o.id}\" type=\"text\" placeholder=\"CÃ³digo para el cliente\" value=\"${o.delivery_code || ''}\" style=\"flex:1; min-width:220px;\" />
        </div>` : ''}
        <div class=\"row-actions\">
          <button class=\"btn btn-approve\" data-id=\"${o.id}\" ${o.status !== 'pending' ? 'disabled' : ''}>Aprobar</button>
          <button class=\"btn btn-reject\" data-id=\"${o.id}\" ${o.status !== 'pending' ? 'disabled' : ''}>Rechazar</button>
        </div>
      `;
      const cust = tile.querySelector('.row-foot .customer');
      if (cust) { cust.textContent = 'ID: ' + playerId + (o.customer_zone ? ' - ZONA: ' + o.customer_zone : '') + (o.phone ? ' - TEL: ' + o.phone : '') + ' - ' + (fixMb(o.name) || fixMb(o.email) || 'Cliente'); }
      ordersList.appendChild(tile);
    });
  }

  if (btnOrdersRefresh) btnOrdersRefresh.addEventListener('click', fetchOrders);
  if (ordersList) {
    ordersList.addEventListener('click', async (e) => {
      const copy = e.target.closest('.btn-copy');
      if (copy) {
        const value = copy.getAttribute('data-copy') || '';
        try { await navigator.clipboard.writeText(value); toast('Copiado'); } catch(_) { toast('No se pudo copiar'); }
        return;
      }
      const btnA = e.target.closest('.btn-approve');
      const btnR = e.target.closest('.btn-reject');
      const btn = btnA || btnR;
      if (!btn) return;
      const id = btn.getAttribute('data-id');
      const status = btnA ? 'approved' : 'rejected';
      try {
        btn.disabled = true;
        const payload = { status };
        // If there is a gift code input for this order and approving, send it
        if (status === 'approved') {
          const codeInput = ordersList.querySelector(`.gift-code[data-id="${id}"]`);
          if (codeInput && codeInput.value.trim()) payload.delivery_code = codeInput.value.trim();
        }
        const res = await fetch(`/admin/orders/${id}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo actualizar');
        await fetchOrders();
      } catch (err) {
        toast(err.message || 'Error');
      } finally {
        btn.disabled = false;
      }
    });
  }

  // =====================
  // Config: rate get/set
  // =====================
  async function fetchRate() {
  try {
    const res = await fetch('/admin/config/rate');
    const data = await res.json();
    if (data && data.ok && inputRate) inputRate.value = data.rate_bsd_per_usd || '';
  } catch (_) { /* ignore */ }
}
window.fetchRate = fetchRate;window.fetchRate = fetchRate;
  }

  async function saveRate() {
    if (!inputRate) return;
    const payload = { rate_bsd_per_usd: inputRate.value.trim() };
    const res = await fetch('/admin/config/rate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar la tasa');
    }
    return res.json();
  }

  // =====================
  // Config: hero get/set
  // =====================
  async function fetchHero() {
    try {
      const res = await fetch('/admin/config/hero');
      const data = await res.json();
      if (data && data.ok) {
        if (hero1) hero1.value = data.hero_1 || '';
        if (hero2) hero2.value = data.hero_2 || '';
        if (hero3) hero3.value = data.hero_3 || '';
      }
window.fetchHero = fetchHero;
    } catch (_) { /* ignore */ }
  }

  async function saveHero() {
    const payload = {
      hero_1: hero1 ? hero1.value.trim() : '',
      hero_2: hero2 ? hero2.value.trim() : '',
      hero_3: hero3 ? hero3.value.trim() : ''
    };
    const res = await fetch('/admin/config/hero', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar hero');
    }
    return res.json();
  }

  function renderGallery(items) {
    if (!gallery) return;
    gallery.innerHTML = '';
    if (!items || items.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.innerHTML = '<h3>Sin imÃ¡genes</h3><p>Sube una imagen para comenzar.</p>';
      gallery.appendChild(empty);
      return;
    }
    for (const it of items) {
      const node = tpl.content.firstElementChild.cloneNode(true);
      const img = node.querySelector('.thumb');
      const title = node.querySelector('.title');
      const path = node.querySelector('.path');
      img.src = it.path;
      img.alt = it.alt_text || it.title || 'Imagen';
      title.textContent = it.title || '';
      path.textContent = it.path || '';
      gallery.appendChild(node);
    }
  }

  async function uploadImage(file) {
    const form = new FormData();
    form.append('image', file);
    const res = await fetch('/admin/images/upload', {
      method: 'POST',
      body: form
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'Error al subir');
    }
    return res.json();
  }

  if (btnUpload && fileInput) {
    btnUpload.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      try {
        btnUpload.disabled = true;
        const result = await uploadImage(file);
        toast('Imagen subida');
        await refreshGallery();
      } catch (e) {
        toast(e.message);
      } finally {
        btnUpload.disabled = false;
        fileInput.value = '';
      }
    });
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => window.refreshGallery && window.refreshGallery());
  }

  // Copy path button (event delegation)
  if (gallery) {
    gallery.addEventListener('click', async (e) => {
      const btn = e.target.closest('.btn-copy');
      if (!btn) return;
      const meta = btn.closest('.meta');
      const pathEl = meta && meta.querySelector('.path');
      const text = pathEl ? pathEl.textContent : '';
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        toast('Ruta copiada al portapapeles');
      } catch (_) {
        toast('No se pudo copiar la ruta');
      }
    });
  }

  // Fetch current config on load of admin page (after element refs are defined)
  window.fetchLogo && window.fetchLogo();
  window.fetchMidBanner && window.fetchMidBanner();
  window.fetchHero && window.fetchHero();
  window.fetchRate && window.fetchRate();
  window.fetchPayments && window.fetchPayments();

  // =====================
  // Logo picker modal
  // =====================
  let currentPickTarget = null;
  async function openLogoPicker(targetInput) {
    if (!logoPicker) return;
    currentPickTarget = targetInput || null;
    await loadLogoPickerGrid();
    logoPicker.removeAttribute('hidden');
  }

  function closeLogoPicker() {
    if (!logoPicker) return;
    logoPicker.setAttribute('hidden', '');
  }

  async function loadLogoPickerGrid() {
    if (!logoPickerGrid) return;
    logoPickerGrid.innerHTML = '';
    try {
      const res = await fetch('/admin/images/list');
      const data = await res.json();
      if (!data || data.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = '<h3>Sin imÃ¡genes</h3><p>Sube una imagen en la pestaÃ±a ImÃ¡genes.</p>';
        logoPickerGrid.appendChild(empty);
        return;
      }
      for (const it of data) {
        const node = logoPickerTpl.content.firstElementChild.cloneNode(true);
        node.querySelector('.thumb').src = it.path;
        node.querySelector('.title').textContent = it.title || '';
        node.querySelector('.path').textContent = it.path || '';
        logoPickerGrid.appendChild(node);
      }
    } catch (_) {
      const err = document.createElement('div');
      err.textContent = 'Error cargando imÃ¡genes';
      logoPickerGrid.appendChild(err);
    }
  }

  if (btnPickLogo) {
    btnPickLogo.addEventListener('click', () => openLogoPicker(inputLogo));
  }
  if (btnPickMidBanner) {
    btnPickMidBanner.addEventListener('click', () => openLogoPicker(inputMidBanner));
  }
  if (btnPickHero1) btnPickHero1.addEventListener('click', () => openLogoPicker(hero1));
  if (btnPickHero2) btnPickHero2.addEventListener('click', () => openLogoPicker(hero2));
  if (btnPickHero3) btnPickHero3.addEventListener('click', () => openLogoPicker(hero3));
  if (btnPickPkgImage) btnPickPkgImage.addEventListener('click', () => openLogoPicker(pkgImage));
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', closeLogoPicker);
  }
  if (logoPicker) {
    logoPicker.addEventListener('click', (e) => {
      if (e.target.classList.contains('modal-backdrop')) {
        closeLogoPicker();

      }
    });
  }

  // Picker grid click handling: use selected image
  if (logoPickerGrid) {
    logoPickerGrid.addEventListener('click', async (e) => {
      const btn = e.target && e.target.closest && e.target.closest('.btn-use-logo');
      if (!btn) return;
      const meta = btn.closest && btn.closest('.meta');
      const pathEl = meta && meta.querySelector && meta.querySelector('.path');
      const path = pathEl && (pathEl.textContent || '').trim();
      if (!path) return;
      const target = currentPickTarget || inputLogo;
      if (!target) return;
      target.value = path;
      if (target === inputLogo) {
        try {
          showLogoPreview && showLogoPreview();
          if (btnSaveLogo) btnSaveLogo.disabled = true;
          const res = await fetch('/admin/config/logo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ logo_path: path }) });
          if (!res.ok) throw new Error('No se pudo guardar el logo');
          toast && toast('Logo actualizado');
        } catch (_) {
          toast && toast('No se pudo guardar el logo');
        } finally {
          if (btnSaveLogo) btnSaveLogo.disabled = false;
        }
      } else if (target === inputMidBanner) {
        try {
          showMidBannerPreview && showMidBannerPreview();
          if (btnSaveMidBanner) btnSaveMidBanner.disabled = true;
          const res = await fetch('/admin/config/mid_banner', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mid_banner_path: path }) });
          if (!res.ok) throw new Error('No se pudo guardar el banner');
          toast && toast('Banner actualizado');
        } catch (_) {
          toast && toast('No se pudo guardar el banner');
        } finally {
          if (btnSaveMidBanner) btnSaveMidBanner.disabled = false;
        }
      }
      closeLogoPicker && closeLogoPicker();
    });
  }
  // Save payments
  if (btnSavePayments) {
    btnSavePayments.addEventListener('click', async () => {
      try {
        btnSavePayments.disabled = true;
        const resp = await savePayments();
        if (resp && resp.ok) {
          toast('MÃƒÂ©todos de pago guardados');
          await fetchPayments();
        } else {
          toast('Guardado, pero respuesta inesperada');
        }
      } catch (e) {
        toast(e.message || 'No se pudo guardar');
      } finally {
        btnSavePayments.disabled = false;
      }
    });
  }

  // Save hero (carousel)
  if (btnSaveHero) {
    btnSaveHero.addEventListener('click', async () => {
      try {
        btnSaveHero.disabled = true;
        const resp = await saveHero();
        if (resp && resp.ok) {
          toast('Carrusel guardado');
          await fetchHero();
        } else {
          toast('Guardado, pero respuesta inesperada');
        }
      } catch (e) {
        toast(e.message || 'No se pudo guardar hero');
      } finally {
        btnSaveHero.disabled = false;
      }
    });
  }
  // Packages CRUD
  // =====================
  function renderPackagesList(items) {
    if (!pkgList) return;
    const grpSpec = pkgList.querySelector('#pkg-group-special');
    const grpNorm = pkgList.querySelector('#pkg-group-normal');
    const accSpec = grpSpec && grpSpec.querySelector('.pkg-accordion');
    const accNorm = grpNorm && grpNorm.querySelector('.pkg-accordion');
    if (accSpec) accSpec.innerHTML = '';
    if (accNorm) accNorm.innerHTML = '';
    if (!items || items.length === 0) {
      const target = accNorm || pkgList;
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.innerHTML = '<h3>Sin paquetes</h3><p>Crea uno nuevo para comenzar.</p>';
      target.appendChild(empty);
      if (grpSpec) grpSpec.hidden = true;
      return;
    }
    let specCount = 0;
    items.forEach(p => {
      const isGift = (p.category || 'mobile') === 'gift';
      const item = document.createElement('div');
      item.className = 'pkg-item';
      item.dataset.id = String(p.id || '');
      item.innerHTML = `
        <div class="pkg-header">
          <img class="mini-thumb" src="${p.image_path}" alt="${p.name}">
          <div>
            <div class="name">${p.name}
              <span class="badge ${isGift ? 'gift' : ''}">${isGift ? 'GIFT CARD' : 'MOBILE'}</span>
            </div>
          </div>
          <div class="head-actions">
            <button class="btn btn-drag" data-id="${p.id}" type="button" title="Arrastrar">↕</button>
            <button class="btn btn-toggle" data-id="${p.id}" type="button">Editar</button>
            <button class="btn btn-delete" data-id="${p.id}" type="button">Eliminar</button>
          </div>
        </div>
        <div class="pkg-content">
          <input class="edit-name" type="text" value="${p.name}" placeholder="Nombre"/>
          <select class="edit-category">
            <option value="mobile" ${p.category === 'mobile' ? 'selected' : ''}>Juegos Mobile</option>
            <option value="gift" ${p.category === 'gift' ? 'selected' : ''}>Gift Cards</option>
          </select>
          <textarea class="edit-desc" placeholder="Descripción del juego" style="min-height:60px;">${p.description || ''}</textarea>
          <label style="display:flex; align-items:center; gap:8px; margin:4px 0;">
            <input class="edit-active" type="checkbox" ${p.active ? 'checked' : ''}/> Activo
          </label>
          <label style="display:flex; align-items:center; gap:8px; margin:4px 0;">
            <input class="edit-requires-zone" type="checkbox" ${p.requires_zone_id ? 'checked' : ''}/> Zona ID requerida
          </label>
          <div style="display:flex; gap:6px;">
            <input class="edit-image" type="text" value="${p.image_path}" readonly />
            <button class="btn btn-pick-img" type="button">Elegir</button>
          </div>
          <code class="path">${p.image_path}</code>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-save" data-id="${p.id}" type="button">Guardar</button>
            <button class="btn btn-cancel" type="button">Cancelar</button>
          </div>
          <hr style="margin:12px 0; opacity:.4;">
          <h4 style="margin:0 0 8px;">Paquetes de este juego</h4>
          <div class="game-items" data-gid="${p.id}">
            <div class="items-actions" style="display:flex; gap:6px; margin-bottom:8px;">
              <button class="btn btn-items-refresh" type="button">Refrescar</button>
            </div>
            <div class="items-list"></div>
            <div class="items-form" style="margin-top:10px; display:grid; gap:6px; grid-template-columns: 1fr 140px;">
              <input class="new-item-title" type="text" placeholder="Título del paquete" />
              <input class="new-item-price" type="number" step="0.01" min="0" placeholder="Precio" />
              <div style="grid-column:1 / -1; display:flex; gap:6px;">
                <button class="btn btn-item-create" type="button">Agregar paquete</button>
              </div>
            </div>
          </div>
        </div>
      `;
      // Bind image picker for this item
      const imgInput = item.querySelector('.edit-image');
      const pickBtn = item.querySelector('.btn-pick-img');
      if (pickBtn && imgInput) {
        pickBtn.addEventListener('click', (ev) => { ev.preventDefault(); openLogoPicker(imgInput); });
      }
      // Enable drag via handle and persist on drop
      const dragHandle = item.querySelector('.btn-drag');
      if (dragHandle) {
        dragHandle.addEventListener('mousedown', () => { try { item.setAttribute('draggable', 'true'); } catch(_) {} });
        ['mouseup','mouseleave','blur'].forEach(ev => dragHandle.addEventListener(ev, () => { try { item.removeAttribute('draggable'); } catch(_) {} }));
      }
      item.addEventListener('dragstart', (ev) => {
        item.classList.add('dragging');
        try { ev.dataTransfer.setData('text/plain', item.dataset.id || ''); } catch(_) {}
      });
      item.addEventListener('dragend', async () => {
        item.classList.remove('dragging');
        try { item.removeAttribute('draggable'); } catch(_) {}
        try { await savePkgOrder(); toast('Orden guardado'); } catch(e) { toast('No se pudo guardar el orden', 'error'); }
      });
      if (isGift && accSpec) { accSpec.appendChild(item); specCount++; }
      else if (accNorm) { accNorm.appendChild(item); }
      else { pkgList.appendChild(item); }
    });
    if (grpSpec) grpSpec.hidden = specCount === 0;
    const containers = [accSpec, accNorm, pkgList].filter(Boolean);
    containers.forEach(container => {
      container.addEventListener('dragover', (e) => {
        e.preventDefault();
        const dragging = document.querySelector('.pkg-item.dragging');
        if (!dragging) return;
        const afterEl = getDragAfterElement(container, e.clientY);
        if (afterEl == null) container.appendChild(dragging);
        else container.insertBefore(dragging, afterEl);
      });
    });
  }

// Save hero (carousel)
if (btnSaveHero) {
  btnSaveHero.addEventListener('click', async () => {
    try {
      btnSaveHero.disabled = true;
      const resp = await saveHero();
      if (resp && resp.ok) {
        toast('Carrusel guardado');
        await fetchHero();
      } else {
        toast('Guardado, pero respuesta inesperada');
      }
    } catch (e) {
      toast(e.message || 'No se pudo guardar hero');
    } finally {
      btnSaveHero.disabled = false;
    }
  });
}

  // Fetch and render packages
  async function fetchPackages() {
    try {
      const res = await fetch('/admin/packages');
      const data = await res.json();
      if (data && data.ok) renderPackagesList(data.packages);
      else renderPackagesList([]);
    } catch (_) {
      if (pkgList) pkgList.innerHTML = '<div class="empty-state"><p>Error</p></div>';
    }
  }

  // Create a new store package
  async function createPackage() {
    const name = (pkgName && pkgName.value.trim()) || '';
    const image_path = (pkgImage && pkgImage.value.trim()) || '';
    const category = (pkgCategory && pkgCategory.value) || 'mobile';
    const description = (pkgDesc && pkgDesc.value.trim()) || '';
    const requires_zone_id = !!(pkgRequires && pkgRequires.checked);
    if (!name || !image_path) {
      toast('Nombre e imagen requeridos');
      throw new Error('Nombre e imagen requeridos');
    }
    const res = await fetch('/admin/packages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, image_path, category, description, requires_zone_id })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.error || 'No se pudo crear');
    }
    return data;
  }

  if (btnPackagesRefresh) {
    btnPackagesRefresh.addEventListener('click', fetchPackages);
  }
  if (btnPickPkgImage && pkgImage) {
    btnPickPkgImage.addEventListener('click', (e) => { e.preventDefault(); openLogoPicker(pkgImage); });
  }
  if (btnCreatePkg) {
    btnCreatePkg.addEventListener('click', async () => {
      try {
        btnCreatePkg.disabled = true;
        await createPackage();
        toast('Paquete creado', 'success');
        if (pkgName) pkgName.value = '';
        if (pkgImage) pkgImage.value = '';
        if (pkgDesc) pkgDesc.value = '';
        if (pkgRequires) pkgRequires.checked = false;
        await fetchPackages();
      } catch (e) {
        toast(e.message || 'No se pudo crear', 'error');
      } finally {
        btnCreatePkg.disabled = false;
      }
    });
  }
  if (pkgList) {
    pkgList.addEventListener('click', async (e) => {
      const btnDel = e.target.closest('.btn-delete');
      const btnPick = e.target.closest('.btn-pick-img');
      const btnSave = e.target.closest('.btn-save');
      const btnToggle = e.target.closest('.btn-toggle');
      const btnCancel = e.target.closest('.btn-cancel');
      const btnItemsRefresh = e.target.closest('.btn-items-refresh');
      const btnItemCreate = e.target.closest('.btn-item-create');
      const btnItemDelete = e.target.closest('.btn-item-delete');
      const btnItemSave = e.target.closest('.btn-item-save');
      if (btnDel) {
        const id = btnDel.getAttribute('data-id');
        if (!id) return;
        try {
          btnDel.disabled = true;
          const res = await fetch(`/admin/packages/${id}`, { method: 'DELETE' });
          if (!res.ok) throw new Error('No se pudo eliminar');
          await fetchPackages();
        } catch (err) {
          toast(err.message || 'Error al eliminar');
        } finally {
          btnDel.disabled = false;
        }
        return;
      }
      if (btnPick) {
        // open image picker for this item
        const meta = btnPick.closest('.meta');
        const input = meta && meta.querySelector('.edit-image');
        if (input) {
          openLogoPicker(input); // reuse picker
        }
        return;
      }
      if (btnToggle) {
        const container = btnToggle.closest('#pkg-list');
        const item = btnToggle.closest('.pkg-item');
        if (container && item) {
          // Close others
          container.querySelectorAll('.pkg-item.open').forEach(el => { if (el !== item) el.classList.remove('open'); });
          item.classList.toggle('open');
          // When opening, refresh game items
          if (item.classList.contains('open')) {
            const game = item.querySelector('.game-items');
            if (game) {
              const gid = game.getAttribute('data-gid');
              await loadGameItems(game, gid);
            }
          }
        }
        return;
      }
      if (btnCancel) {
        const item = btnCancel.closest('.pkg-item');
        if (item) item.classList.remove('open');
        return;
      }
      if (btnSave) {
        const id = btnSave.getAttribute('data-id');
        if (!id) return;
        const item = btnSave.closest('.pkg-item');
        const nameEl = item && item.querySelector('.edit-name');
        const catEl = item && item.querySelector('.edit-category');
        const imgEl = item && item.querySelector('.edit-image');
        const descEl = item && item.querySelector('.edit-desc');
        const activeEl = item && item.querySelector('.edit-active');
        const rzEl = item && item.querySelector('.edit-requires-zone');
        const payload = {
          name: nameEl ? nameEl.value.trim() : '',
          category: catEl ? catEl.value : 'mobile',
          image_path: imgEl ? imgEl.value.trim() : '',
          description: descEl ? descEl.value.trim() : '',
          requires_zone_id: rzEl ? !!rzEl.checked : false,
          active: activeEl ? !!activeEl.checked : true
        };
        try {
          btnSave.disabled = true;
          const res = await fetch(`/admin/packages/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (!res.ok) throw new Error('No se pudo guardar');
          await fetchPackages();
        } catch (err) {
          toast(err.message || 'Error al guardar');
        } finally {
          btnSave.disabled = false;
        }
      }

      // Items section handlers
      if (btnItemsRefresh) {
        const game = btnItemsRefresh.closest('.game-items');
        const gid = game && game.getAttribute('data-gid');
        if (gid) await loadGameItems(game, gid);
        return;
      }
      if (btnItemCreate) {
        const game = btnItemCreate.closest('.game-items');
        const gid = game && game.getAttribute('data-gid');
        const titleEl = game && game.querySelector('.new-item-title');
        const priceEl = game && game.querySelector('.new-item-price');
        const title = titleEl ? titleEl.value.trim() : '';
        const price = priceEl ? parseFloat(priceEl.value || '0') : 0;
        if (!gid || !title) { toast('TÃƒÆ’Ã‚Â­tulo requerido'); return; }
        try {
          btnItemCreate.disabled = true;
          const res = await fetch(`/admin/package/${gid}/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, price })
          });
          if (!res.ok) throw new Error('No se pudo crear');
          if (titleEl) titleEl.value = '';
          if (priceEl) priceEl.value = '';
          await loadGameItems(game, gid);
        } catch (err) {
          toast(err.message || 'Error al crear');
        } finally {
          btnItemCreate.disabled = false;
        }
        return;
      }
      if (btnItemDelete) {
        const row = btnItemDelete.closest('.item-row');
        const id = row && row.getAttribute('data-id');
        if (!id) return;
        try {
          btnItemDelete.disabled = true;
          const res = await fetch(`/admin/package/item/${id}`, { method: 'DELETE' });
          if (!res.ok) throw new Error('No se pudo eliminar');
          const game = btnItemDelete.closest('.game-items');
          const gid = game && game.getAttribute('data-gid');
          await loadGameItems(game, gid);
        } catch (err) {
          toast(err.message || 'Error al eliminar');
        } finally {
          btnItemDelete.disabled = false;
        }
        return;
      }
      if (btnItemSave) {
        const row = btnItemSave.closest('.item-row');
        const id = row && row.getAttribute('data-id');
        if (!id) return;
        const titleEl = row.querySelector('.it-title');
        const priceEl = row.querySelector('.it-price');
        const specialEl = row.querySelector('.it-special');
        const payload = {
          title: titleEl ? titleEl.value.trim() : '',
          price: priceEl ? parseFloat(priceEl.value || '0') : 0,
          sticker: specialEl && specialEl.checked ? 'special' : ''
        };
        try {
          btnItemSave.disabled = true;
          const res = await fetch(`/admin/package/item/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (!res.ok) throw new Error('No se pudo guardar');
          toast('Guardado');
        } catch (err) {
          toast(err.message || 'Error al guardar');
        } finally {
          btnItemSave.disabled = false;
        }
        return;
      }
    });
  }

  // Load packages if tab is visible initially
  fetchPackages();

  // Helpers for game items rendering
  async function loadGameItems(gameContainer, gid) {
    if (!gameContainer || !gid) return;
    const list = gameContainer.querySelector('.items-list');
    if (!list) return;
    list.innerHTML = '<div class="empty-state"><p>Cargando...</p></div>';
    try {
      const res = await fetch(`/admin/package/${gid}/items`);
      const data = await res.json();
      if (!data || !data.ok) throw new Error('No se pudo cargar');
      renderItemsList(list, data.items || []);
    } catch (err) {
      list.innerHTML = `<div class="empty-state"><p>${err.message || 'Error'}</p></div>`;
    }
  }

  function renderItemsList(list, items) {
    list.innerHTML = '';
    if (!items || items.length === 0) {
      list.innerHTML = '<div class="empty-state"><p>Sin paquetes para este juego.</p></div>';
      return;
    }
    const specials = items.filter(it => (it.sticker || '').toLowerCase() === 'special');
    const normals = items.filter(it => (it.sticker || '').toLowerCase() !== 'special');
    const addRow = (it) => {
      const row = document.createElement('div');
      row.className = 'item-row';
      row.setAttribute('data-id', it.id);
      row.style.display = 'grid';
      row.style.gridTemplateColumns = '1fr 140px';
      row.style.gap = '6px';
      row.style.marginBottom = '8px';
      row.innerHTML = `
        <input class="it-title" type="text" value="${it.title || ''}" placeholder="Título" />
        <input class="it-price" type="number" step="0.01" min="0" value="${Number(it.price || 0)}" placeholder="Precio" />
        <div style="grid-column:1 / -1; display:flex; align-items:center; gap:12px;">
          <label style="display:flex; align-items:center; gap:6px;">
            <input class="it-special" type="checkbox" ${(it.sticker||'').toLowerCase()==='special' ? 'checked' : ''}/> Especial
          </label>
          <div style="display:flex; gap:6px; margin-left:auto;">
            <button class="btn btn-item-save" type="button">Guardar</button>
            <button class="btn btn-item-delete" type="button">Eliminar</button>
          </div>
        </div>
      `;
      return row;
    };
    if (specials.length > 0) specials.forEach(it => list.appendChild(addRow(it)));
    if (normals.length > 0) {
      const sep = document.createElement('div');
      sep.style.borderTop = '1px solid rgba(148,163,184,0.35)';
      sep.style.margin = '10px 0';
      list.appendChild(sep);
      normals.forEach(it => list.appendChild(addRow(it)));
    }
  }
});
