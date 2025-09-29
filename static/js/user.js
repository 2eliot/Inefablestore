document.addEventListener('DOMContentLoaded', () => {
  const nameInput = document.getElementById('profile-name');
  const emailInput = document.getElementById('profile-email');
  const phoneInput = document.getElementById('profile-phone');
  const btnSave = document.getElementById('btn-save-profile');
  const btnLogout = document.getElementById('btn-logout');
  const whoName = document.getElementById('who-name');
  const whoEmail = document.getElementById('who-email');
  const avatar = document.getElementById('avatar-initials');
  const alertBox = document.getElementById('profile-alert');
  const qEmail = document.getElementById('q-email');
  const qCustomer = document.getElementById('q-customer');
  const btnMyOrders = document.getElementById('btn-myorders');
  const myOrders = document.getElementById('my-orders');
  const root = document.querySelector('.user-page');
  const IS_ADMIN = !!(root && root.dataset && root.dataset.isAdmin === '1');
  const IS_AFFILIATE = !!(root && root.dataset && root.dataset.isAffiliate === '1');
  const affCodeEl = document.getElementById('aff-code');
  const affApprovedEl = document.getElementById('aff-approved');
  const affBalanceEl = document.getElementById('aff-balance');
  const btnAffWithdraw = document.getElementById('btn-aff-withdraw');
  const withdrawPanel = document.getElementById('aff-withdraw-panel');
  const awMethod = document.getElementById('aw-method');
  const awPM = document.getElementById('aw-pm');
  const awBIN = document.getElementById('aw-bin');
  const awZIN = document.getElementById('aw-zin');
  const awBank = document.getElementById('aw-pm-bank');
  const awName = document.getElementById('aw-pm-name');
  const awPhone = document.getElementById('aw-pm-phone');
  const awId = document.getElementById('aw-pm-id');
  const awBEmail = document.getElementById('aw-bin-email');
  const awBPhone = document.getElementById('aw-bin-phone');
  const awZEmail = document.getElementById('aw-zin-email');
  const awZTag = document.getElementById('aw-zin-tag');
  const awAmount = document.getElementById('aw-amount');
  const btnAwSend = document.getElementById('btn-aw-send');
  const awAlert = document.getElementById('aw-alert');
  const awList = document.getElementById('aw-list');

  function showAlert(type, msg) {
    if (!alertBox) return;
    alertBox.textContent = msg || '';
    alertBox.className = 'alert ' + (type || '');
    alertBox.removeAttribute('hidden');
  }
  function clearAlert() {
    if (!alertBox) return;
    alertBox.setAttribute('hidden', '');
    alertBox.textContent = '';
  }
  function setHero(name, email) {
    if (whoName) whoName.textContent = name || 'Usuario';
    if (whoEmail) whoEmail.textContent = email || 'correo@example.com';
    if (avatar) {
      const initials = (name || email || 'U').trim().charAt(0).toUpperCase();
      avatar.textContent = initials || 'U';
    }
  }

  async function loadProfile() {
    try {
      const res = await fetch('/auth/profile');
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert('error', data.error || 'No se pudo cargar el perfil');
        return;
      }
      const { name, email, phone } = data.profile || {};
      if (nameInput) nameInput.value = name || '';
      if (emailInput) emailInput.value = email || '';
      if (phoneInput) phoneInput.value = phone || '';
      setHero(name, email);
      clearAlert();
    } catch (e) {
      showAlert('error', 'No se pudo cargar el perfil');
    }
  }

  async function saveProfile() {
    const name = nameInput ? nameInput.value.trim() : '';
    const email = emailInput ? emailInput.value.trim() : '';
    const phone = phoneInput ? phoneInput.value.trim() : '';
    try {
      const res = await fetch('/auth/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, phone })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showAlert('error', data.error || 'No se pudo guardar');
        return;
      }
      setHero(name, email);
      showAlert('success', 'Perfil guardado');
    } catch (e) {
      showAlert('error', 'No se pudo guardar');
    }
  }

  async function logout() {
    try {
      await fetch('/auth/logout', { method: 'POST' });
    } finally {
      window.location.href = '/';
    }
  }

  if (btnSave) btnSave.addEventListener('click', saveProfile);
  if (btnLogout) btnLogout.addEventListener('click', logout);

  async function fetchMyOrders() {
    let url = '/orders/my';
    if (IS_ADMIN) {
      const email = qEmail ? qEmail.value.trim() : '';
      const cid = qCustomer ? qCustomer.value.trim() : '';
      const params = new URLSearchParams();
      if (email) params.set('email', email);
      if (cid) params.set('customer_id', cid);
      url = `/orders/my?${params.toString()}`;
    }
    try {
      const res = await fetch(url);
      const data = await res.json();
      renderMyOrders((data && data.orders) || []);
    } catch (_) {
      renderMyOrders([]);
    }
  }

  function renderMyOrders(items) {
    if (!myOrders) return;
    myOrders.innerHTML = '';
    if (!items || items.length === 0) {
      myOrders.innerHTML = '<div class="muted">Sin órdenes aprobadas</div>';
      return;
    }
    items.forEach(o => {
      const row = document.createElement('div');
      row.className = 'order-mini';
      row.style.border = '1px solid rgba(16,185,129,0.25)';
      row.style.borderRadius = '10px';
      row.style.padding = '8px 10px';
      const badge = (s) => {
        const color = s === 'approved' ? '#10b981' : (s === 'rejected' ? '#ef4444' : '#f59e0b');
        return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid ${color};color:${color};font-weight:800;font-size:11px;">${s}</span>`;
      };
      row.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;font-weight:800;">
          <span>${o.package_name} • ${o.item_title}</span>
          ${badge(o.status || 'approved')}
        </div>
        <div style="font-size:12px; color:#93c5b1;">Ref: ${o.reference} • ${new Date(o.created_at).toLocaleString()}</div>
        <div style="font-size:12px; color:#93c5b1;">Precio: $${Number(o.item_price_usd||0).toFixed(2)} (${o.method})</div>
      `;
      myOrders.appendChild(row);
    });
  }

  if (btnMyOrders) btnMyOrders.addEventListener('click', fetchMyOrders);

  // Hide filters for non-admin users
  if (!IS_ADMIN) {
    if (qEmail) qEmail.parentElement.style.display = 'none';
    if (qCustomer) qCustomer.parentElement.style.display = 'none';
  }

  // Try to prefill from localStorage and auto-fetch orders
  try {
    const st = JSON.parse(localStorage.getItem('inefablestore_checkout') || 'null');
    if (st) {
      if (qEmail && st.email) qEmail.value = st.email;
      if (qCustomer && st.customer_id) qCustomer.value = st.customer_id;
    }
  } catch (_) {}

  // Auto-fetch on load if any query present
  // Auto-fetch on load: for users always; for admin only if provided filters
  if (!IS_ADMIN || (qEmail && qEmail.value.trim()) || (qCustomer && qCustomer.value.trim())) {
    fetchMyOrders();
  }

  // Affiliate summary
  async function loadAffiliateSummary() {
    if (!IS_AFFILIATE) return;
    try {
      const res = await fetch('/affiliate/summary');
      const data = await res.json();
      if (res.ok && data && data.ok) {
        if (affCodeEl) affCodeEl.textContent = data.code || '-';
        if (affApprovedEl) affApprovedEl.textContent = String(data.approved_orders || 0);
        if (affBalanceEl) affBalanceEl.textContent = `$${Number(data.balance_usd || 0).toFixed(2)}`;
      }
    } catch (_) {}
  }

  loadProfile();
  loadAffiliateSummary();

  // Withdrawals UI behavior
  function toggleWithdrawPanel() {
    if (!withdrawPanel) return;
    const visible = withdrawPanel.style.display !== 'none';
    withdrawPanel.style.display = visible ? 'none' : 'block';
  }
  if (btnAffWithdraw) btnAffWithdraw.addEventListener('click', toggleWithdrawPanel);
  if (awMethod) {
    awMethod.addEventListener('change', () => {
      const m = awMethod.value;
      if (m === 'pm') {
        if (awPM) awPM.style.display = 'grid';
        if (awBIN) awBIN.style.display = 'none';
        if (awZIN) awZIN.style.display = 'none';
      } else if (m === 'binance') {
        if (awPM) awPM.style.display = 'none';
        if (awBIN) awBIN.style.display = 'grid';
        if (awZIN) awZIN.style.display = 'none';
      } else {
        if (awPM) awPM.style.display = 'none';
        if (awBIN) awBIN.style.display = 'none';
        if (awZIN) awZIN.style.display = 'grid';
      }
    });
  }

  async function fetchWithdrawals() {
    if (!IS_AFFILIATE || !awList) return;
    try {
      const res = await fetch('/affiliate/withdrawals');
      const data = await res.json();
      renderWithdrawals((data && data.items) || []);
    } catch (_) {
      renderWithdrawals([]);
    }
  }

  function renderWithdrawals(items) {
    if (!awList) return;
    awList.innerHTML = '';
    if (!items || items.length === 0) {
      awList.innerHTML = '<div class="muted">Sin solicitudes de retiro</div>';
      return;
    }
    const fmtUSD = (n) => {
      try { return Number(n||0).toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 }); } catch(_) { return `$${n}`; }
    };
    items.forEach(r => {
      const row = document.createElement('div');
      row.className = 'order-mini';
      row.style.border = '1px solid rgba(16,185,129,0.25)';
      row.style.borderRadius = '10px';
      row.style.padding = '8px 10px';
      const statusColor = r.status === 'approved' ? '#10b981' : (r.status === 'rejected' ? '#ef4444' : '#f59e0b');
      row.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;font-weight:800;">
          <span>Retiro ${fmtUSD(r.amount_usd)} • ${r.method.toUpperCase()}</span>
          <span style="display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid ${statusColor};color:${statusColor};font-weight:800;font-size:11px;">${r.status}</span>
        </div>
        <div style="font-size:12px; color:#93c5b1;">${new Date(r.created_at).toLocaleString()}</div>
      `;
      awList.appendChild(row);
    });
  }

  async function sendWithdrawal() {
    if (!IS_AFFILIATE) return;
    const method = awMethod ? awMethod.value : 'pm';
    const payload = { method, amount_usd: awAmount ? awAmount.value : '' };
    if (method === 'pm') {
      payload.pm_bank = awBank ? awBank.value : '';
      payload.pm_name = awName ? awName.value : '';
      payload.pm_phone = awPhone ? awPhone.value : '';
      payload.pm_id = awId ? awId.value : '';
    } else {
      if (method === 'binance') {
        payload.binance_email = awBEmail ? awBEmail.value : '';
        payload.binance_phone = awBPhone ? awBPhone.value : '';
      } else {
        payload.zinli_email = awZEmail ? awZEmail.value : '';
        payload.zinli_tag = awZTag ? awZTag.value : '';
      }
    }
    try {
      if (awAlert) { awAlert.style.color = '#94a3b8'; awAlert.textContent = 'Enviando...'; }
      const res = await fetch('/affiliate/withdrawals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo enviar');
      if (awAlert) { awAlert.style.color = '#86efac'; awAlert.textContent = 'Solicitud enviada'; }
      await loadAffiliateSummary();
      await fetchWithdrawals();
    } catch (e) {
      if (awAlert) { awAlert.style.color = '#fecaca'; awAlert.textContent = e.message || 'Error'; }
    }
  }
  if (btnAwSend) btnAwSend.addEventListener('click', sendWithdrawal);

  fetchWithdrawals();
});
