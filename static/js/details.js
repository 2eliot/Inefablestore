// Details page logic
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('game-details');
  if (!root) return;
  const gid = root.getAttribute('data-game-id');
  const category = (root.getAttribute('data-category') || '').toLowerCase();
  const isGift = category === 'gift';
  const grid = document.getElementById('items-grid');
  const selBox = document.getElementById('selected-box');
  const selTitle = document.getElementById('selected-title');
  const selPrice = document.getElementById('selected-price');
  const sumPrice = document.getElementById('summary-price');
  const btnMore = document.getElementById('btn-more');
  const btnPayBSD = document.getElementById('pay-bsd');
  const btnPayUSD = document.getElementById('pay-usd');
  // Mobile footer selection
  const mfs = document.getElementById('mfs');
  const mfsTitle = document.getElementById('mfs-title');
  const mfsPrice = document.getElementById('mfs-price');
  const mfsClose = document.getElementById('mfs-close');
  // Step 4 inputs
  const inputCustomerId = document.getElementById('customer-id');
  // Hide Step 1 (player ID) for gift category
  if (isGift && inputCustomerId) {
    const stepCard = inputCustomerId.closest('.step-card');
    if (stepCard) stepCard.hidden = true;
    // Renumber remaining steps for gift category
    const stepCards = root.querySelectorAll('.details-right .step-card');
    // stepCards[0] is the (now hidden) customer-id; we adjust titles of next ones if present
    const step2Title = stepCards[1] && stepCards[1].querySelector('.step-title');
    const step3Title = stepCards[2] && stepCards[2].querySelector('.step-title');
    const step4Title = stepCards[3] && stepCards[3].querySelector('.step-title');
    if (step2Title) step2Title.textContent = '1 Selecciona tu producto';
    if (step3Title) step3Title.textContent = '2 Seleccione un método de pago';
    if (step4Title) step4Title.textContent = '3 Ingresa tus datos';
  }
  const inputName = document.getElementById('full-name');
  const inputEmail = document.getElementById('email');
  const inputPhone = document.getElementById('phone');
  const chkSave = document.getElementById('save-data');
  const btnBuy = document.getElementById('btn-buy');
  const inputRefCode = document.getElementById('ref-code');
  const refStatus = document.getElementById('ref-status');
  let validRef = null; // { code, discount }
  // Pay modal
  const payModal = document.getElementById('pay-modal');
  const payInfo = document.getElementById('pay-info');
  const payTotalTitle = document.getElementById('pay-total-title');
  const payTimer = document.getElementById('pay-timer');
  const payRef = document.getElementById('pay-ref');
  const btnConfirmPay = document.getElementById('btn-confirm-pay');
  let paymentsCfg = null;
  let countdownId = null;
  let allItems = [];
  let showingAll = false; // only used on mobile
  let isMobile = window.matchMedia('(max-width: 699px)').matches;
  let rate = 0; // BsD per 1 USD
  let currency = 'USD'; // 'USD' or 'BSD'
  let selectedItemIndex = -1;
  let methodChosen = false; // show prices only after choosing a payment method

  function updateMobileFooter() {
    if (!mfs) return;
    const show = isMobile && selectedItemIndex >= 0;
    if (!show) {
      mfs.classList.remove('show');
      mfs.setAttribute('hidden', '');
      return;
    }
    const it = (allItems && selectedItemIndex >= 0) ? allItems[selectedItemIndex] : null;
    if (it) {
      if (mfsTitle) mfsTitle.textContent = it.title || '';
      if (mfsPrice) {
        const val = currency === 'BSD' ? (Number(it.price || 0) * (rate || 0)) : Number(it.price || 0);
        mfsPrice.textContent = formatPrice(val);
      }
    }
    mfs.classList.add('show');
    mfs.removeAttribute('hidden');
  }

  function formatPrice(n){
    const v = Number(n || 0);
    if (currency === 'BSD') {
      // Show in BsD
      return v.toLocaleString('es-VE', { style:'currency', currency:'VES', minimumFractionDigits: 0, maximumFractionDigits: 0 });
    } else {
      // Show in USD
      return v.toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 });
    }
  }

  function renderItems(items) {
    if (!grid) return;
    grid.innerHTML = '';
    if (!items || items.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.innerHTML = '<p>No hay paquetes configurados para este juego.</p>';
      grid.appendChild(empty);
      return;
    }
    const list = isMobile ? (showingAll ? items : items.slice(0, 6)) : items;
    list.forEach((it, i) => {
      const b = document.createElement('button');
      b.className = 'item-pill';
      // Do NOT show price in the package selector; only title.
      b.innerHTML = `<span class="t">${it.title}</span>`;
      b.addEventListener('click', () => {
        selBox.hidden = false;
        selTitle.textContent = it.title;
        const val = currency === 'BSD' ? (Number(it.price || 0) * (rate || 0)) : Number(it.price || 0);
        selPrice.textContent = formatPrice(val);
        sumPrice.textContent = formatPrice(val);
        grid.querySelectorAll('.item-pill').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        selectedItemIndex = items.indexOf(it);
        persistState();
        updateMobileFooter();
      });
      // Autoselect first visible if none selected yet
      if (i === 0 && !grid.querySelector('.item-pill.active')) setTimeout(() => b.click(), 0);
      grid.appendChild(b);
    });
    if (btnMore) {
      if (!isMobile) {
        btnMore.hidden = true;
      } else {
        const needMore = items.length > 6;
        btnMore.hidden = !needMore || showingAll;
      }
    }
  }

  fetch(`/store/package/${gid}/items`).then(r => r.json()).then(data => {
    allItems = (data && data.items) || [];
    showingAll = false;
    renderItems(allItems);
  }).catch(() => {});

  // Fetch exchange rate (BsD per 1 USD)
  fetch('/store/rate').then(r => r.json()).then(data => {
    rate = Number((data && data.rate_bsd_per_usd) || 0);
    renderItems(allItems);
  }).catch(() => { rate = 0; renderItems(allItems); });
  // Fetch payments configuration (Admin-configured)
  fetch('/store/payments').then(r => r.json()).then(data => {
    if (data && data.ok) paymentsCfg = data.payments || null;
  }).catch(() => { paymentsCfg = null; });

  if (mfsClose) {
    mfsClose.addEventListener('click', () => {
      if (!mfs) return;
      mfs.classList.remove('show');
      mfs.setAttribute('hidden', '');
    });
  }

  function setCurrency(newCurrency) {
    currency = newCurrency;
    methodChosen = true;
    // toggle active state on buttons
    if (btnPayBSD && btnPayUSD) {
      if (currency === 'BSD') {
        btnPayBSD.classList.add('primary');
        btnPayUSD.classList.remove('primary');
      } else {
        btnPayUSD.classList.add('primary');
        btnPayBSD.classList.remove('primary');
      }
    }
    // Recompute and show prices only now that a method is chosen
    if (selectedItemIndex >= 0) {
      const it = allItems[selectedItemIndex];
      if (it) {
        const val = currency === 'BSD' ? (Number(it.price || 0) * (rate || 0)) : Number(it.price || 0);
        selPrice.textContent = formatPrice(val);
        sumPrice.textContent = formatPrice(val);
      }
    }
    renderItems(allItems);
    persistState();
    updateMobileFooter();
  }

  if (btnPayBSD) btnPayBSD.addEventListener('click', () => setCurrency('BSD'));
  if (btnPayUSD) btnPayUSD.addEventListener('click', () => setCurrency('USD'));

  // Do not pre-select a payment method to avoid showing prices prematurely

  // Re-render on resize to switch mobile/desktop behavior
  window.addEventListener('resize', () => {
    const nowMobile = window.matchMedia('(max-width: 699px)').matches;
    if (nowMobile !== isMobile) {
      isMobile = nowMobile;
      showingAll = false; // reset when switching
      renderItems(allItems);
    }
    updateMobileFooter();
  });

  // =====================
  // Local persistence + profile autofill
  // =====================
  const LS_KEY = 'inefablestore_checkout';

  function persistState() {
    if (!chkSave || !chkSave.checked) return; // only persist if user opted in
    const data = {
      customer_id: isGift ? '' : (inputCustomerId ? inputCustomerId.value.trim() : ''),
      name: inputName ? inputName.value.trim() : '',
      email: inputEmail ? inputEmail.value.trim() : '',
      phone: inputPhone ? inputPhone.value.trim() : '',
      currency,
      selectedIndex: selectedItemIndex,
      save: true
    };
    try { localStorage.setItem(LS_KEY, JSON.stringify(data)); } catch (_) {}
  }

  function clearState() {
    try { localStorage.removeItem(LS_KEY); } catch (_) {}
  }

  function loadLocal() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) { return null; }
  }

  function applyState(state) {
    if (!state || !state.save) return; // only apply if user opted in previously
    if (chkSave) chkSave.checked = true;
    if (!isGift && inputCustomerId && state.customer_id && !inputCustomerId.value) inputCustomerId.value = state.customer_id;
    if (inputName && state.name) inputName.value = state.name;
    if (inputEmail && state.email) inputEmail.value = state.email;
    if (inputPhone && state.phone) inputPhone.value = state.phone;
    if (typeof state.selectedIndex === 'number') selectedItemIndex = state.selectedIndex;
    if (state.currency === 'BSD' || state.currency === 'USD') setCurrency(state.currency);
  }

  async function loadProfileThenLocal() {
    // Try admin profile endpoint (logged-in admin).
    // If fails or not admin, fall back to localStorage only.
    let applied = false;
    try {
      const res = await fetch('/auth/profile');
      const data = await res.json();
      if (data && data.ok && data.profile) {
        if (inputName) inputName.value = data.profile.name || '';
        if (inputEmail) inputEmail.value = data.profile.email || '';
        if (inputPhone) inputPhone.value = data.profile.phone || '';
        applied = true;
      }
    } catch (_) {}
    if (!applied) {
      const st = loadLocal();
      applyState(st);
    }
  }

  // Wire inputs to persist
  [inputName, inputEmail, inputPhone].forEach(el => {
    if (!el) return;
    el.addEventListener('input', () => { if (chkSave && chkSave.checked) persistState(); });
  });
  if (chkSave) chkSave.addEventListener('change', () => { if (chkSave.checked) { persistState(); } else { clearState(); } });
  if (btnBuy) btnBuy.addEventListener('click', () => { if (chkSave && chkSave.checked) persistState(); });

  // Initial load of profile/local state after items/rate are ready
  loadProfileThenLocal();

  // =====================
  // Pay modal logic
  // =====================
  function currentSelectedItem() {
    if (!allItems || selectedItemIndex < 0 || selectedItemIndex >= allItems.length) return null;
    return allItems[selectedItemIndex];
  }

  function computeCurrentTotal() {
    const it = currentSelectedItem();
    if (!it) return 0;
    const baseUsd = Number(it.price || 0);
    let totalUsd = baseUsd;
    if (validRef && validRef.discount) {
      totalUsd = totalUsd * (1 - validRef.discount);
    }
    return currency === 'BSD' ? totalUsd * (rate || 0) : totalUsd;
  }

  function openPay() {
    if (!payModal) return;
    // Title
    const total = computeCurrentTotal();
    const label = currency === 'BSD' ? 'BsD' : 'USD';
    payTotalTitle.textContent = `Total a pagar: ${formatPrice(total)} ${label === 'USD' ? '' : ''}`;
    // Info
    if (payInfo) {
      payInfo.innerHTML = '';
      if (currency === 'BSD') {
        const rows = [
          ['Banco', (paymentsCfg && paymentsCfg.pm_bank) || ''],
          ['Nombre', (paymentsCfg && paymentsCfg.pm_name) || ''],
          ['Teléfono', (paymentsCfg && paymentsCfg.pm_phone) || ''],
          ['Cédula/RIF', (paymentsCfg && paymentsCfg.pm_id) || ''],
        ];
        rows.forEach(([k, v]) => {
          const div = document.createElement('div');
          div.innerHTML = `<div style="display:flex; justify-content:space-between; gap:10px; border-top:1px solid rgba(148,163,184,0.2); padding-top:10px;"><strong>${k}</strong><span>${v || '-'}</span></div>`;
          payInfo.appendChild(div);
        });
      } else {
        const rows = [
          ['Binance', 'Transferencia interna'],
          ['Email', (paymentsCfg && paymentsCfg.binance_email) || ''],
          ['Teléfono', (paymentsCfg && paymentsCfg.binance_phone) || ''],
        ];
        rows.forEach(([k, v]) => {
          const div = document.createElement('div');
          div.innerHTML = `<div style="display:flex; justify-content:space-between; gap:10px; border-top:1px solid rgba(148,163,184,0.2); padding-top:10px;"><strong>${k}</strong><span>${v || '-'}</span></div>`;
          payInfo.appendChild(div);
        });
      }
    }
    // Timer 30:00
    startTimer(30 * 60);
    payRef && (payRef.value = '');
    payModal.removeAttribute('hidden');
  }

  function closePay() {
    if (!payModal) return;
    payModal.setAttribute('hidden', '');
    if (countdownId) { clearInterval(countdownId); countdownId = null; }
  }

  function startTimer(seconds) {
    if (!payTimer) return;
    let remaining = seconds;
    if (countdownId) clearInterval(countdownId);
    const render = () => {
      const m = Math.floor(remaining / 60).toString().padStart(2, '0');
      const s = Math.floor(remaining % 60).toString().padStart(2, '0');
      payTimer.textContent = `${m}:${s}`;
    };
    render();
    countdownId = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      render();
      if (remaining <= 0) {
        clearInterval(countdownId);
      }
    }, 1000);
  }

  if (btnBuy) {
    btnBuy.addEventListener('click', () => {
      if (selectedItemIndex < 0) return alert('Selecciona un paquete');
      if (!isGift) {
        if (!inputCustomerId || !inputCustomerId.value.trim()) {
          alert('Ingrese su ID de jugador');
          if (inputCustomerId) inputCustomerId.focus();
          return;
        }
      }
      // Persist current selection if user opted
      if (chkSave && chkSave.checked) persistState();
      const gid = root.getAttribute('data-game-id');
      const method = (currency === 'BSD') ? 'pm' : 'binance';
      const paramsObj = {
        sel: String(selectedItemIndex),
        cur: currency,
        method,
        n: (inputName && inputName.value.trim()) || '',
        e: (inputEmail && inputEmail.value.trim()) || '',
        p: (inputPhone && inputPhone.value.trim()) || ''
      };
      if (!isGift && inputCustomerId) {
        paramsObj.cid = inputCustomerId.value.trim();
      }
      const rcode = inputRefCode ? inputRefCode.value.trim() : '';
      if (rcode) paramsObj.rc = rcode;
      const params = new URLSearchParams(paramsObj);
      window.location.href = `/checkout/${gid}?${params.toString()}`;
    });
  }

  async function validateRefCode() {
    if (!inputRefCode) return;
    const code = inputRefCode.value.trim();
    const gid = (() => { const r = document.getElementById('game-details'); return r ? r.getAttribute('data-game-id') : ''; })();
    validRef = null;
    if (!code) { if (refStatus) refStatus.textContent = ''; renderItems(allItems); return; }
    try {
      if (refStatus) { refStatus.style.color = '#94a3b8'; refStatus.textContent = 'Validando...'; }
      const res = await fetch(`/store/special/validate?code=${encodeURIComponent(code)}&gid=${encodeURIComponent(gid||'')}`);
      const data = await res.json();
      if (!res.ok || !data.ok || !data.allowed) throw new Error(data.error || 'Código inválido');
      validRef = { code, discount: Number(data.discount || 0) };
      if (refStatus) { refStatus.style.color = '#86efac'; refStatus.textContent = `Código válido: ${code} (${Math.round((validRef.discount||0)*100)}% OFF)`; }
      renderItems(allItems);
    } catch (e) {
      validRef = null;
      if (refStatus) refStatus.textContent = '';
    }
  }
  // Attach validators
  if (inputRefCode) {
    inputRefCode.addEventListener('blur', validateRefCode);
    inputRefCode.addEventListener('input', () => {
      if (!inputRefCode.value.trim()) {
        validRef = null;
        if (refStatus) refStatus.textContent = '';
        renderItems(allItems);
      }
    });
  }
});
