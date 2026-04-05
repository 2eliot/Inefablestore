document.addEventListener('DOMContentLoaded', () => {
  console.log('admin.js loaded v7');
  const tabs = document.querySelectorAll('#adminTabs .tab');
  const panels = document.querySelectorAll('.tab-panel');
  // Elements used across handlers (declare early)
  const btnUpload = document.getElementById('btn-upload');
  const btnRefresh = document.getElementById('btn-refresh');
  const fileInput = document.getElementById('file-input');
  const gallery = document.getElementById('gallery');
  const tpl = document.getElementById('image-card-tpl');
  let lastOpenAt = 0;
  let lastFilesSig = '';
  let isUploading = false;
  let processingChange = false;
  // Client-side index to resolve IDs when dataset is missing
  const imgIndex = {
    byPath: new Map(), // '/static/uploads/..' => id
    byTitle: new Map(), // title => id
  };
  // Config elements
  const inputSiteName = document.getElementById('site-name');
  const btnSaveSiteName = document.getElementById('btn-save-site-name');
  const inputLogo = document.getElementById('logo-path');
  const btnSaveLogo = document.getElementById('btn-save-logo');
  // Mid banner config
  const inputMidBanner = document.getElementById('mid-banner-path');
  const btnSaveMidBanner = document.getElementById('btn-save-mid-banner');
  // Thanks image config
  const inputThanksImage = document.getElementById('thanks-image-path');
  const btnSaveThanksImage = document.getElementById('btn-save-thanks-image');
  // Hero config
  const hero1 = document.getElementById('hero-1');
  const hero2 = document.getElementById('hero-2');
  const hero3 = document.getElementById('hero-3');
  const btnSaveHero = document.getElementById('btn-save-hero');
  // Rate config
  const inputRate = document.getElementById('rate-bsd');
  const btnSaveRate = document.getElementById('btn-save-rate');
  // Force-hide mail verification and session sections (fallback)
  function hideMailAndSessionSections() {
    const ids = [
      'mail-user','mail-to','mail-subject','mail-body','btn-mail-save','btn-mail-test','mail-test-result',
      'sess-email','sess-role'
    ];
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const row = el.closest && el.closest('.form-row');
      if (row) { row.style.display = 'none'; }
      else { el.style.display = 'none'; }
    });
    // Also hide nearby headings if present
    document.querySelectorAll('h3').forEach(h3 => {
      const txt = (h3.textContent || '').toLowerCase();
      if (txt.includes('correo: verificación') || txt.includes('correo: verificacion') || txt.includes('sesión actual') || txt.includes('sesion actual')) {
        h3.style.display = 'none';
      }
    });
  }

  // Save Thanks image
  if (btnSaveThanksImage) {
    btnSaveThanksImage.addEventListener('click', async () => {
      try {
        btnSaveThanksImage.disabled = true;
        await saveThanksImage();
        toast && toast('Imagen de gracias guardada');
      } catch (e) {
        toast && toast(e.message || 'No se pudo guardar');
      } finally {
        btnSaveThanksImage.disabled = false;
      }
    });
  }

  // =====================
  // Blocked Customers (Player IDs)
  // =====================
  // Elements for Blocked Customers tab (declare before use)
  const btnBlockedRefresh = document.getElementById('btn-blocked-refresh');
  const blockedList = document.getElementById('blocked-list');
  const blockedForm = document.getElementById('blocked-form');
  const blockedCustomerId = document.getElementById('blocked-customer-id');
  const blockedReason = document.getElementById('blocked-reason');
  const blockedActive = document.getElementById('blocked-active');
  const btnBlockedAdd = document.getElementById('btn-blocked-add');
  async function fetchBlocked() {
    if (!blockedList) return;
    blockedList.innerHTML = '<div class="empty-state"><p>Cargando...</p></div>';
    try {
      const res = await fetch('/admin/blocked-customers');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar');
      renderBlocked(data.blocked || []);
    } catch (e) {
      blockedList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
    }
  }

  function renderBlocked(items) {
    if (!blockedList) return;
    blockedList.innerHTML = '';
    if (!items || items.length === 0) {
      blockedList.innerHTML = '<div class="empty-state"><h3>Sin IDs bloqueados</h3><p>Agrega IDs de jugadores que desees bloquear.</p></div>';
      return;
    }
    items.forEach(r => {
      const card = document.createElement('div');
      card.className = 'order-card';
      const when = r.created_at ? new Date(r.created_at).toLocaleString() : '';
      card.innerHTML = `
        <div class="order-head">
          <div>
            <div class="order-id">#${r.id} · ${r.customer_id}</div>
            <div class="order-meta">
              <span>${r.reason ? r.reason : ''}</span>
              <span class="badge ${r.active ? 'approved' : 'rejected'}">${r.active ? 'ACTIVO' : 'INACTIVO'}</span>
            </div>
          </div>
          <div class="box-right">
            <div class="metric usd"><span>${when}</span></div>
          </div>
        </div>
        <div class="order-actions">
          <button class="btn btn-blocked-toggle" data-id="${r.id}" data-active="${r.active ? '1' : '0'}">${r.active ? 'Desactivar' : 'Activar'}</button>
          <button class="btn btn-blocked-del" data-id="${r.id}">Eliminar</button>
        </div>
      `;
      blockedList.appendChild(card);
    });
  }

  async function addOrUpdateBlocked() {
    const payload = {
      customer_id: blockedCustomerId ? (blockedCustomerId.value || '').trim() : '',
      reason: blockedReason ? (blockedReason.value || '').trim() : '',
      active: blockedActive ? !!blockedActive.checked : true,
    };
    if (!payload.customer_id) { toast && toast('Ingrese un ID de jugador'); return; }
    const res = await fetch('/admin/blocked-customers', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo guardar');
    // Clear only reason checkbox keep id for series
    if (blockedReason) blockedReason.value = '';
    await fetchBlocked();
  }

  if (btnBlockedAdd) {
    btnBlockedAdd.addEventListener('click', async () => {
      try {
        btnBlockedAdd.disabled = true;
        await addOrUpdateBlocked();
        toast && toast('Guardado');
      } catch (e) {
        toast && toast(e.message || 'Error');
      } finally {
        btnBlockedAdd.disabled = false;
      }
    });
  }

  if (btnBlockedRefresh) {
    btnBlockedRefresh.addEventListener('click', fetchBlocked);
  }

  if (blockedList) {
    blockedList.addEventListener('click', async (e) => {
      const del = e.target.closest('.btn-blocked-del');
      const tog = e.target.closest('.btn-blocked-toggle');
      if (del) {
        const id = del.getAttribute('data-id');
        if (!id) return;
        try {
          del.disabled = true;
          const res = await fetch(`/admin/blocked-customers/${id}`, { method: 'DELETE' });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo eliminar');
          await fetchBlocked();
        } catch (err) {
          toast && toast(err.message || 'Error');
        } finally {
          del.disabled = false;
        }
      }
      if (tog) {
        const id = tog.getAttribute('data-id');
        const cur = tog.getAttribute('data-active') === '1';
        try {
          tog.disabled = true;
          const res = await fetch(`/admin/blocked-customers/${id}`, {
            method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ active: !cur })
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo actualizar');
          await fetchBlocked();
        } catch (err) {
          toast && toast(err.message || 'Error');
        } finally {
          tog.disabled = false;
        }
      }
    });
  }
  
  // Payments config
  const pmBank = document.getElementById('pm-bank');
  const pmName = document.getElementById('pm-name');
  const pmPhone = document.getElementById('pm-phone');
  const pmId = document.getElementById('pm-id');
  const binEmail = document.getElementById('binance-email');
  const binPhone = document.getElementById('binance-phone');
  const btnSavePayments = document.getElementById('btn-save-payments');
  const pmImage = document.getElementById('pm-image');
  const binImage = document.getElementById('binance-image');
  const binAutoEnabled = document.getElementById('binance-auto-enabled');
  const binAutoNote = document.getElementById('binance-auto-note');
  const paymentVerificationProvider = document.getElementById('payment-verification-provider');
  const pabiloAutoVerifyEnabled = document.getElementById('pabilo-auto-verify-enabled');
  const pabiloMethod = document.getElementById('pabilo-method');
  const pabiloApiKey = document.getElementById('pabilo-api-key');
  const pabiloPmUserBankId = document.getElementById('pabilo-pm-user-bank-id');
  const pabiloBinanceUserBankId = document.getElementById('pabilo-binance-user-bank-id');
  const pabiloBaseUrl = document.getElementById('pabilo-base-url');
  const pabiloDefaultMovementType = document.getElementById('pabilo-default-movement-type');
  const pabiloTimeoutSeconds = document.getElementById('pabilo-timeout-seconds');
  const pabiloEnforceMethod = document.getElementById('pabilo-enforce-method');
  const pabiloVerifyBox = document.getElementById('pabilo-verify-box');
  const ubiiVerifyBox = document.getElementById('ubii-verify-box');
  const ubiiMethod = document.getElementById('ubii-method');
  const ubiiTextField = document.getElementById('ubii-text-field');
  const ubiiAmountRegex = document.getElementById('ubii-amount-regex');
  const ubiiReferenceRegex = document.getElementById('ubii-reference-regex');
  const ubiiWebhookSecret = document.getElementById('ubii-webhook-secret');
  const ubiiWebhookPath = document.getElementById('ubii-webhook-path');
  const payMethodSelect = document.getElementById('pay-method-select');
  const pmSection = document.getElementById('pm-section');
  const binSection = document.getElementById('binance-section');
  let activePayMethodView = (payMethodSelect && payMethodSelect.value) ? payMethodSelect.value : 'pm';

  function showPaySection(which) {
    const raw = which != null ? which : (payMethodSelect && payMethodSelect.value);
    const val = (raw || '').toLowerCase();
    if (!val) {
      if (pmSection) pmSection.style.display = 'none';
      if (binSection) binSection.style.display = 'none';
      return;
    }
    activePayMethodView = val;
    if (payMethodSelect && payMethodSelect.value !== val) {
      payMethodSelect.value = val;
    }
    if (pmSection) pmSection.style.display = (val === 'pm') ? '' : 'none';
    if (binSection) binSection.style.display = (val === 'binance') ? '' : 'none';
  }
  if (payMethodSelect) {
    payMethodSelect.addEventListener('change', () => {
      activePayMethodView = payMethodSelect.value || activePayMethodView || 'pm';
      showPaySection(activePayMethodView);
    });
  }
  if (binAutoEnabled) {
    binAutoEnabled.addEventListener('change', () => {
      if (binAutoNote) binAutoNote.style.display = binAutoEnabled.checked ? '' : 'none';
    });
  }
  function showPaymentVerificationProvider(provider) {
    const value = (provider || '').toLowerCase();
    if (paymentVerificationProvider && paymentVerificationProvider.value !== value) {
      paymentVerificationProvider.value = value;
    }
    if (pabiloVerifyBox) pabiloVerifyBox.style.display = (value === 'pabilo') ? '' : 'none';
    if (ubiiVerifyBox) ubiiVerifyBox.style.display = (value === 'ubii') ? '' : 'none';
  }
  if (paymentVerificationProvider) {
    paymentVerificationProvider.addEventListener('change', () => {
      showPaymentVerificationProvider(paymentVerificationProvider.value || '');
    });
  }
  const inputActiveLoginGame = document.getElementById('active-login-game');
  const btnSaveActiveLoginGame = document.getElementById('btn-save-active-login-game');
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
  const btnCreatePkg = document.getElementById('btn-create-pkg');
  const btnPackagesRefresh = document.getElementById('btn-packages-refresh');
  const pkgList = document.getElementById('pkg-list');
  const pkgSelect = document.getElementById('pkg-select');
  // Stats tab elements
  const statsPkgSelect = document.getElementById('stats-pkg-select');
  const statsItems = document.getElementById('stats-items');
  const statsSummary = document.getElementById('stats-summary');
  const statsTotalAfter = document.getElementById('stats-total-after');
  const statsSummaryTitle = document.getElementById('stats-summary-title');
  const statsSummaryScope = document.getElementById('stats-summary-scope');
  const btnStatsSaveAll = document.getElementById('btn-stats-save-all');
  // Orders elements
  const btnOrdersRefresh = document.getElementById('btn-orders-refresh');
  const ordersList = document.getElementById('orders-list');
  const ordersPagination = document.getElementById('orders-pagination');
  const btnOrdersWdRefresh = document.getElementById('btn-orders-wd-refresh');
  const ordersWdList = document.getElementById('orders-wd-list');
  let ordersCurrentPage = 1;
  const ordersPerPage = 50;
  // Revendedores mapping elements
  const btnRevSync = document.getElementById('btn-rev-sync');
  const btnRevRefresh = document.getElementById('btn-rev-refresh');
  const btnRevSave = document.getElementById('btn-rev-save');
  const revStorePackage = document.getElementById('rev-store-package');
  const revMapList = document.getElementById('rev-map-list');
  let revMappingData = null;

  async function fetchRevMappingData(storePackageId) {
    if (!revMapList) return;
    revMapList.innerHTML = '<div class="empty-state"><p>Cargando mapeo...</p></div>';
    try {
      const qs = storePackageId ? `?store_package_id=${encodeURIComponent(storePackageId)}` : '';
      const res = await fetch(`/admin/revendedores/mapping-data${qs}`);
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo cargar mapeo');
      revMappingData = data;
      renderRevMapping();
    } catch (e) {
      revMapList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
    }
  }

  function renderRevMapping() {
    if (!revMapList || !revStorePackage || !revMappingData) return;
    const pkgs = Array.isArray(revMappingData.store_packages) ? revMappingData.store_packages : [];
    const items = Array.isArray(revMappingData.store_items) ? revMappingData.store_items : [];
    const remoteCatalog = Array.isArray(revMappingData.remote_catalog) ? revMappingData.remote_catalog : [];

    revStorePackage.innerHTML = '<option value="">— Selecciona un juego —</option>';
    pkgs.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = String(p.id);
      opt.textContent = `${p.name || ('Juego #' + p.id)}`;
      if (parseInt(p.id, 10) === parseInt(revMappingData.selected_store_package_id || 0, 10)) {
        opt.selected = true;
      }
      revStorePackage.appendChild(opt);
    });

    const hasSelectedPackage = !!(revMappingData.selected_store_package_id && parseInt(revMappingData.selected_store_package_id, 10) > 0);
    if (!items.length) {
      if (!hasSelectedPackage) {
        revMapList.innerHTML = '<div class="empty-state"><h3>Selecciona un juego</h3><p>Primero elige un juego de InefableStore para mostrar sus ítems y mapearlos.</p></div>';
      } else {
        revMapList.innerHTML = '<div class="empty-state"><h3>Sin ítems</h3><p>Este juego no tiene ítems activos para mapear.</p></div>';
      }
      return;
    }

    let html = '';
    items.forEach((it) => {
      const mapping = it.mapping || null;
      const mappedCatalogId = remoteCatalog.find((r) => {
        if (!mapping) return false;
        return parseInt(r.remote_package_id, 10) === parseInt(mapping.remote_package_id, 10)
          && parseInt(r.remote_product_id || 0, 10) === parseInt(mapping.remote_product_id || 0, 10);
      })?.catalog_id;

      html += `
        <div class="order-card rev-map-row" data-store-item-id="${it.id}">
          <div class="order-head">
            <div>
              <div class="order-id">${it.title || ('Item #' + it.id)}</div>
              <div class="order-meta">
                <span>ID ${it.id}</span>
                <span>USD ${Number(it.price || 0).toFixed(2)}</span>
              </div>
            </div>
          </div>
          <div class="row-actions" style="display:grid; gap:8px;">
            <select class="input rev-catalog-select" data-store-item-id="${it.id}">
              <option value="">Manual (sin mapeo automático)</option>
              ${(() => {
                const groups = {};
                remoteCatalog.forEach((rc) => {
                  const gName = (rc.remote_product_name || '').trim() || 'Otro';
                  if (!groups[gName]) groups[gName] = [];
                  groups[gName].push(rc);
                });
                return Object.keys(groups).sort().map((gName) => {
                  const opts = groups[gName].map((rc) => {
                    const selected = mappedCatalogId && parseInt(mappedCatalogId, 10) === parseInt(rc.catalog_id, 10) ? 'selected' : '';
                    const pkgName = (rc.remote_package_name || '').trim() || ('Paquete ' + rc.remote_package_id);
                    const priceTag = rc.price != null ? ` ($${Number(rc.price).toFixed(2)})` : '';
                    return `<option value="${rc.catalog_id}" ${selected}>${pkgName}${priceTag}</option>`;
                  }).join('');
                  return `<optgroup label="${gName}">${opts}</optgroup>`;
                }).join('');
              })()}
            </select>
            <label style="display:flex; align-items:center; gap:8px; font-size:13px; color:#cbd5e1;">
              <input type="checkbox" class="rev-auto-enabled" data-store-item-id="${it.id}" ${(mapping && mapping.auto_enabled) ? 'checked' : ''}>
              Activar recarga automática para este ítem
            </label>
          </div>
        </div>
      `;
    });
    revMapList.innerHTML = html;
  }

  async function syncRevCatalog() {
    const res = await fetch('/admin/revendedores/sync', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo sincronizar catálogo');
    return data;
  }

  async function saveRevMappings() {
    if (!revMapList) return;
    const rows = Array.from(revMapList.querySelectorAll('.rev-map-row'));
    const entries = rows.map((row) => {
      const storeItemId = parseInt(row.getAttribute('data-store-item-id') || '0', 10);
      const sel = row.querySelector('.rev-catalog-select');
      const chk = row.querySelector('.rev-auto-enabled');
      return {
        store_item_id: storeItemId,
        catalog_id: sel ? (sel.value || '') : '',
        auto_enabled: !!(chk && chk.checked),
      };
    }).filter((x) => x.store_item_id > 0);

    const res = await fetch('/admin/revendedores/mappings/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entries }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo guardar mapeo');
    return data;
  }
  // Affiliates elements
  const btnAffRefresh = document.getElementById('btn-aff-refresh');
  const affForm = document.getElementById('aff-form');
  const affName = document.getElementById('aff-name');
  const affEmail = document.getElementById('aff-email');
  const affCode = document.getElementById('aff-code');
  const affSecondaryCode = document.getElementById('aff-secondary-code');
  const affPass = document.getElementById('aff-pass');
  const affDiscount = document.getElementById('aff-discount');
  const affCommission = document.getElementById('aff-commission');
  const affScope = document.getElementById('aff-scope');
  const affPkgSelect = document.getElementById('aff-pkg-select');
  const affBalance = document.getElementById('aff-balance');
  const affActive = document.getElementById('aff-active');
  const btnAffCreate = document.getElementById('btn-aff-create');
  const affList = document.getElementById('aff-list');
  const btnAffWdRefresh = document.getElementById('btn-aff-wd-refresh');
  const affWdList = document.getElementById('aff-wd-list');
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

  // =====================
  // Config: active login game get/set
  // =====================
  async function fetchActiveLoginGame() {
    try {
      const res = await fetch('/admin/config/active_login_game');
      const data = await res.json();
      if (data && data.ok && inputActiveLoginGame) {
        inputActiveLoginGame.value = (data.active_login_game_id || '').toString();
      }
      window.fetchActiveLoginGame = fetchActiveLoginGame;
    } catch (_) { /* ignore */ }
  }

  async function saveActiveLoginGame() {
    const payload = { active_login_game_id: inputActiveLoginGame ? (inputActiveLoginGame.value || '').trim() : '' };
    const res = await fetch('/admin/config/active_login_game', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar');
    }
    return res.json();
  }
  

  // Determine position to insert while dragging
  function getDragAfterElement(container, mouseY) {
    const els = [...container.querySelectorAll('.pkg-card:not(.dragging)')];
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
    const ids = Array.from(document.querySelectorAll('#pkg-list .pkg-card'))
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
        syncDropdown(inputMidBanner);
      }
      window.fetchMidBanner = fetchMidBanner;
    } catch (_) { /* ignore */ }
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

  async function fetchThanksImage() {
    try {
      const res = await fetch('/admin/config/thanks_image');
      const data = await res.json();
      if (inputThanksImage) {
        inputThanksImage.value = (data && data.thanks_image_path) || '';
        syncDropdown(inputThanksImage);
      }
      window.fetchThanksImage = fetchThanksImage;
    } catch (_) { /* ignore */ }
  }

  async function saveThanksImage() {
    if (!inputThanksImage) return;
    const thanks_image_path = (inputThanksImage.value || '').trim();
    const res = await fetch('/admin/config/thanks_image', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ thanks_image_path })
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
      affWdList.innerHTML = '<div class="empty-state"><h3>Sin solicitudes</h3><p>Cuando los afiliados pidan retiro aparecer\u00e1n aqu\u00ed.</p></div>';
      return;
    }
    const fmtUSD = (n) => {
      try { return Number(n||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); } catch(_) { return `$${n}`; }
    };
    items.forEach(r => {
      const tile = document.createElement('div');
      tile.className = 'aff-wd-card';
      const when = new Date(r.created_at).toLocaleString();
      const statusCls = r.status === 'approved' ? 'aff-status--active' : r.status === 'rejected' ? 'aff-status--inactive' : 'aff-status--pending';
      const statusTxt = r.status === 'approved' ? 'Aprobado' : r.status === 'rejected' ? 'Rechazado' : 'Pendiente';
      let payDetails = '';
      if (r.method === 'pm') {
        payDetails = `<div class="aff-meta-item"><span class="aff-meta-label">Banco</span><span class="aff-meta-value">${r.pm_bank || '-'}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Titular</span><span class="aff-meta-value">${r.pm_name || '-'}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Tel\u00e9fono</span><span class="aff-meta-value">${r.pm_phone || '-'}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">C\u00e9dula</span><span class="aff-meta-value">${r.pm_id || '-'}</span></div>`;
      } else if (r.method === 'binance') {
        payDetails = `<div class="aff-meta-item"><span class="aff-meta-label">Email</span><span class="aff-meta-value">${r.binance_email || '-'}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Tel\u00e9fono</span><span class="aff-meta-value">${r.binance_phone || '-'}</span></div>`;
      } else if (r.method === 'zinli') {
        payDetails = `<div class="aff-meta-item"><span class="aff-meta-label">Email</span><span class="aff-meta-value">${r.zinli_email || '-'}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Tag</span><span class="aff-meta-value">${r.zinli_tag || '-'}</span></div>`;
      }
      tile.innerHTML = `
        <div class="aff-wd-head">
          <div class="aff-wd-info">
            <div class="aff-wd-name">${r.affiliate_name || 'Afiliado'}</div>
            <span class="aff-status ${statusCls}">${statusTxt}</span>
          </div>
          <div class="aff-wd-amount">${fmtUSD(r.amount_usd)}</div>
        </div>
        <div class="aff-card-meta">
          <div class="aff-meta-item"><span class="aff-meta-label">M\u00e9todo</span><span class="aff-meta-value">${(r.method || '').toUpperCase()}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Fecha</span><span class="aff-meta-value">${when}</span></div>
          ${payDetails}
        </div>
        ${r.status === 'pending' ? `<div class="aff-wd-actions">
          <button class="btn primary btn-wd-approve" data-id="${r.id}">Aprobar</button>
          <button class="btn btn-wd-reject" data-id="${r.id}">Rechazar</button>
        </div>` : ''}
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
        applyPaymentsData(data);
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
      binance_phone: binPhone ? binPhone.value.trim() : '',
      pm_image_path: pmImage ? pmImage.value.trim() : '',
      binance_image_path: binImage ? binImage.value.trim() : '',
      binance_auto_enabled: binAutoEnabled ? binAutoEnabled.checked : false,
      payment_verification_provider: paymentVerificationProvider ? paymentVerificationProvider.value : '',
      pabilo_auto_verify_enabled: pabiloAutoVerifyEnabled ? pabiloAutoVerifyEnabled.checked : false,
      pabilo_method: pabiloMethod ? pabiloMethod.value : 'pm',
      pabilo_api_key: pabiloApiKey ? pabiloApiKey.value.trim() : '',
      pabilo_pm_user_bank_id: pabiloPmUserBankId ? pabiloPmUserBankId.value.trim() : '',
      pabilo_binance_user_bank_id: pabiloBinanceUserBankId ? pabiloBinanceUserBankId.value.trim() : '',
      pabilo_base_url: pabiloBaseUrl ? pabiloBaseUrl.value.trim() : '',
      pabilo_default_movement_type: pabiloDefaultMovementType ? pabiloDefaultMovementType.value : '',
      pabilo_timeout_seconds: pabiloTimeoutSeconds ? pabiloTimeoutSeconds.value.trim() : '30',
      pabilo_enforce_method: pabiloEnforceMethod ? pabiloEnforceMethod.checked : true,
      ubii_method: ubiiMethod ? ubiiMethod.value : 'pm',
      ubii_text_field: ubiiTextField ? ubiiTextField.value.trim() : 'texto',
      ubii_amount_regex: ubiiAmountRegex ? ubiiAmountRegex.value.trim() : 'Bs\\.\\s*([\\d\\.,]+)',
      ubii_reference_regex: ubiiReferenceRegex ? ubiiReferenceRegex.value.trim() : 'referencia\\s+(\\d+)',
      ubii_webhook_secret: ubiiWebhookSecret ? ubiiWebhookSecret.value.trim() : ''
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
    return res.json();
  }

  function applyPaymentsData(data) {
    if (!data) return;
    if (pmBank) pmBank.value = data.pm_bank || '';
    if (pmName) pmName.value = data.pm_name || '';
    if (pmPhone) pmPhone.value = data.pm_phone || '';
    if (pmId) pmId.value = data.pm_id || '';
    if (binEmail) binEmail.value = data.binance_email || '';
    if (binPhone) binPhone.value = data.binance_phone || '';
    if (pmImage) { pmImage.value = data.pm_image_path || ''; syncDropdown(pmImage); }
    if (binImage) { binImage.value = data.binance_image_path || ''; syncDropdown(binImage); }
    if (binAutoEnabled) {
      binAutoEnabled.checked = (data.binance_auto_enabled === '1' || data.binance_auto_enabled === 1 || data.binance_auto_enabled === true);
      if (binAutoNote) binAutoNote.style.display = binAutoEnabled.checked ? '' : 'none';
    }
    if (paymentVerificationProvider) paymentVerificationProvider.value = (data.payment_verification_provider || '').toLowerCase();
    if (pabiloAutoVerifyEnabled) pabiloAutoVerifyEnabled.checked = (data.pabilo_auto_verify_enabled === '1' || data.pabilo_auto_verify_enabled === 1 || data.pabilo_auto_verify_enabled === true);
    if (pabiloMethod) pabiloMethod.value = (data.pabilo_method || 'pm').toLowerCase() === 'binance' ? 'binance' : 'pm';
    if (pabiloApiKey) pabiloApiKey.value = data.pabilo_api_key || '';
    if (pabiloPmUserBankId) pabiloPmUserBankId.value = data.pabilo_pm_user_bank_id || data.pabilo_user_bank_id || '';
    if (pabiloBinanceUserBankId) pabiloBinanceUserBankId.value = data.pabilo_binance_user_bank_id || '';
    if (pabiloBaseUrl) pabiloBaseUrl.value = data.pabilo_base_url || '';
    if (pabiloDefaultMovementType) pabiloDefaultMovementType.value = data.pabilo_default_movement_type || '';
    if (pabiloTimeoutSeconds) pabiloTimeoutSeconds.value = data.pabilo_timeout_seconds || '30';
    if (pabiloEnforceMethod) pabiloEnforceMethod.checked = !(data.pabilo_enforce_method === '0' || data.pabilo_enforce_method === 0 || data.pabilo_enforce_method === false);
    if (ubiiMethod) ubiiMethod.value = (data.ubii_method || 'pm').toLowerCase() === 'binance' ? 'binance' : 'pm';
    if (ubiiTextField) ubiiTextField.value = data.ubii_text_field || 'texto';
    if (ubiiAmountRegex) ubiiAmountRegex.value = data.ubii_amount_regex || 'Bs\\.\\s*([\\d\\.,]+)';
    if (ubiiReferenceRegex) ubiiReferenceRegex.value = data.ubii_reference_regex || 'referencia\\s+(\\d+)';
    if (ubiiWebhookSecret) ubiiWebhookSecret.value = data.ubii_webhook_secret || '';
    if (ubiiWebhookPath) ubiiWebhookPath.value = data.ubii_webhook_path || '/webhook-ubii';
    showPaymentVerificationProvider((data.payment_verification_provider || '').toLowerCase());
    showPaySection((payMethodSelect && payMethodSelect.value) || activePayMethodView || 'pm');
  }
  // Ensure global symbol exists for any external references
  window.savePayments = savePayments;

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

  // Wire tabs click (if not already wired by server)
  if (tabs && tabs.length) {
    tabs.forEach(btn => {
      btn.addEventListener('click', async () => {
        tabs.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const target = btn.dataset.target;
        activateTab(target);
        // Lazy-load per tab
        if (target === '#tab-orders') { fetchOrders(); fetchAffWithdrawalsForOrders(); }
        if (target === '#tab-images') { if (gallery) await fetchImages(); }
        if (target === '#tab-config') { fetchSiteName(); fetchLogo(); fetchMidBanner(); fetchThanksImage(); fetchActiveLoginGame(); fetchPayments(); }
        if (target === '#tab-affiliates') { fetchAffiliates(); fetchAffWithdrawals(); populatePackagesSelect(); }
        if (target === '#tab-packages') { fetchPackages(); }
        if (target === '#tab-rev-map') { fetchRevMappingData(revStorePackage ? revStorePackage.value : ''); }
        if (target === '#tab-stats') { fetchStatsPackages(); fetchGlobalStatsSummary(); }
        if (target === '#tab-blocked') { fetchBlocked(); }
      });
    });
  }

  if (revStorePackage) {
    revStorePackage.addEventListener('change', () => {
      fetchRevMappingData(revStorePackage.value || '');
    });
  }

  if (btnRevRefresh) {
    btnRevRefresh.addEventListener('click', () => {
      fetchRevMappingData(revStorePackage ? revStorePackage.value : '');
    });
  }

  if (btnRevSync) {
    btnRevSync.addEventListener('click', async () => {
      try {
        btnRevSync.disabled = true;
        const data = await syncRevCatalog();
        const gamesInfo = data.games ? Object.entries(data.games).map(([g, c]) => `${g}: ${c}`).join('\n') : '';
        toast(`Sincronizado: ${data.created || 0} nuevos, ${data.updated || 0} actualizados, ${data.active_in_db || 0} activos en DB\n${gamesInfo}`);
        await fetchRevMappingData(revStorePackage ? revStorePackage.value : '');
      } catch (e) {
        toast(e.message || 'Error al sincronizar');
      } finally {
        btnRevSync.disabled = false;
      }
    });
  }

  if (btnRevSave) {
    btnRevSave.addEventListener('click', async () => {
      try {
        btnRevSave.disabled = true;
        await saveRevMappings();
        toast('Mapeo guardado');
        await fetchRevMappingData(revStorePackage ? revStorePackage.value : '');
      } catch (e) {
        toast(e.message || 'Error al guardar mapeo');
      } finally {
        btnRevSave.disabled = false;
      }
    });
  }

  // =====================
  // Stats: helpers
  // =====================
  function fmtUSD(n) {
    try { return Number(n || 0).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }); }
    catch (_) { return `$${n}`; }
  }

  function renderStatsSummary(summary, scopeLabel, titleLabel) {
    if (!statsSummary || !statsTotalAfter) return;
    const statsCommEl = document.getElementById('stats-total-commission');
    const s = summary || {};
    statsSummary.style.display = 'block';
    if (statsSummaryTitle) statsSummaryTitle.textContent = titleLabel || 'Ganancias semanales';
    if (statsSummaryScope) statsSummaryScope.textContent = scopeLabel || 'Resumen global de la semana actual';
    statsTotalAfter.textContent = fmtUSD(s.total_profit_after_affiliates_usd || 0);
    if (statsCommEl) statsCommEl.textContent = fmtUSD(s.total_affiliate_commission_usd || 0);
  }

  async function fetchGlobalStatsSummary() {
    if (!statsSummary || !statsTotalAfter) return;
    try {
      const res = await fetch('/admin/stats/summary?period=weekly');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo cargar resumen global');
      renderStatsSummary(data.summary || {}, 'Resumen global de la semana actual', 'Ganancias semanales');
    } catch (e) {
      renderStatsSummary({}, 'Resumen global de la semana actual', 'Ganancias semanales');
    }
    fetchProfitHistory();
  }

  // ---------- Profit History ----------
  async function fetchProfitHistory() {
    const container = document.getElementById('stats-history-list');
    if (!container) return;
    try {
      const res = await fetch('/admin/stats/history');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error');
      const hist = data.history || [];
      if (!hist.length) {
        container.innerHTML = '<div class="empty-state"><p>Sin historial aún.</p></div>';
        return;
      }
      container.innerHTML = '';
      hist.forEach(h => {
        const card = document.createElement('div');
        card.className = 'order-card';
        card.style.marginBottom = '8px';
        card.innerHTML = `
          <div class="order-head" style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div class="order-id" style="font-size:13px;">${h.period_start} → ${h.period_end}</div>
              <div class="order-meta">
                <span>Ganancia: <strong style="color:#10b981;">${fmtUSD(h.profit_usd)}</strong></span>
                <span style="margin-left:12px;">Comisiones: <strong style="color:#f59e0b;">${fmtUSD(h.commission_usd)}</strong></span>
              </div>
            </div>
            <button class="btn btn-delete" data-snap-id="${h.id}" title="Eliminar" style="padding:4px 10px; font-size:16px; cursor:pointer;">✕</button>
          </div>
        `;
        card.querySelector('.btn-delete').addEventListener('click', () => deleteProfitSnapshot(h.id));
        container.appendChild(card);
      });
    } catch (e) {
      container.innerHTML = '<div class="empty-state"><p>Error cargando historial.</p></div>';
    }
  }

  async function deleteProfitSnapshot(id) {
    if (!confirm('¿Eliminar este registro del historial?')) return;
    try {
      const res = await fetch(`/admin/stats/history/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error');
      fetchProfitHistory();
    } catch (e) {
      alert(e.message || 'Error al eliminar');
    }
  }

  async function fetchStatsPackages() {
    if (!statsPkgSelect) return;
    try {
      const res = await fetch('/admin/stats/packages');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar paquetes');
      statsPkgSelect.innerHTML = '<option value="">— Selecciona un paquete —</option>';
      (data.packages || []).forEach(p => {
        const opt = document.createElement('option');
        opt.value = String(p.id);
        opt.textContent = `${p.name} (${p.category || '-'})`;
        statsPkgSelect.appendChild(opt);
      });
      if ((data.packages || []).length === 0) {
        if (statsItems) {
          statsItems.innerHTML = '<div class="empty-state"><h3>Sin paquetes</h3><p>Crea paquetes para ver estadísticas.</p></div>';
        }
        if (statsSummary) statsSummary.style.display = 'none';
      }
    } catch (e) {
      if (statsItems) {
        statsItems.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
      }
      if (statsSummary) statsSummary.style.display = 'none';
    }
  }

  async function fetchStatsForPackage(pkgId) {
    if (!statsItems || !pkgId) return;
    statsItems.innerHTML = '<div class="empty-state"><p>Cargando...</p></div>';
    try {
      const res = await fetch(`/admin/stats/package/${pkgId}?period=weekly`);
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo cargar estadísticas');
      const items = data.items || [];
      if (!items.length) {
        statsItems.innerHTML = '<div class="empty-state"><h3>Sin datos</h3><p>Define una ganancia neta para los ítems de este paquete para que aparezcan aquí.</p></div>'; // texto legacy pero funcional
      } else {
        statsItems.innerHTML = '';
        items.forEach(it => {
          const row = document.createElement('div');
          row.className = 'stats-row';
          row.dataset.itemId = String(it.id);
          row.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid #e2e8f0;">
              <div style="flex:1; min-width:0;">
                <div style="font-weight:600; color:#0f172a; margin-bottom:2px;">${it.title}</div>
                <div style="font-size:12px; color:#64748b; display:flex; flex-wrap:wrap; gap:8px;">
                  <span>Precio web: <strong>${fmtUSD(it.price)}</strong></span>
                  <span>Unidades totales: <strong>${it.qty_total || 0}</strong></span>
                  <span>Sin influencer: <strong>${it.qty_normal || 0}</strong></span>
                  <span>Con influencer: <strong>${it.qty_with_affiliate || 0}</strong></span>
                </div>
              </div>
              <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px; min-width:190px;">
                <label style="font-size:12px; color:#475569;">Costo por unidad (USD)</label>
                <input type="number" step="0.01" min="0" class="stats-profit-input" value="${Number(it.cost_unit_usd || 0).toFixed(2)}" style="width:120px; padding:4px 6px; border:1px solid #cbd5e1; border-radius:4px;" />
                <div style="font-size:11px; color:#ffffff;">Ganancia estándar/unidad: <strong>Con descuento: ${fmtUSD(it.profit_unit_real_avg_usd || 0)}</strong> · <strong>Sin descuento: ${fmtUSD(it.profit_unit_std_usd || 0)}</strong></div>
                <div style="font-size:12px; color:#ffffff;">Ganancia total (semana actual): <strong>${fmtUSD(it.total_profit_net_usd || 0)}</strong></div>
              </div>
            </div>
          `;
          statsItems.appendChild(row);
        });
      }
      const pkgName = ((data.package || {}).name || '').trim();
      const scope = pkgName ? `Resumen semanal de ${pkgName}` : 'Resumen del paquete en la semana actual';
      renderStatsSummary(data.summary || {}, scope, 'Ganancias del paquete');
    } catch (e) {
      statsItems.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
      renderStatsSummary({}, 'Resumen del paquete en la semana actual', 'Ganancias del paquete');
    }
  }

  async function saveItemNetProfit(itemId, value) {
    // Enviar costo por unidad en USD; el backend lo guarda en la columna profit_net_usd
    const payload = { cost_unit_usd: value };
    const res = await fetch(`/admin/package/item/${itemId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let msg = 'No se pudo guardar la ganancia';
      try { const d = await res.json(); msg = d.error || msg; } catch (_) {}
      throw new Error(msg);
    }
  }

  if (statsPkgSelect) {
    statsPkgSelect.addEventListener('change', () => {
      const val = statsPkgSelect.value || '';
      if (!val) {
        if (statsItems) {
          statsItems.innerHTML = '<div class="empty-state"><h3>Sin datos</h3><p>Selecciona un paquete para ver sus estadísticas.</p></div>';
        }
        // Mantener siempre visible el resumen global
        fetchGlobalStatsSummary();
        return;
      }
      fetchStatsForPackage(val);
    });
  }

  if (btnStatsSaveAll) {
    btnStatsSaveAll.addEventListener('click', async () => {
      if (!statsItems) return;
      const cards = statsItems.querySelectorAll('.stats-row');
      if (!cards || !cards.length) {
        toast && toast('No hay ítems para guardar');
        return;
      }
      try {
        btnStatsSaveAll.disabled = true;
        const tasks = [];
        cards.forEach(card => {
          const itemId = card.dataset.itemId;
          const input = card.querySelector('.stats-profit-input');
          if (!itemId || !input) return;
          let val = parseFloat(input.value || '0');
          if (Number.isNaN(val) || val < 0) val = 0;
          tasks.push(saveItemNetProfit(itemId, val));
        });
        if (tasks.length === 0) {
          toast && toast('No hay cambios para guardar');
        } else {
          await Promise.all(tasks);
          toast && toast('Ganancias guardadas');
          if (statsPkgSelect && statsPkgSelect.value) {
            await fetchStatsForPackage(statsPkgSelect.value);
          }
          // Actualizar resumen global después de guardar
          fetchGlobalStatsSummary();
        }
      } catch (err) {
        toast && toast(err.message || 'Error');
      } finally {
        btnStatsSaveAll.disabled = false;
      }
    });
  }

  // =====================
  // Config: site name get/set
  // =====================
  async function fetchSiteName() {
    try {
      const res = await fetch('/admin/config/site_name');
      const data = await res.json();
      if (inputSiteName && data && data.ok) {
        inputSiteName.value = data.site_name || 'InefableStore';
      }
      window.fetchSiteName = fetchSiteName;
    } catch (_) { /* ignore */ }
  }

  async function saveSiteName() {
    if (!inputSiteName) return;
    const site_name = inputSiteName.value.trim();
    if (!site_name) {
      throw new Error('El nombre del sitio no puede estar vacío');
    }
    const res = await fetch('/admin/config/site_name', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site_name })
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt || 'No se pudo guardar');
    }
    return res.json();
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
        syncDropdown(inputLogo);
      }
window.fetchLogo = fetchLogo;
    } catch (_) { /* ignore */ }
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

  if (btnSaveSiteName) {
    btnSaveSiteName.addEventListener('click', async () => {
      try {
        btnSaveSiteName.disabled = true;
        await saveSiteName();
        toast('Nombre del sitio guardado');
      } catch (e) {
        toast(e.message);
      } finally {
        btnSaveSiteName.disabled = false;
      }
    });
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
        fetchSiteName();
        fetchRate();
        fetchPayments();
        fetchMailInfo();
        fetchSessionInfo();
        fetchMidBanner && fetchMidBanner();
        fetchActiveLoginGame();
        hideMailAndSessionSections();
      }
      // If Orders tab is opened, refresh orders
      if (tab.dataset.target === '#tab-orders') {
        fetchOrders();
      }
      // If Packages tab is opened, fetch packages to populate selector and list
      if (tab.dataset.target === '#tab-packages') {
        fetchPackages();
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
  if (document.querySelector('#tab-blocked.active')) { fetchBlocked(); }
  // Do not select a payment method by default on load
  showPaySection();
  // Always hide mail/session blocks (fallback)
  hideMailAndSessionSections();

  // Wire mail test button
  if (btnMailTest) btnMailTest.addEventListener('click', sendMailTest);
  if (btnMailSave) btnMailSave.addEventListener('click', saveMailDestination);
  // If landing on Config, also fetch session/mail info immediately
  if (document.querySelector('#tab-config.active')) { fetchMailInfo(); fetchSessionInfo(); }

  // Wire save active login game
  if (btnSaveActiveLoginGame) {
    btnSaveActiveLoginGame.addEventListener('click', async () => {
      try {
        btnSaveActiveLoginGame.disabled = true;
        const resp = await saveActiveLoginGame();
        if (resp && resp.ok) {
          toast('Juego activo guardado');
          await fetchActiveLoginGame();
        } else {
          toast('Guardado, pero respuesta inesperada');
        }
      } catch (e) {
        toast(e.message || 'No se pudo guardar');
      } finally {
        btnSaveActiveLoginGame.disabled = false;
      }
    });
  }

  // =====================
  // Config: Blood Strike package ID (Smile.One verification)
  // =====================
  const inputBsPackageId = document.getElementById('bs-package-id');
  const inputBsServerId = document.getElementById('bs-server-id');
  const btnSaveBsPackageId = document.getElementById('btn-save-bs-package-id');

  async function fetchBsPackageId() {
    try {
      const [res1, res2] = await Promise.all([
        fetch('/admin/config/bs_package_id'),
        fetch('/admin/config/bs_server_id')
      ]);
      const data1 = await res1.json();
      const data2 = await res2.json();
      if (res1.ok && data1 && data1.ok && inputBsPackageId) {
        inputBsPackageId.value = data1.bs_package_id || '';
      }
      if (res2.ok && data2 && data2.ok && inputBsServerId) {
        inputBsServerId.value = data2.bs_server_id || '';
      }
    } catch (_) { /* ignore */ }
  }

  async function saveBsPackageId() {
    const pkgVal = inputBsPackageId ? String(inputBsPackageId.value || '').trim() : '';
    const srvVal = inputBsServerId ? String(inputBsServerId.value || '').trim() : '';
    await Promise.all([
      fetch('/admin/config/bs_package_id', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bs_package_id: pkgVal })
      }),
      fetch('/admin/config/bs_server_id', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bs_server_id: srvVal })
      })
    ]);
  }

  if (btnSaveBsPackageId) {
    btnSaveBsPackageId.addEventListener('click', async () => {
      try {
        btnSaveBsPackageId.disabled = true;
        await saveBsPackageId();
        toast('ID de paquete Blood Strike guardado');
      } catch (e) {
        toast(e.message || 'Error');
      } finally {
        btnSaveBsPackageId.disabled = false;
      }
    });
  }

  fetchBsPackageId();

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
    console.log('[images] uploadImage called for:', file.name);
    const fd = new FormData();
    fd.append('image', file);
    const res = await fetch('/admin/images/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo subir');
    console.log('[images] uploadImage completed for:', file.name);
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
      console.log('[images] onFileChange triggered, files:', fileInput.files?.length || 0, 'processingChange:', processingChange, 'isUploading:', isUploading);
      if (isUploading) { console.log('[images] change ignored: upload in progress'); return; }
      // Prevent multiple executions with a flag
      if (processingChange) { console.log('[images] change ignored: already processing'); return; }
      processingChange = true;
      console.log('[images] starting processing, setting processingChange=true');
      const files = Array.from(fileInput.files || []);
      const sig = files.map(f => `${f.name}|${f.size}|${f.lastModified}`).join(',');
      if (sig && sig === lastFilesSig) {
        console.log('[images] duplicate change ignored (same selection)');
        fileInput.value = '';
        processingChange = false;
        return;
      }
      lastFilesSig = sig;
      if (!files.length) {
        processingChange = false;
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
          console.log(`[images] loop iteration ${i+1}/${unique.length} for ${f.name}`);
          toast(`Subiendo ${i+1}/${unique.length}: ${f.name}`);
          await uploadImage(f);
        }
        await refreshGallery();
        toast(`Se subieron ${unique.length} archivo(s)`, 'success');
      } catch (e) {
        toast(e.message || 'Error al subir', 'error');
      } finally {
        console.log('[images] entering finally block, resetting processingChange');
        btnUpload.disabled = false;
        fileInput.value = '';
        isUploading = false;
        processingChange = false;
        console.log('[images] processingChange reset to false');
        setTimeout(() => { lastOpenAt = 0; lastFilesSig = ''; }, 200);
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
      if (affPkgSelect) {
        const keep = affPkgSelect.querySelector('option[value=""]');
        affPkgSelect.innerHTML = '';
        if (keep) { keep.selected = true; affPkgSelect.appendChild(keep); }
        pkgs.forEach(p => {
          const opt = document.createElement('option');
          opt.value = String(p.id);
          opt.textContent = `${p.name || 'Paquete'} (ID ${p.id})`;
          affPkgSelect.appendChild(opt);
        });
      }
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
    if (!items || items.length === 0) {
      affList.innerHTML = '<div class="empty-state"><h3>Sin afiliados</h3><p>Crea uno nuevo para comenzar.</p></div>';
      return;
    }
    const fmtUSD = (n) => {
      try { return Number(n||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); } catch(_) { return `$${n}`; }
    };
    items.forEach(u => {
      const card = document.createElement('div');
      card.className = 'aff-card';
      const statusCls = u.active ? 'aff-status--active' : 'aff-status--inactive';
      const statusTxt = u.active ? 'Activo' : 'Inactivo';
      const scopeTxt = u.scope === 'package' ? `Juego #${u.scope_package_id || '?'}` : 'Todos';
      card.innerHTML = `
        <div class="aff-card-head">
          <div class="aff-card-info">
            <div class="aff-card-name">${u.name || 'Sin nombre'}</div>
            <span class="aff-status ${statusCls}">${statusTxt}</span>
          </div>
          <div class="aff-card-balance">${fmtUSD(u.balance)}</div>
        </div>
        <div class="aff-card-meta">
          <div class="aff-meta-item"><span class="aff-meta-label">C\u00f3digo</span><span class="aff-meta-value">${u.code}</span></div>
          ${u.secondary_code ? `<div class="aff-meta-item"><span class="aff-meta-label">Adicional</span><span class="aff-meta-value">${u.secondary_code}</span></div>` : ''}
          <div class="aff-meta-item"><span class="aff-meta-label">Email</span><span class="aff-meta-value">${u.email || '-'}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Alcance</span><span class="aff-meta-value">${scopeTxt}</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Descuento</span><span class="aff-meta-value">${u.discount_percent || 0}%</span></div>
          <div class="aff-meta-item"><span class="aff-meta-label">Comisi\u00f3n</span><span class="aff-meta-value">${u.commission_percent || 0}%</span></div>
        </div>
        <details class="aff-card-edit">
          <summary class="aff-edit-toggle">Editar</summary>
          <div class="aff-edit-body">
            <div class="aff-edit-grid">
              <div class="aff-edit-field"><label>Nombre</label><input class="aff-edit-name" type="text" value="${u.name || ''}" /></div>
              <div class="aff-edit-field"><label>Email</label><input class="aff-edit-email" type="email" value="${u.email || ''}" /></div>
              <div class="aff-edit-field"><label>C\u00f3digo</label><input class="aff-edit-code" type="text" value="${u.code || ''}" /></div>
              <div class="aff-edit-field"><label>C\u00f3digo adicional</label><input class="aff-edit-secondary-code" type="text" value="${u.secondary_code || ''}" /></div>
              <div class="aff-edit-field"><label>Nueva contrase\u00f1a</label><input class="aff-edit-pass" type="password" value="" placeholder="Dejar vac\u00edo para no cambiar" /></div>
              <div class="aff-edit-field"><label>Saldo (USD)</label><input class="aff-edit-balance" type="number" step="0.01" min="0" value="${u.balance || 0}" /></div>
            </div>
            <div class="aff-edit-grid aff-edit-grid--2">
              <div class="aff-edit-field"><label>Descuento al usuario %</label><input class="aff-edit-discount" type="number" step="0.1" min="0" max="100" value="${u.discount_percent || 0}" /></div>
              <div class="aff-edit-field"><label>Ganancia afiliado %</label><input class="aff-edit-commission" type="number" step="0.1" min="0" max="100" value="${u.commission_percent || 0}" /></div>
            </div>
            <div class="aff-edit-grid aff-edit-grid--3">
              <div class="aff-edit-field"><label>Alcance</label>
                <select class="aff-edit-scope">
                  <option value="all" ${u.scope !== 'package' ? 'selected' : ''}>Todos</option>
                  <option value="package" ${u.scope === 'package' ? 'selected' : ''}>Solo juego</option>
                </select>
              </div>
              <div class="aff-edit-field"><label>ID Juego</label><input class="aff-edit-pkgid" type="number" min="1" value="${u.scope_package_id || ''}" placeholder="Si aplica" /></div>
              <div class="aff-edit-field aff-edit-field--check"><label>Activo</label><label class="aff-toggle"><input class="aff-edit-active" type="checkbox" ${u.active ? 'checked' : ''} /><span class="aff-toggle-label">${u.active ? 'S\u00ed' : 'No'}</span></label></div>
            </div>
            <div class="aff-edit-actions">
              <button class="btn primary btn-aff-save" data-id="${u.id}" type="button">Guardar</button>
              <button class="btn btn-aff-del" data-id="${u.id}" type="button">Eliminar</button>
            </div>
          </div>
        </details>
      `;
      affList.appendChild(card);
    });
  }

  async function createAffiliate() {
    const payload = {
      name: (affName && affName.value.trim()) || '',
      email: (affEmail && affEmail.value.trim()) || '',
      code: (affCode && affCode.value.trim()) || '',
      secondary_code: (affSecondaryCode && affSecondaryCode.value.trim()) || '',
      password: (affPass && affPass.value) || '',
      discount_percent: (affDiscount && parseFloat(affDiscount.value || '0')) || 0,
      commission_percent: (affCommission && parseFloat(affCommission.value || '0')) || 0,
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
        if (affSecondaryCode) affSecondaryCode.value = '';
        if (affPass) affPass.value = '';
        if (affDiscount) affDiscount.value = '';
        if (affCommission) affCommission.value = '';
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
        const container = btnSave.closest('.aff-card');
        const name = container.querySelector('.aff-edit-name')?.value.trim() || '';
        const code = container.querySelector('.aff-edit-code')?.value.trim() || '';
        const secondary_code = container.querySelector('.aff-edit-secondary-code')?.value.trim() || '';
        const email = container.querySelector('.aff-edit-email')?.value.trim() || '';
        const password = container.querySelector('.aff-edit-pass')?.value || '';
        const discount_percent = parseFloat(container.querySelector('.aff-edit-discount')?.value || '0') || 0;
        const commission_percent = parseFloat(container.querySelector('.aff-edit-commission')?.value || '0') || 0;
        const scope = container.querySelector('.aff-edit-scope')?.value || 'all';
        const scope_package_id = container.querySelector('.aff-edit-pkgid')?.value ? parseInt(container.querySelector('.aff-edit-pkgid').value, 10) : null;
        const balance = parseFloat(container.querySelector('.aff-edit-balance')?.value || '0') || 0;
        const active = !!container.querySelector('.aff-edit-active')?.checked;
        try {
          btnSave.disabled = true;
          const res = await fetch(`/admin/special/users/${id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, code, secondary_code, email, password, discount_percent, commission_percent, scope, scope_package_id, balance, active })
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
  function renderOrdersPagination(meta) {
    if (!ordersPagination) return;
    const pagination = meta || {};
    const totalPages = Math.max(parseInt(pagination.total_pages || 1, 10) || 1, 1);
    const page = Math.min(Math.max(parseInt(pagination.page || 1, 10) || 1, 1), totalPages);
    const totalOrders = parseInt(pagination.total_orders || 0, 10) || 0;

    if (totalOrders <= ordersPerPage) {
      ordersPagination.innerHTML = '';
      return;
    }

    const pageButtons = [];
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, start + 4);
    for (let current = start; current <= end; current += 1) {
      pageButtons.push(`
        <button class="btn btn-orders-page${current === page ? ' primary' : ''}" data-page="${current}" type="button" ${current === page ? 'disabled' : ''}>${current}</button>
      `);
    }

    ordersPagination.innerHTML = `
      <button class="btn btn-orders-page-nav" data-page="${page - 1}" type="button" ${page <= 1 ? 'disabled' : ''}>Anterior</button>
      <span style="color:#cbd5e1;font-size:13px;">Página ${page} de ${totalPages} · ${totalOrders} órdenes</span>
      ${pageButtons.join('')}
      <button class="btn btn-orders-page-nav" data-page="${page + 1}" type="button" ${page >= totalPages ? 'disabled' : ''}>Siguiente</button>
    `;
  }

  async function fetchOrders(page = ordersCurrentPage) {
    try {
      const normalizedPage = Math.max(parseInt(page || 1, 10) || 1, 1);
      const res = await fetch(`/admin/orders?page=${normalizedPage}&per_page=${ordersPerPage}`);
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo listar');
      const pagination = data.pagination || {};
      ordersCurrentPage = Math.max(parseInt(pagination.page || normalizedPage, 10) || normalizedPage, 1);
      renderOrders(data.orders || []);
      renderOrdersPagination(pagination);
    } catch (e) {
      if (ordersList) ordersList.innerHTML = `<div class="empty-state"><p>${e.message || 'Error'}</p></div>`;
      if (ordersPagination) ordersPagination.innerHTML = '';
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
    items.forEach(o => {
      const tile = document.createElement('div');
      tile.className = 'order-tile';
      tile.setAttribute('data-customer-name', o.customer_name || '');
      const autoSummary = o.auto_recharge_summary || {};
      const payVerify = o.payment_verify || {};
      const pabiloRequest = o.pabilo_request || {};
      const pabiloEligibility = o.pabilo_eligibility || {};
      const totalAutoUnits = parseInt(autoSummary.total_units || 0, 10) || 0;
      const completedAutoUnits = parseInt(autoSummary.completed_units || 0, 10) || 0;
      const processingAutoUnits = parseInt(autoSummary.processing_units || 0, 10) || 0;
      const retryableAutoUnits = parseInt(autoSummary.retryable_units || 0, 10) || 0;
      const isAutoMapped = totalAutoUnits > 0;
      const autoActionUnits = retryableAutoUnits > 0 ? retryableAutoUnits : totalAutoUnits;
      const approveLabel = isAutoMapped
        ? `${completedAutoUnits > 0 ? 'Continuar' : 'Procesar'} ${autoActionUnits} recarga${autoActionUnits === 1 ? '' : 's'}`
        : 'Aprobar';
      const approveDisabled = o.status !== 'pending' || (isAutoMapped && processingAutoUnits > 0 && retryableAutoUnits === 0);
      const rejectDisabled = o.status !== 'pending' || (isAutoMapped && processingAutoUnits > 0);
      const autoSummaryText = isAutoMapped
        ? `Auto: ${completedAutoUnits}/${totalAutoUnits} completadas${processingAutoUnits ? ` · ${processingAutoUnits} verificando` : ''}${retryableAutoUnits ? ` · ${retryableAutoUnits} por reenviar` : ''}`
        : '';
      const pabiloEligible = (typeof pabiloEligibility.eligible === 'boolean')
        ? !!pabiloEligibility.eligible
        : !!o.pabilo_eligible;
      const pabiloVerified = !!payVerify.verified;
      const payProvider = String(payVerify.provider || '').toLowerCase();
      const activeVerifyProvider = String(o.payment_verification_provider_active || '').toLowerCase();
      const payProviderLabel = payProvider === 'ubii' ? 'Ubii' : 'Pabilo';
      const pabiloRequestable = (typeof pabiloRequest.requestable === 'boolean')
        ? !!pabiloRequest.requestable
        : pabiloEligible;
      let pabiloStateText = '';
      let pabiloStateColor = '#cbd5e1';
      if (payProvider === 'ubii') {
        pabiloStateText = pabiloVerified
          ? `Pago verificado en ${payProviderLabel}${payVerify.verification_id ? ` · Ref ${payVerify.verification_id}` : ''}`
          : (payVerify.message ? `${payProviderLabel}: ${payVerify.message}` : '');
        pabiloStateColor = pabiloVerified ? '#6ee7b7' : '#fca5a5';
      } else if (activeVerifyProvider === 'ubii') {
        pabiloStateText = pabiloVerified
          ? `Pago verificado en Ubii${payVerify.verification_id ? ` · Ref ${payVerify.verification_id}` : ''}`
          : 'Ubii activo: esperando webhook con referencia exacta y monto mayor o igual a la orden';
        pabiloStateColor = pabiloVerified ? '#6ee7b7' : '#86efac';
      } else if (pabiloEligible) {
        pabiloStateText = pabiloVerified
          ? `Pago verificado en Pabilo${payVerify.verification_id ? ` · ID ${payVerify.verification_id}` : ''}`
          : `Pago no verificado en Pabilo${payVerify.message ? ` · ${payVerify.message}` : ''}`;
        pabiloStateColor = pabiloVerified ? '#6ee7b7' : '#fca5a5';
      } else if (pabiloRequestable) {
        pabiloStateText = `Solicitud Pabilo permitida${payVerify.message ? ` · ${payVerify.message}` : ''}`;
      } else if (pabiloRequest.reason && pabiloRequest.reason !== 'Pabilo esta desactivado') {
        pabiloStateText = `Pabilo no consulta: ${pabiloRequest.reason}`;
      } else if (pabiloEligibility.reason && pabiloEligibility.reason !== 'Pabilo esta desactivado') {
        pabiloStateText = `Pabilo no aplica: ${pabiloEligibility.reason}`;
      }
      tile.setAttribute('data-is-auto', isAutoMapped ? '1' : '0');
      const when = new Date(o.created_at).toLocaleString();
      const itemsArr = Array.isArray(o.items) ? o.items : [];
      const qtyTotal = itemsArr.length
        ? itemsArr.reduce((sum, it) => sum + parseInt(it.qty||1,10), 0)
        : 1;
      const diam = itemsArr.length
        ? itemsArr.map(it => `${parseInt(it.qty||1,10)}x ${fixMb(it.title||'')}`).join(' · ')
        : ((qtyTotal > 1 ? `${qtyTotal}x ` : '') + (fixMb(o.item_title) || ''));
      const amountRounded = Math.round(Number(o.amount||0));
      const amountDisp = `${amountRounded} ${o.currency || ''}`.trim();
      const affiliateTag = o.affiliate_code ? ` <span class="aff-code">(${fixMb(o.affiliate_code)})</span>` : '';
      const statusIcon = o.status === 'approved' ? 'Aprobado' : o.status === 'rejected' ? 'Rechazado' : o.status === 'delivered' ? 'Entregado' : 'Pendiente';
      const statusClass = (o.status === 'approved' || o.status === 'delivered') ? 'ok' : o.status === 'rejected' ? 'rej' : 'pend';
      const playerId = fixMb(o.customer_id || '-');
      const txRef = fixMb(o.reference || '-');
      const gameName = fixMb(o.package_name || '');
      const playerNick = fixMb(o.customer_name || '');
      const isGift = (o.package_category || '').toLowerCase() === 'gift';
      const canEditReference = o.status === 'pending';
      tile.innerHTML = `
        <div class="row-head">
          <div class="box-left">
            <div class="game-name">${gameName} <span class="state ${statusClass}">${statusIcon}</span></div>
            <div class="package-name">${diam || ''}</div>
            ${playerNick && playerNick !== (o.name||'').trim() && playerNick !== (o.email||'').trim() ? `<div class="package-name" style="color:#86efac;font-size:12px;">👤 ${playerNick}</div>` : ''}
            ${autoSummaryText ? `<div class="package-name" style="color:#93c5fd;font-size:12px;">${autoSummaryText}</div>` : ''}
            ${pabiloStateText ? `<div class="package-name" style="color:${pabiloStateColor};font-size:12px;">${pabiloStateText}</div>` : ''}
            <div class="quantity-label">Cantidad: <span class="quantity-value">${itemsArr.length ? qtyTotal : 1}</span></div>
            <div class="ref-section">
              <div class="ref-label">REFERENCIA</div>
              <div class="ref-value">${txRef}</div>
              ${canEditReference ? `<button class="btn btn-edit-reference" data-id="${o.id}" type="button" style="margin-top:6px;background:rgba(59,130,246,0.18);border:1px solid rgba(59,130,246,0.45);color:#bfdbfe;font-size:11px;padding:5px 10px;border-radius:8px;">Editar referencia</button>` : ''}
            </div>
          </div>
          ${(() => {
            if (isAutoMapped) return `<div class="box-right">
            <div class="id-section">
              <div class="id-label">${o.customer_zone ? 'ID - ZONA ID' : 'ID'} <a href="#" class="btn-show-id" style="color:#22c55e;font-weight:800;text-decoration:underline;font-size:12px;margin-left:6px;">Ver</a></div>
              <code class="hex" style="display:none;">${playerId}${o.customer_zone ? ' - ' + o.customer_zone : ''}</code>
              <button class="btn-copy" type="button" data-copy="${playerId}" style="display:none;">Copiar</button>
            </div>
          </div>`;
            return `<div class="box-right">
            <div class="id-section">
              <div class="id-label">${o.customer_zone ? 'ID - ZONA ID' : 'ID'}</div>
              <code class="hex">${playerId}${o.customer_zone ? ' - ' + o.customer_zone : ''}</code>
              <button class="btn-copy" type="button" data-copy="${playerId}">Copiar</button>
            </div>
          </div>`;
          })()}
        </div>
        <div class="row-foot">
          <div class="amount">${amountDisp}${affiliateTag}</div>
          <div>${when}</div>
          <div class="customer">${o.name || o.email || 'Cliente'}${o.phone ? ' - ' + o.phone : ''}</div>
        </div>
        ${o.payment_capture_url ? `<div style="padding:6px 12px 2px;"><button type="button" class="btn btn-sm" style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.4);color:#6ee7b7;font-size:11px;padding:4px 12px;border-radius:8px;cursor:pointer;width:100%;" onclick="openCaptureModal('${o.payment_capture_url.replace(/'/g, "\\'")}')">📷 Ver comprobante</button></div>` : ''}
        ${isGift ? `
        <div class="row-actions">
          ${(itemsArr.length && qtyTotal > 1)
            ? `<textarea class="input gift-codes" data-id="${o.id}" placeholder="Un c\u00f3digo por l\u00ednea" rows="${Math.min(6, Math.max(2, qtyTotal))}" style="flex:1; min-width:260px; resize:vertical;"></textarea>`
            : `<input class="input gift-code" data-id="${o.id}" type="text" placeholder="C\u00f3digo para el cliente" value="${o.delivery_code || ''}" style="flex:1; min-width:220px;" />`
          }
        </div>` : ''}
        <div class="row-actions" style="justify-content:space-between;">
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            ${payProvider !== 'ubii' && pabiloRequestable && ['pending', 'approved', 'delivered'].includes(o.status) && !pabiloVerified ? `<button class="btn btn-verify-payment" data-id="${o.id}">Verificar pago</button>` : ''}
            ${activeVerifyProvider === 'ubii' && ['pending', 'approved', 'delivered'].includes(o.status) && !pabiloVerified ? `<button class="btn btn-verify-ubii" data-id="${o.id}">Verificar Ubii</button>` : ''}
            <button class="btn btn-approve" data-id="${o.id}" ${approveDisabled ? 'disabled' : ''}>${approveLabel}</button>
            ${isAutoMapped && processingAutoUnits > 0 ? `<button class="btn btn-verify-recharge" data-id="${o.id}">Verificar ${processingAutoUnits}</button>` : ''}
          </div>
          <button class="btn btn-reject" data-id="${o.id}" ${rejectDisabled ? 'disabled' : ''} style="background:#dc2626;">Rechazar</button>
        </div>
      `;
      ordersList.appendChild(tile);
    });
  }

  if (btnOrdersRefresh) btnOrdersRefresh.addEventListener('click', fetchOrders);
  if (ordersList) {
    ordersList.addEventListener('click', async (e) => {
      const showId = e.target.closest('.btn-show-id');
      if (showId) {
        e.preventDefault();
        const section = showId.closest('.id-section');
        if (section) {
          const code = section.querySelector('.hex');
          const copyBtn = section.querySelector('.btn-copy');
          if (code) code.style.display = code.style.display === 'none' ? '' : 'none';
          if (copyBtn) copyBtn.style.display = copyBtn.style.display === 'none' ? '' : 'none';
          showId.textContent = code && code.style.display === 'none' ? 'Ver' : 'Ocultar';
        }
        return;
      }

      const copy = e.target.closest('.btn-copy');
      if (copy) {
        const value = copy.getAttribute('data-copy') || '';
        try { await navigator.clipboard.writeText(value); toast('Copiado'); } catch(_) { toast('No se pudo copiar'); }
        return;
      }

      function _pollVerifyRecharge(orderId, btnEl) {
        let attempts = 0;
        const maxAttempts = 12;
        function _doPoll() {
          attempts++;
          fetch(`/admin/orders/${orderId}/verify-recharge`, { method: 'POST' })
            .then(r => r.json())
            .then(d => {
              if (d.result === 'completed') {
                const done = d.summary && d.summary.total_units ? `${d.summary.completed_units}/${d.summary.total_units}` : 'completada';
                toast(`✅ Cola completada: ${done} recargas listas${d.player_name ? `. Jugador: ${d.player_name}` : ''}`, 'success');
                if (btnEl) { btnEl.textContent = 'Completada'; btnEl.style.background = '#22c55e'; }
                setTimeout(() => fetchOrders(), 1500);
              } else if (d.result === 'processing') {
                const processing = d.summary && d.summary.processing_units ? d.summary.processing_units : attempts;
                if (btnEl) btnEl.textContent = `Cola activa ${processing}... (${attempts})`;
                if (attempts < maxAttempts) setTimeout(_doPoll, 5000);
                else {
                  if (btnEl) { btnEl.textContent = 'Reintentar verificar'; btnEl.disabled = false; }
                  btnEl.onclick = function(ev) { ev.preventDefault(); ev.stopPropagation(); attempts = 0; btnEl.disabled = true; btnEl.textContent = 'Verificando...'; _doPoll(); };
                }
              } else if (d.can_approve) {
                toast(d.message || 'Recarga no completada. Puedes reintentar.', 'warning');
                if (btnEl) { btnEl.disabled = false; btnEl.textContent = 'Verificar'; btnEl.onclick = null; }
                fetchOrders();
              } else {
                if (btnEl) btnEl.textContent = 'Error verificando';
                if (attempts < maxAttempts) setTimeout(_doPoll, 5000);
              }
            })
            .catch(() => {
              if (attempts < maxAttempts) setTimeout(_doPoll, 5000);
              else if (btnEl) { btnEl.textContent = 'Verificar'; btnEl.disabled = false; btnEl.onclick = null; }
            });
        }
        setTimeout(_doPoll, 2000);
      }

      const btnV = e.target.closest('.btn-verify-recharge');
      if (btnV) {
        const id = btnV.getAttribute('data-id');
        if (!id) return;
        btnV.disabled = true;
        btnV.textContent = 'Verificando...';
        _pollVerifyRecharge(id, btnV);
        return;
      }

      const btnP = e.target.closest('.btn-verify-payment');
      if (btnP) {
        const id = btnP.getAttribute('data-id');
        if (!id) return;
        try {
          btnP.disabled = true;
          btnP.textContent = 'Verificando...';
          const res = await fetch(`/admin/orders/${id}/verify-payment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.ok) {
            const requestReason = (data.request && data.request.reason) ? ` (${data.request.reason})` : '';
            const eligReason = (!requestReason && data.eligibility && data.eligibility.reason) ? ` (${data.eligibility.reason})` : '';
            throw new Error((data.error || 'No se pudo verificar el pago') + requestReason + eligReason);
          }
          const pv = data.payment_verify || {};
          if (pv.verified) {
            toast(`✅ Pago verificado en Pabilo${pv.verification_id ? ` · ${pv.verification_id}` : ''}`, 'success');
          } else {
            toast(pv.message || 'Pago no verificado todavía', 'warning');
          }
          await fetchOrders();
        } catch (err) {
          toast(err.message || 'Error verificando pago');
        } finally {
          btnP.disabled = false;
          btnP.textContent = 'Verificar pago';
        }
        return;
      }

      const btnUbii = e.target.closest('.btn-verify-ubii');
      if (btnUbii) {
        const id = btnUbii.getAttribute('data-id');
        if (!id) return;
        const pastedText = window.prompt('Pega el texto completo de la notificación de Ubii para verificar esta orden');
        if (pastedText === null) return;
        if (!String(pastedText || '').trim()) {
          toast('Debes pegar el texto de la notificación');
          return;
        }
        try {
          btnUbii.disabled = true;
          btnUbii.textContent = 'Verificando Ubii...';
          const res = await fetch(`/admin/orders/${id}/verify-ubii`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: String(pastedText || '').trim() })
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.ok) {
            throw new Error(data.error || (data.payment_verify && data.payment_verify.message) || 'No se pudo verificar con Ubii');
          }
          const pv = data.payment_verify || {};
          if (pv.verified) {
            toast(`✅ Pago verificado en Ubii${pv.verification_id ? ` · ${pv.verification_id}` : ''}`, 'success');
          } else {
            toast(pv.message || 'Pago no verificado todavía', 'warning');
          }
          await fetchOrders();
        } catch (err) {
          toast(err.message || 'Error verificando Ubii');
        } finally {
          btnUbii.disabled = false;
          btnUbii.textContent = 'Verificar Ubii';
        }
        return;
      }

      const btnEditRef = e.target.closest('.btn-edit-reference');
      if (btnEditRef) {
        const id = btnEditRef.getAttribute('data-id');
        const tile = btnEditRef.closest('.order-tile');
        const currentRef = tile ? ((tile.querySelector('.ref-value')?.textContent || '').trim()) : '';
        const nextRef = window.prompt('Ingresa la referencia correcta para esta orden', currentRef === '-' ? '' : currentRef);
        if (nextRef === null) return;
        try {
          btnEditRef.disabled = true;
          btnEditRef.textContent = 'Guardando...';
          const res = await fetch(`/admin/orders/${id}/reference`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reference: String(nextRef || '').trim() })
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo actualizar la referencia');
          toast(data.changed ? 'Referencia actualizada. Ya puedes verificar el pago.' : 'La referencia no cambió.', data.changed ? 'success' : 'warning');
          await fetchOrders(ordersCurrentPage);
        } catch (err) {
          toast(err.message || 'Error actualizando referencia');
        } finally {
          btnEditRef.disabled = false;
          btnEditRef.textContent = 'Editar referencia';
        }
        return;
      }

      const btnA = e.target.closest('.btn-approve');
      const btnR = e.target.closest('.btn-reject');
      const btn = btnA || btnR;
      if (!btn) return;
      const id = btn.getAttribute('data-id');
      const status = btnA ? 'approved' : 'rejected';
      if (btnA) {
        const tile = btn.closest('.order-tile');
        const isAutoTile = tile && tile.getAttribute('data-is-auto') === '1';
        if (isAutoTile) {
          const _game = tile ? (tile.querySelector('.game-name')?.textContent || '').trim() : '';
          const _pid = tile ? (tile.querySelector('.hex')?.textContent || '').trim() : '';
          const _ref = tile ? (tile.querySelector('.ref-value')?.textContent || '').trim() : '';
          const _nick = tile ? (tile.getAttribute('data-customer-name') || '') : '';
          const msg = `⚠️ RECARGA AUTOMÁTICA E IRREVERSIBLE\n\n` +
            `Juego: ${_game}\n` +
            `ID: ${_pid}\n` +
            (_nick ? `Nombre: ${_nick}\n` : '') +
            `Referencia: ${_ref}\n\n` +
            `¿Confirmar envío?`;
          if (!confirm(msg)) return;
        }
      }
      let keepDisabled = false;
      try {
        btn.disabled = true;
        const payload = { status };
        if (status === 'approved') {
          const codeInput = ordersList.querySelector(`.gift-code[data-id="${id}"]`);
          const codesArea = ordersList.querySelector(`.gift-codes[data-id="${id}"]`);
          if (codesArea) {
            const lines = codesArea.value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
            if (lines.length) payload.delivery_codes = lines;
          } else if (codeInput && codeInput.value.trim()) {
            payload.delivery_code = codeInput.value.trim();
          }
        }
        const res = await fetch(`/admin/orders/${id}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          // If Pabilo verification failed (409), offer manual override
          if (res.status === 409 && data.payment_verify && !data.payment_verify.verified) {
            const pvMsg = data.payment_verify.message || data.error || 'Pago no verificado';
            const override = confirm(
              `⚠️ Verificación Pabilo falló:\n${pvMsg}\n\n¿Deseas aprobar esta orden manualmente sin verificación de Pabilo?`
            );
            if (override) {
              payload.skip_payment_verification = true;
              const res2 = await fetch(`/admin/orders/${id}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
              });
              const data2 = await res2.json();
              if (!res2.ok || !data2.ok) throw new Error(data2.error || 'No se pudo aprobar manualmente');
              // Handle auto-recharge response same as normal flow
              if (data2.webb_recarga) {
                if (data2.webb_recarga.ok) {
                  const summary = data2.webb_recarga.summary || {};
                  const done = summary.total_units ? `${summary.completed_units}/${summary.total_units}` : '1/1';
                  toast(`✅ Cola completada al instante: ${done}`, 'success');
                } else if (data2.webb_recarga.pending_verification) {
                  const summary = data2.webb_recarga.summary || {};
                  const processing = summary.processing_units || 0;
                  toast(`⚠️ Cola iniciada: ${processing} recarga(s) en proceso.`, 'error');
                  keepDisabled = true;
                  btn.disabled = true;
                  btn.textContent = 'Verificando...';
                  _pollVerifyRecharge(data2.webb_recarga.order_id, btn);
                  await fetchOrders();
                  return;
                }
              }
              toast('Orden aprobada manualmente', 'success');
              await fetchOrders();
              return;
            }
            return;
          }
          throw new Error(data.error || 'No se pudo actualizar');
        }
        if (data.webb_recarga) {
          if (data.webb_recarga.ok) {
            const summary = data.webb_recarga.summary || {};
            const done = summary.total_units ? `${summary.completed_units}/${summary.total_units}` : '1/1';
            toast(`✅ Cola completada al instante: ${done}`, 'success');
          } else if (data.webb_recarga.pending_verification) {
            const summary = data.webb_recarga.summary || {};
            const processing = summary.processing_units || 0;
            toast(`⚠️ Cola iniciada: ${processing} recarga(s) en proceso. La siguiente saldrá sola al completarse.${data.webb_recarga.error ? ` ${data.webb_recarga.error}` : ''}`, 'error');
            keepDisabled = true;
            btn.disabled = true;
            btn.textContent = 'Verificando...';
            _pollVerifyRecharge(data.webb_recarga.order_id, btn);
            return;
          } else {
            const summary = data.webb_recarga.summary || {};
            const retryable = summary.retryable_units || 0;
            toast(`⚠️ Quedan ${retryable} recarga(s) por reenviar${data.webb_recarga.error ? `: ${data.webb_recarga.error}` : ''}.`, 'error');
          }
        }
        await fetchOrders();
      } catch (err) {
        toast(err.message || 'Error');
      } finally {
        if (!keepDisabled) btn.disabled = false;
      }
    });
  }
  if (ordersPagination) {
    ordersPagination.addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-page]');
      if (!btn) return;
      const page = parseInt(btn.getAttribute('data-page') || '1', 10) || 1;
      await fetchOrders(page);
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
        if (hero1) { hero1.value = data.hero_1 || ''; syncDropdown(hero1); }
        if (hero2) { hero2.value = data.hero_2 || ''; syncDropdown(hero2); }
        if (hero3) { hero3.value = data.hero_3 || ''; syncDropdown(hero3); }
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

  // Duplicate uploadImage function and event listeners removed - using the ones above

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
  window.fetchThanksImage && window.fetchThanksImage();
  window.fetchHero && window.fetchHero();
  window.fetchRate && window.fetchRate();
  window.fetchPayments && window.fetchPayments();

  // =====================
  // Image thumbnail dropdown (used everywhere)
  // =====================
  let _imgDropdownCache = null;
  async function getImageList() {
    if (_imgDropdownCache) return _imgDropdownCache;
    try {
      const res = await fetch('/admin/images/list');
      _imgDropdownCache = await res.json();
    } catch (_) { _imgDropdownCache = []; }
    return _imgDropdownCache || [];
  }
  function invalidateImageCache() { _imgDropdownCache = null; }

  function createImageDropdown(currentPath, onSelect) {
    const wrap = document.createElement('div');
    wrap.className = 'img-dropdown-wrap';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'img-dropdown-btn';
    const preview = document.createElement('img');
    preview.className = 'img-dropdown-preview';
    preview.src = currentPath || '';
    preview.alt = '';
    if (!currentPath) preview.style.display = 'none';
    const label = document.createElement('span');
    label.className = 'img-dropdown-label';
    label.textContent = currentPath ? 'Cambiar imagen' : 'Elegir imagen';
    const arrow = document.createElement('span');
    arrow.className = 'img-dropdown-arrow';
    arrow.textContent = '\u25BC';
    btn.append(preview, label, arrow);

    const panel = document.createElement('div');
    panel.className = 'img-dropdown-panel';

    wrap.append(btn, panel);
    wrap._hiddenInput = null;
    wrap._currentPath = currentPath || '';

    function closePanel() { panel.classList.remove('open'); }

    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (panel.classList.contains('open')) { closePanel(); return; }
      // Close any other open dropdowns
      document.querySelectorAll('.img-dropdown-panel.open').forEach(p => p.classList.remove('open'));
      panel.innerHTML = '';
      const imgs = await getImageList();
      if (!imgs.length) { panel.innerHTML = '<div style="padding:12px;color:#94a3b8;font-size:12px;grid-column:1/-1;">Sin im\u00e1genes</div>'; }
      imgs.forEach(it => {
        const opt = document.createElement('div');
        opt.className = 'img-dropdown-option';
        if (it.path === wrap._currentPath) opt.classList.add('selected');
        const img = document.createElement('img');
        img.src = it.path;
        img.alt = it.title || '';
        img.loading = 'lazy';
        opt.appendChild(img);
        opt.addEventListener('click', (ev) => {
          ev.stopPropagation();
          wrap._currentPath = it.path;
          preview.src = it.path;
          preview.style.display = '';
          label.textContent = 'Cambiar imagen';
          if (wrap._hiddenInput) wrap._hiddenInput.value = it.path;
          if (onSelect) onSelect(it.path);
          closePanel();
        });
        panel.appendChild(opt);
      });
      panel.classList.add('open');
    });

    document.addEventListener('click', (e) => {
      if (!wrap.contains(e.target)) closePanel();
    });

    return wrap;
  }

  // Helper: mount a config image dropdown into a slot, wiring it to a hidden input
  function mountConfigDropdown(slotId, hiddenInput, onSelect) {
    const slot = document.getElementById(slotId);
    if (!slot || !hiddenInput) return;
    const dd = createImageDropdown(hiddenInput.value || '', (path) => {
      hiddenInput.value = path;
      if (onSelect) onSelect(path);
    });
    dd._hiddenInput = hiddenInput;
    slot.appendChild(dd);
    // Keep dropdown in sync when value loaded async
    hiddenInput._imgDropdown = dd;
  }
  function syncDropdown(input) {
    if (input && input._imgDropdown) {
      const dd = input._imgDropdown;
      dd._currentPath = input.value || '';
      const prev = dd.querySelector('.img-dropdown-preview');
      const lbl = dd.querySelector('.img-dropdown-label');
      if (prev) { prev.src = input.value || ''; prev.style.display = input.value ? '' : 'none'; }
      if (lbl) lbl.textContent = input.value ? 'Cambiar imagen' : 'Elegir imagen';
    }
  }

  // Mount config image dropdowns (Logo auto-saves on pick)
  mountConfigDropdown('slot-logo', inputLogo, async (path) => {
    try {
      const res = await fetch('/admin/config/logo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ logo_path: path }) });
      if (!res.ok) throw new Error();
      toast('Logo actualizado');
    } catch (_) { toast('No se pudo guardar el logo', 'error'); }
  });
  // Mid-Banner auto-saves on pick
  mountConfigDropdown('slot-mid-banner', inputMidBanner, async (path) => {
    try {
      const res = await fetch('/admin/config/mid_banner', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mid_banner_path: path }) });
      if (!res.ok) throw new Error();
      toast('Banner actualizado');
    } catch (_) { toast('No se pudo guardar el banner', 'error'); }
  });
  mountConfigDropdown('slot-thanks-image', inputThanksImage);
  mountConfigDropdown('slot-hero-1', hero1);
  mountConfigDropdown('slot-hero-2', hero2);
  mountConfigDropdown('slot-hero-3', hero3);
  mountConfigDropdown('slot-pm-image', pmImage);
  mountConfigDropdown('slot-binance-image', binImage);

  // Package creation form dropdown
  {
    const slot = document.getElementById('pkg-image-dropdown-slot');
    if (slot && pkgImage) {
      const dd = createImageDropdown('', (path) => { pkgImage.value = path; });
      dd._hiddenInput = pkgImage;
      slot.appendChild(dd);
      pkgImage._imgDropdown = dd;
    }
  }

  // Save payments
  if (btnSavePayments) {
    btnSavePayments.addEventListener('click', async () => {
      try {
        btnSavePayments.disabled = true;
        const resp = await savePayments();
        if (resp && resp.ok) {
          if (resp.saved) applyPaymentsData(resp.saved);
          toast('Métodos de pago guardados', 'success');
          showPaySection(activePayMethodView || 'pm');
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
      const category = (p.category || 'mobile');
      const isGift = category === 'gift';
      const card = document.createElement('div');
      card.className = 'pkg-card';
      card.dataset.id = String(p.id || '');
      let catClass = 'pkg-badge--mobile';
      let catLabel = 'MOBILE';
      if (isGift) {
        catClass = 'pkg-badge--gift';
        catLabel = 'GIFT CARD';
      } else if (category === 'other') {
        catLabel = 'OTROS SERVICIOS';
      }
      const activeClass = p.active ? 'pkg-badge--active' : 'pkg-badge--inactive';
      const activeTxt = p.active ? 'Activo' : 'Inactivo';
      card.innerHTML = `
        <div class="pkg-card-head">
          <img class="pkg-card-thumb" src="${p.image_path}" alt="${p.name}">
          <div class="pkg-card-info">
            <div class="pkg-card-name">${p.name}</div>
            <div class="pkg-card-badges">
              <span class="pkg-badge ${catClass}">${catLabel}</span>
              <span class="pkg-badge ${activeClass}">${activeTxt}</span>
            </div>
          </div>
          <div class="pkg-card-actions">
            <button class="btn btn-drag" data-id="${p.id}" type="button" title="Arrastrar">\u2195</button>
            <button class="btn btn-delete" data-id="${p.id}" type="button">Eliminar</button>
          </div>
        </div>
        <details class="pkg-card-edit">
          <summary class="pkg-edit-toggle">Editar</summary>
          <div class="pkg-edit-body">
            <input class="edit-special-desc" type="hidden" value="${(p.special_description || '').replace(/"/g, '&quot;')}">
            <div class="pkg-edit-section-label">Datos del paquete</div>
            <div class="pkg-edit-grid">
              <div class="pkg-edit-field"><label>Nombre</label><input class="edit-name" type="text" value="${p.name}" /></div>
              <div class="pkg-edit-field"><label>Categor\u00eda</label>
                <select class="edit-category">
                  <option value="mobile" ${p.category === 'mobile' ? 'selected' : ''}>Juegos Mobile</option>
                  <option value="gift" ${p.category === 'gift' ? 'selected' : ''}>Gift Cards</option>
                  <option value="other" ${p.category === 'other' ? 'selected' : ''}>Otros Servicios</option>
                </select>
              </div>
            </div>
            <div class="pkg-edit-grid pkg-edit-grid--1">
              <div class="pkg-edit-field"><label>Descripci\u00f3n</label><textarea class="edit-desc" rows="2">${p.description || ''}</textarea></div>
            </div>
            <div class="pkg-edit-grid pkg-edit-grid--3">
              <div class="pkg-edit-field"><label>Imagen</label>
                <div class="pkg-img-dropdown-slot"></div>
                <input class="edit-image" type="hidden" value="${p.image_path}" />
              </div>
              <div class="pkg-edit-field" style="display:flex;flex-direction:column;justify-content:center;">
                <label>Activo</label>
                <label class="pkg-toggle"><input class="edit-active" type="checkbox" ${p.active ? 'checked' : ''} /><span class="pkg-toggle-label">${p.active ? 'S\u00ed' : 'No'}</span></label>
              </div>
              <div class="pkg-edit-field" style="display:flex;flex-direction:column;justify-content:center;">
                <label>Zona ID</label>
                <label class="pkg-toggle"><input class="edit-requires-zone" type="checkbox" ${p.requires_zone_id ? 'checked' : ''} /><span class="pkg-toggle-label">Requerida</span></label>
              </div>
            </div>

            <div class="pkg-edit-section-label">Items de este paquete</div>
            <div class="game-items" data-gid="${p.id}">
              <div class="items-list"></div>
              <div class="pkg-new-item">
                <div class="pkg-edit-field"><label>T\u00edtulo</label><input class="new-item-title" type="text" placeholder="Nuevo item" /></div>
                <div class="pkg-edit-field"><label>Precio</label><input class="new-item-price" type="number" step="0.01" min="0" placeholder="0.00" /></div>
                <div class="pkg-edit-field" style="display:flex;align-items:end;"><button class="btn btn-item-create" type="button">+ Agregar</button></div>
                <div class="pkg-new-item-extras">
                  <div class="pkg-edit-field" style="flex:1;min-width:180px;"><label>Icono (opc.)</label>
                    <div class="item-icon-dropdown-slot"></div><input class="new-item-icon" type="hidden">
                  </div>
                </div>
              </div>
            </div>

            <div class="pkg-edit-actions">
              <button class="btn primary btn-save-all" data-id="${p.id}" type="button">Guardar todo</button>
              <button class="btn btn-delete" data-id="${p.id}" type="button">Eliminar paquete</button>
            </div>
          </div>
        </details>
      `;
      // Bind image dropdown for package image
      const imgInput = card.querySelector('.edit-image');
      const imgSlot = card.querySelector('.pkg-img-dropdown-slot');
      if (imgSlot && imgInput) {
        const dd = createImageDropdown(p.image_path, (path) => { imgInput.value = path; });
        dd._hiddenInput = imgInput;
        imgSlot.appendChild(dd);
      }
      // Bind icon dropdown for new item form
      const newIconSlot = card.querySelector('.pkg-new-item-extras .item-icon-dropdown-slot');
      const newIconInput = card.querySelector('.new-item-icon');
      if (newIconSlot && newIconInput) {
        const dd2 = createImageDropdown('', (path) => { newIconInput.value = path; });
        dd2._hiddenInput = newIconInput;
        newIconSlot.appendChild(dd2);
      }
      // Enable drag via handle and persist on drop
      const dragHandle = card.querySelector('.btn-drag');
      if (dragHandle) {
        dragHandle.addEventListener('mousedown', () => { try { card.setAttribute('draggable', 'true'); } catch(_) {} });
        ['mouseup','mouseleave','blur'].forEach(ev => dragHandle.addEventListener(ev, () => { try { card.removeAttribute('draggable'); } catch(_) {} }));
      }
      card.addEventListener('dragstart', (ev) => {
        card.classList.add('dragging');
        try { ev.dataTransfer.setData('text/plain', card.dataset.id || ''); } catch(_) {}
      });
      card.addEventListener('dragend', async () => {
        card.classList.remove('dragging');
        try { card.removeAttribute('draggable'); } catch(_) {}
        try { await savePkgOrder(); toast('Orden guardado'); } catch(e) { toast('No se pudo guardar el orden', 'error'); }
      });
      // Auto-load items when <details> opens
      const detailsEl = card.querySelector('details.pkg-card-edit');
      if (detailsEl) {
        detailsEl.addEventListener('toggle', () => {
          if (detailsEl.open) {
            const game = card.querySelector('.game-items');
            if (game) loadGameItems(game, game.getAttribute('data-gid'));
          }
        });
      }
      if (isGift && accSpec) { accSpec.appendChild(card); specCount++; }
      else if (accNorm) { accNorm.appendChild(card); }
      else { pkgList.appendChild(card); }
    });
    if (grpSpec) grpSpec.hidden = specCount === 0;
    const containers = [accSpec, accNorm, pkgList].filter(Boolean);
    containers.forEach(container => {
      container.addEventListener('dragover', (e) => {
        e.preventDefault();
        const dragging = document.querySelector('.pkg-card.dragging');
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

  // =====================
  // Config: Mobile Legends package ID (Smile.One verification)
  // =====================
  const inputMlPackageId = document.getElementById('ml-package-id');
  const inputMlSmilePid = document.getElementById('ml-smile-pid');
  const btnSaveMlPackageId = document.getElementById('btn-save-ml-package-id');

  async function fetchMlPackageId() {
    try {
      const [res1, res2] = await Promise.all([
        fetch('/admin/config/ml_package_id'),
        fetch('/admin/config/ml_smile_pid')
      ]);
      const data1 = await res1.json();
      const data2 = await res2.json();
      if (res1.ok && data1 && data1.ok && inputMlPackageId) {
        inputMlPackageId.value = data1.ml_package_id || '';
      }
      if (res2.ok && data2 && data2.ok && inputMlSmilePid) {
        inputMlSmilePid.value = data2.ml_smile_pid || '';
      }
    } catch (_) { /* ignore */ }
  }

  async function saveMlPackageId() {
    const pkgVal = inputMlPackageId ? String(inputMlPackageId.value || '').trim() : '';
    const pidVal = inputMlSmilePid ? String(inputMlSmilePid.value || '').trim() : '';
    await Promise.all([
      fetch('/admin/config/ml_package_id', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ml_package_id: pkgVal })
      }),
      fetch('/admin/config/ml_smile_pid', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ml_smile_pid: pidVal })
      })
    ]);
  }

  if (btnSaveMlPackageId) {
    btnSaveMlPackageId.addEventListener('click', async () => {
      try {
        btnSaveMlPackageId.disabled = true;
        await saveMlPackageId();
        toast('Configuración de Mobile Legends guardada');
      } catch (e) {
        toast(e.message || 'Error');
      } finally {
        btnSaveMlPackageId.disabled = false;
      }
    });
  }

  fetchMlPackageId();

  // =====================
  // Smile.One Connections CRUD
  // =====================
  const soName = document.getElementById('so-name');
  const soPageUrl = document.getElementById('so-page-url');
  const soStorePkg = document.getElementById('so-store-pkg');
  const soSmilePid = document.getElementById('so-smile-pid');
  const soServerId = document.getElementById('so-server-id');
  const soProductSlug = document.getElementById('so-product-slug');
  const soRequiresZone = document.getElementById('so-requires-zone');
  const btnSoCreate = document.getElementById('btn-so-create');
  const btnSoRefresh = document.getElementById('btn-so-refresh');
  const soList = document.getElementById('so-list');

  let _soConnections = [];

  async function fetchSmileOneConnections() {
    try {
      const res = await fetch('/admin/smileone/connections');
      const data = await res.json();
      if (!res.ok || !data.ok) return;
      _soConnections = data.connections || [];
      renderSmileOneConnections();
    } catch (_) { /* ignore */ }
  }

  function renderSmileOneConnections() {
    if (!soList) return;
    if (!_soConnections.length) {
      soList.innerHTML = '<div class="empty-state"><h3>Sin conexiones</h3><p>Agrega conexiones a Smile.One para verificar IDs de jugadores automáticamente.</p></div>';
      return;
    }
    soList.innerHTML = _soConnections.map(c => {
      const badge = c.active
        ? '<span style="color:#22c55e; font-weight:700;">Activa</span>'
        : '<span style="color:#ef4444; font-weight:700;">Inactiva</span>';
      const zoneBadge = c.requires_zone
        ? '<span style="background:rgba(59,130,246,0.15); color:#93c5fd; padding:2px 8px; border-radius:4px; font-size:11px;">Zona ID</span>'
        : '';
      return `
        <div class="order-tile" data-so-id="${c.id}" style="margin-bottom:10px;">
          <div class="row-head" style="cursor:pointer;" onclick="this.parentElement.classList.toggle('open')">
            <div>
              <div class="order-id" style="font-size:15px;">${c.name} ${zoneBadge}</div>
              <div class="order-meta">
                <span>Paquete tienda: <strong>#${c.store_package_id}</strong></span>
                <span style="margin-left:12px;">PID: <strong>${c.smile_pid || '—'}</strong></span>
                <span style="margin-left:12px;">Slug: <strong>${c.product_slug || '—'}</strong></span>
                <span style="margin-left:12px;">${badge}</span>
              </div>
            </div>
          </div>
          <div class="row-body" style="display:none; padding:12px 16px; border-top:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:13px; color:#94a3b8; margin-bottom:10px; word-break:break-all;">
              URL: <code>${c.page_url}</code><br>
              Server ID: <code>${c.server_id || '-1'}</code>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              <button class="btn" type="button" onclick="toggleSmileOneActive(${c.id}, ${!c.active})">${c.active ? 'Desactivar' : 'Activar'}</button>
              <button class="btn" type="button" style="border-color:rgba(239,68,68,0.5); color:#fca5a5;" onclick="deleteSmileOneConn(${c.id})">Eliminar</button>
            </div>
          </div>
        </div>`;
    }).join('');
    // Toggle open/close
    soList.querySelectorAll('.order-tile').forEach(tile => {
      const head = tile.querySelector('.row-head');
      const body = tile.querySelector('.row-body');
      if (head && body) {
        head.addEventListener('click', () => {
          const open = body.style.display !== 'none';
          body.style.display = open ? 'none' : 'block';
        });
      }
    });
  }

  window.toggleSmileOneActive = async function(id, active) {
    try {
      await fetch(`/admin/smileone/connections/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active })
      });
      toast(active ? 'Conexión activada' : 'Conexión desactivada');
      fetchSmileOneConnections();
    } catch (e) { toast(e.message || 'Error'); }
  };

  window.deleteSmileOneConn = async function(id) {
    if (!confirm('¿Eliminar esta conexión?')) return;
    try {
      await fetch(`/admin/smileone/connections/${id}`, { method: 'DELETE' });
      toast('Conexión eliminada');
      fetchSmileOneConnections();
    } catch (e) { toast(e.message || 'Error'); }
  };

  if (btnSoCreate) {
    btnSoCreate.addEventListener('click', async () => {
      const name = soName ? soName.value.trim() : '';
      const pageUrl = soPageUrl ? soPageUrl.value.trim() : '';
      const storePkg = soStorePkg ? soStorePkg.value.trim() : '';
      const smilePid = soSmilePid ? soSmilePid.value.trim() : '';
      const serverId = soServerId ? soServerId.value.trim() : '-1';
      const productSlug = soProductSlug ? soProductSlug.value.trim() : '';
      const requiresZone = soRequiresZone ? soRequiresZone.checked : false;
      if (!name || !pageUrl || !storePkg) {
        toast('Nombre, URL y Paquete son requeridos');
        return;
      }
      try {
        btnSoCreate.disabled = true;
        const res = await fetch('/admin/smileone/connections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, page_url: pageUrl, store_package_id: storePkg, smile_pid: smilePid, server_id: serverId, product_slug: productSlug, requires_zone: requiresZone })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          toast(data.error || 'Error al crear');
          return;
        }
        toast('Conexión creada');
        if (soName) soName.value = '';
        if (soPageUrl) soPageUrl.value = '';
        if (soStorePkg) soStorePkg.value = '';
        if (soSmilePid) soSmilePid.value = '';
        if (soServerId) soServerId.value = '-1';
        if (soProductSlug) soProductSlug.value = '';
        if (soRequiresZone) soRequiresZone.checked = false;
        fetchSmileOneConnections();
      } catch (e) {
        toast(e.message || 'Error');
      } finally {
        btnSoCreate.disabled = false;
      }
    });
  }

  if (btnSoRefresh) btnSoRefresh.addEventListener('click', fetchSmileOneConnections);
  fetchSmileOneConnections();

  function filterPackagesBySelect() {
    const sel = pkgSelect ? String(pkgSelect.value || '') : '';
    const items = pkgList ? pkgList.querySelectorAll('.pkg-card') : [];
    if (!items || items.length === 0) return;
    if (!sel) {
      // Hide all until user selects
      items.forEach(el => { el.style.display = 'none'; el.classList.remove('open'); });
      return;
    }
    items.forEach(el => {
      const match = (el.dataset && el.dataset.id) === sel;
      el.style.display = match ? '' : 'none';
      if (match) {
        el.classList.add('open');
        try { el.scrollIntoView({ behavior: 'auto', block: 'start' }); } catch(_) {}
      } else {
        el.classList.remove('open');
      }
    });
  }
  if (pkgSelect) {
    pkgSelect.addEventListener('change', filterPackagesBySelect);
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
    const text = await res.text();
    let data;
    try { data = JSON.parse(text); } catch (_) { throw new Error('Respuesta inválida: ' + text.substring(0, 100)); }
    if (!res.ok || !data.ok) {
      throw new Error(data.error || ('Error ' + res.status));
    }
    return data;
  }

  if (btnPackagesRefresh) {
    btnPackagesRefresh.addEventListener('click', fetchPackages);
  }
  if (btnCreatePkg) {
    btnCreatePkg.addEventListener('click', async () => {
      try {
        btnCreatePkg.disabled = true;
        await createPackage();
        toast('Paquete creado', 'success');
        if (pkgName) pkgName.value = '';
        if (pkgImage) { pkgImage.value = ''; syncDropdown(pkgImage); }
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
      const btnSaveAll = e.target.closest('.btn-save-all');
      const btnItemCreate = e.target.closest('.btn-item-create');
      const btnItemDelete = e.target.closest('.btn-item-delete');
      const btnSpecialDescSave = e.target.closest('.btn-special-desc-save');

      // Save single special description for the package
      if (btnSpecialDescSave) {
        const pkg = btnSpecialDescSave.closest('.pkg-card');
        const game = btnSpecialDescSave.closest('.game-items');
        const gid = (pkg && pkg.getAttribute('data-id')) || (game && game.getAttribute('data-gid'));
        if (!gid) { toast('No se encontr\u00f3 el ID del juego'); return; }
        const textEl = (pkg || game).querySelector('.special-desc');
        const editSpecDesc = pkg ? pkg.querySelector('.edit-special-desc') : null;
        const special_description = textEl ? textEl.value.trim() : '';
        try {
          btnSpecialDescSave.disabled = true;
          const res = await fetch(`/admin/packages/${gid}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ special_description })
          });
          if (!res.ok) throw new Error('No se pudo guardar');
          if (editSpecDesc) editSpecDesc.value = special_description;
          toast('Descripci\u00f3n guardada');
        } catch (err) {
          toast(err.message || 'Error al guardar descripci\u00f3n');
        } finally {
          btnSpecialDescSave.disabled = false;
        }
        return;
      }
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

      // === SAVE ALL: package info + all items in one go ===
      if (btnSaveAll) {
        const id = btnSaveAll.getAttribute('data-id');
        if (!id) return;
        const card = btnSaveAll.closest('.pkg-card');
        if (!card) return;
        const nameEl = card.querySelector('.edit-name');
        const catEl = card.querySelector('.edit-category');
        const imgEl = card.querySelector('.edit-image');
        const descEl = card.querySelector('.edit-desc');
        const activeEl = card.querySelector('.edit-active');
        const rzEl = card.querySelector('.edit-requires-zone');
        const specDescEl = card.querySelector('.edit-special-desc');
        const specialDescTextarea = card.querySelector('.special-desc');
        const pkgPayload = {
          name: nameEl ? nameEl.value.trim() : '',
          category: catEl ? catEl.value : 'mobile',
          image_path: imgEl ? imgEl.value.trim() : '',
          description: descEl ? descEl.value.trim() : '',
          requires_zone_id: rzEl ? !!rzEl.checked : false,
          active: activeEl ? !!activeEl.checked : true
        };
        if (specialDescTextarea) {
          pkgPayload.special_description = specialDescTextarea.value.trim();
        } else if (specDescEl) {
          pkgPayload.special_description = specDescEl.value;
        }
        // Collect all item rows
        const itemRows = card.querySelectorAll('.pkg-item-row');
        const itemsPayload = [];
        itemRows.forEach(row => {
          const itemId = row.getAttribute('data-id');
          if (!itemId) return;
          const titleEl = row.querySelector('.it-title');
          const priceEl = row.querySelector('.it-price');
          const specialEl = row.querySelector('.it-special');
          const iconEl = row.querySelector('.it-icon');
          itemsPayload.push({
            id: parseInt(itemId, 10),
            title: titleEl ? titleEl.value.trim() : '',
            price: priceEl ? parseFloat(priceEl.value || '0') : 0,
            sticker: specialEl && specialEl.checked ? 'special' : '',
            icon_path: iconEl ? iconEl.value.trim() : ''
          });
        });
        try {
          btnSaveAll.disabled = true;
          // Save package info
          const resPkg = await fetch(`/admin/packages/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pkgPayload)
          });
          if (!resPkg.ok) throw new Error('No se pudo guardar el paquete');
          // Bulk save items
          if (itemsPayload.length > 0) {
            const resItems = await fetch(`/admin/package/${id}/items/bulk`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ items: itemsPayload })
            });
            if (!resItems.ok) throw new Error('No se pudieron guardar los items');
          }
          toast('Todo guardado', 'success');
          await fetchPackages();
        } catch (err) {
          toast(err.message || 'Error al guardar');
        } finally {
          btnSaveAll.disabled = false;
        }
        return;
      }

      // Create new item
      if (btnItemCreate) {
        const game = btnItemCreate.closest('.game-items');
        const gid = game && game.getAttribute('data-gid');
        const titleEl = game && game.querySelector('.new-item-title');
        const priceEl = game && game.querySelector('.new-item-price');
        const iconEl = game && game.querySelector('.new-item-icon');
        const title = titleEl ? titleEl.value.trim() : '';
        const price = priceEl ? parseFloat(priceEl.value || '0') : 0;
        const icon_path = iconEl ? iconEl.value.trim() : '';
        if (!gid || !title) { toast('T\u00edtulo requerido'); return; }
        try {
          btnItemCreate.disabled = true;
          const res = await fetch(`/admin/package/${gid}/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, price, icon_path })
          });
          if (!res.ok) throw new Error('No se pudo crear');
          if (titleEl) titleEl.value = '';
          if (priceEl) priceEl.value = '';
          if (iconEl) iconEl.value = '';
          await loadGameItems(game, gid);
        } catch (err) {
          toast(err.message || 'Error al crear');
        } finally {
          btnItemCreate.disabled = false;
        }
        return;
      }
      // Delete item
      if (btnItemDelete) {
        const row = btnItemDelete.closest('.pkg-item-row');
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
    });
  }

  // Load packages initially (and again on tab switch)
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
      row.className = 'pkg-item-row';
      row.setAttribute('data-id', it.id);
      row.innerHTML = `
        <label class="pkg-edit-field"><span>T\u00edtulo</span>
          <input class="it-title" type="text" value="${it.title || ''}" placeholder="T\u00edtulo" />
        </label>
        <label class="pkg-edit-field"><span>Precio</span>
          <input class="it-price" type="number" step="0.01" min="0" value="${Number(it.price || 0)}" placeholder="Precio" />
        </label>
        <div class="pkg-item-extras">
          <label class="pkg-edit-field" style="flex:0 auto;"><span>Especial</span>
            <input class="it-special" type="checkbox" ${(it.sticker||'').toLowerCase()==='special' ? 'checked' : ''}/>
          </label>
          <label class="pkg-edit-field" style="flex:1;"><span>Icono</span>
            <div class="it-icon-wrap">
              <div class="item-icon-dropdown-slot"></div>
              <input class="it-icon" type="hidden" value="${it.icon_path || ''}">
            </div>
          </label>
          <button class="btn btn-item-delete" type="button" style="align-self:flex-end;">Eliminar</button>
        </div>
      `;
      return row;
    };
    if (specials.length > 0) specials.forEach(it => list.appendChild(addRow(it)));
    if (specials.length > 0) {
      const pkgRoot = list.closest('.pkg-card');
      const pkgDescInput = pkgRoot ? pkgRoot.querySelector('.edit-special-desc') : null;
      const wrap = document.createElement('div');
      wrap.className = 'pkg-item-row';
      wrap.innerHTML = `
        <div class="pkg-edit-section-label">Descripci\u00f3n para paquetes especiales</div>
        <textarea class="special-desc" style="width:100%; min-height:90px;">${pkgDescInput ? (pkgDescInput.value || '') : ''}</textarea>
        <div style="margin-top:6px;">
          <button class="btn btn-special-desc-save" type="button">Guardar descripci\u00f3n</button>
        </div>
      `;
      list.appendChild(wrap);
    }
    if (normals.length > 0) {
      if (specials.length > 0) {
        const sep = document.createElement('div');
        sep.className = 'pkg-edit-section-label';
        sep.textContent = 'Items normales';
        list.appendChild(sep);
      }
      normals.forEach(it => list.appendChild(addRow(it)));
    }
    // Initialize icon dropdowns for all item rows
    list.querySelectorAll('.item-icon-dropdown-slot').forEach(slot => {
      const hiddenInput = slot.parentElement && slot.parentElement.querySelector('.it-icon');
      if (!hiddenInput) return;
      const dd = createImageDropdown(hiddenInput.value || '', (path) => { hiddenInput.value = path; });
      dd._hiddenInput = hiddenInput;
      slot.appendChild(dd);
    });
  }
});

// ── Capture modal (comprobante viewer) ──────────────────────────────────────
function openCaptureModal(url) {
  var modal = document.getElementById('captureModal');
  var img = document.getElementById('capturePreviewImg');
  if (!modal || !img) return;
  // Mover el modal al body para que position:fixed no sea afectado por transform en padres
  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  img.src = url;
  modal.style.display = 'flex';
}
function closeCaptureModal() {
  var modal = document.getElementById('captureModal');
  var img = document.getElementById('capturePreviewImg');
  if (img) img.src = '';
  if (modal) modal.style.display = 'none';
}
document.addEventListener('click', function(e) {
  var modal = document.getElementById('captureModal');
  if (modal && e.target === modal) closeCaptureModal();
});
