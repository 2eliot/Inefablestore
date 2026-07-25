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
  const IS_MINI = !!(root && root.dataset && root.dataset.isMini === '1');
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
      myOrders.innerHTML = '<div class="muted">Sin órdenes registradas</div>';
      return;
    }
    const orderStatusMeta = (rawStatus) => {
      const status = String(rawStatus || 'pending').toLowerCase();
      if (status === 'delivered') {
        return { label: 'Entregada', color: '#10b981', border: 'rgba(16,185,129,0.25)' };
      }
      if (status === 'approved') {
        return { label: 'Procesando', color: '#f59e0b', border: 'rgba(245,158,11,0.25)' };
      }
      if (status === 'rejected') {
        return { label: 'Rechazada', color: '#ef4444', border: 'rgba(239,68,68,0.25)' };
      }
      return { label: 'Pendiente', color: '#f59e0b', border: 'rgba(245,158,11,0.25)' };
    };
    items.forEach(o => {
      const row = document.createElement('div');
      const statusMeta = orderStatusMeta(o.status);
      row.className = 'order-mini';
      row.style.border = `1px solid ${statusMeta.border}`;
      row.style.borderRadius = '10px';
      row.style.padding = '8px 10px';
      row.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;font-weight:800;">
          <span>${o.package_name} • ${o.item_title}</span>
          <span style="display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid ${statusMeta.color};color:${statusMeta.color};font-weight:800;font-size:11px;">${statusMeta.label}</span>
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
        const affBonusEl = document.getElementById('aff-bonus');
        if (affBonusEl) affBonusEl.textContent = `$${Number(data.bonus_usd || 0).toFixed(2)}`;
        const affPill = document.getElementById('aff-comm-pill');
        if (affPill) affPill.textContent = `${Number(data.commission_percent || 0)}% comisión`;
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

  // =====================
  // Mini influencer panel
  // =====================
  const miniBanner = document.getElementById('mini-status-banner');
  const miniCodePill = document.getElementById('mini-code-pill');
  const miniUses = document.getElementById('mini-uses');
  const miniCommission = document.getElementById('mini-commission');
  const miniBonus = document.getElementById('mini-bonus');
  const miniTotal = document.getElementById('mini-total');
  const miniDiscount = document.getElementById('mini-discount');
  const miniCommPct = document.getElementById('mini-comm-pct');
  const miniVideosCount = document.getElementById('mini-videos-count');
  const miniViewsCount = document.getElementById('mini-views-count');
  const miniVideoUrl = document.getElementById('mini-video-url');
  const miniVideoViews = document.getElementById('mini-video-views');
  const btnMiniVideoAdd = document.getElementById('btn-mini-video-add');
  const miniVideoAlert = document.getElementById('mini-video-alert');
  const miniVideoList = document.getElementById('mini-video-list');

  const money = (n) => `$${Number(n || 0).toFixed(2)}`;
  const num = (n) => Number(n || 0).toLocaleString('es-VE');

  function miniAlert(msg, kind) {
    if (!miniVideoAlert) return;
    miniVideoAlert.textContent = msg || '';
    miniVideoAlert.style.color = kind === 'error' ? '#fecaca' : (kind === 'ok' ? '#86efac' : '#94a3b8');
  }

  function setMiniStatus(status) {
    if (!miniBanner) return;
    const st = String(status || 'approved');
    if (st === 'pending') {
      miniBanner.className = 'mini-banner mini-banner--pending';
      miniBanner.innerHTML = 'Tu perfil está <strong>en revisión</strong>. Tu código se activa cuando lo aprobemos, '
        + 'y ahí podrás empezar a cargar tus videos.';
      miniBanner.removeAttribute('hidden');
    } else if (st === 'rejected') {
      miniBanner.className = 'mini-banner mini-banner--rejected';
      miniBanner.innerHTML = 'Tu perfil <strong>no fue aprobado</strong>. Si crees que es un error, escríbenos.';
      miniBanner.removeAttribute('hidden');
    } else {
      miniBanner.className = 'mini-banner mini-banner--approved';
      miniBanner.innerHTML = 'Tu perfil está <strong>activo</strong>. Comparte tu código y sube tus videos para ganar bonos.';
      miniBanner.removeAttribute('hidden');
    }
    // Uploading videos and withdrawing only make sense once approved
    const approved = (st === 'approved');
    if (miniVideoUrl) miniVideoUrl.disabled = !approved;
    if (miniVideoViews) miniVideoViews.disabled = !approved;
    if (btnMiniVideoAdd) btnMiniVideoAdd.disabled = !approved;
    if (!approved) {
      if (btnAffWithdraw) btnAffWithdraw.style.display = 'none';
      if (withdrawPanel) withdrawPanel.style.display = 'none';
    }
  }

  const miniRankCurrent = document.getElementById('mini-rank-current');
  const miniRankFill = document.getElementById('mini-rank-fill');
  const miniRankHint = document.getElementById('mini-rank-hint');
  const miniRankGrid = document.getElementById('mini-rank-grid');
  const miniTierTable = document.getElementById('mini-tier-table');
  const miniTierComm = document.getElementById('mini-tier-comm');

  function renderRanks(data) {
    if (!miniRankGrid) return;
    const ranks = data.ranks || [];
    const uses = Number(data.code_uses || 0);
    const currentName = data.rank_current ? data.rank_current.name : '';
    if (miniRankCurrent) miniRankCurrent.textContent = currentName ? `Rango ${currentName}` : 'Sin rango aún';
    if (miniRankFill) miniRankFill.style.width = `${Number(data.rank_progress || 0)}%`;
    if (miniRankHint) {
      if (data.rank_next) {
        const left = Number(data.rank_uses_to_next || 0);
        miniRankHint.innerHTML = `Te faltan <strong>${num(left)}</strong> usos para <strong>${escapeHtml(data.rank_next.name)}</strong> `
          + `(${money(data.rank_next.bonus)} de bono)`;
      } else if (ranks.length) {
        miniRankHint.innerHTML = 'Alcanzaste el rango más alto.';
      } else {
        miniRankHint.textContent = '';
      }
    }
    miniRankGrid.innerHTML = '';
    if (!ranks.length) {
      miniRankGrid.innerHTML = '<div class="muted">Todavía no hay rangos configurados.</div>';
      return;
    }
    ranks.forEach(r => {
      const unlocked = uses >= Number(r.uses || 0);
      const isCurrent = (r.name === currentName);
      const card = document.createElement('div');
      card.className = 'mini-rank-card'
        + (unlocked ? ' mini-rank-card--unlocked' : '')
        + (isCurrent ? ' mini-rank-card--current' : '');
      card.innerHTML = `
        <div class="mini-rank-name">${escapeHtml(r.name)}</div>
        <div class="mini-rank-uses">${num(r.uses)} usos</div>
        <div class="mini-rank-bonus">${money(r.bonus)}</div>
        <div class="mini-rank-tag">${isCurrent ? 'Tu rango' : (unlocked ? 'Desbloqueado' : 'Bloqueado')}</div>
      `;
      miniRankGrid.appendChild(card);
    });
  }

  function renderTierTable(tiers) {
    if (!miniTierTable) return;
    const rows = tiers || [];
    miniTierTable.innerHTML = '<div class="mini-tier-row mini-tier-row--head"><span>Vistas</span><span>Recompensa</span></div>';
    if (!rows.length) {
      miniTierTable.insertAdjacentHTML('beforeend', '<div class="mini-tier-row"><span class="muted">Sin tramos configurados</span><span></span></div>');
      return;
    }
    rows.forEach((t, i) => {
      const label = (t.max === null || t.max === undefined)
        ? `${num(t.min)} o más`
        : `${num(t.min)} - ${num(t.max)}`;
      miniTierTable.insertAdjacentHTML('beforeend',
        `<div class="mini-tier-row${i % 2 ? ' mini-tier-row--alt' : ''}"><span>${label}</span><span class="mini-tier-reward">${money(t.reward)}</span></div>`);
    });
  }

  async function loadMiniSummary() {
    if (!IS_MINI) return;
    try {
      const res = await fetch('/mini/summary');
      const data = await res.json();
      if (!res.ok || !data.ok) return;
      setMiniStatus(data.status);
      renderRanks(data);
      renderTierTable(data.view_tiers);
      if (miniTierComm) miniTierComm.textContent = `${Number(data.commission_percent || 0)}%`;
      if (miniCodePill) miniCodePill.textContent = data.code || '-';
      if (miniUses) miniUses.textContent = num(data.code_uses);
      if (miniCommission) miniCommission.textContent = money(data.commission_usd);
      if (miniBonus) miniBonus.textContent = money(data.bonus_usd);
      if (miniTotal) miniTotal.textContent = money(data.balance_usd);
      if (miniDiscount) miniDiscount.textContent = `${Number(data.discount_percent || 0)}%`;
      if (miniCommPct) miniCommPct.textContent = `${Number(data.commission_percent || 0)}%`;
      if (miniVideosCount) {
        const total = Number(data.videos_total || 0);
        miniVideosCount.textContent = `${total} ${total === 1 ? 'video' : 'videos'}`;
      }
      if (miniViewsCount) miniViewsCount.textContent = `${num(data.views_total)} vistas aprobadas`;
    } catch (_) {}
  }

  function renderMiniVideos(items) {
    if (!miniVideoList) return;
    miniVideoList.innerHTML = '';
    if (!items || items.length === 0) {
      miniVideoList.innerHTML = '<div class="muted">Todavía no cargaste videos.</div>';
      return;
    }
    const meta = (s) => {
      if (s === 'approved') return { label: 'Aprobado', color: '#34d399' };
      if (s === 'rejected') return { label: 'Rechazado', color: '#f87171' };
      return { label: 'En revisión', color: '#fbbf24' };
    };
    items.forEach(v => {
      const st = meta(v.status);
      const row = document.createElement('div');
      row.className = 'mini-video-item';
      let reward = '';
      if (Number(v.reward_usd || 0) > 0) {
        reward = `<span>Bono: <strong style="color:#34d399;">${money(v.reward_usd)}</strong></span>`;
      } else if ((v.status || 'pending') === 'pending' && Number(v.tier_reward_usd || 0) > 0) {
        // Reference from the tier table, still to be confirmed on review
        reward = `<span>Estimado por tramo: <strong>${money(v.tier_reward_usd)}</strong></span>`;
      }
      const note = v.note ? `<span>${escapeHtml(v.note)}</span>` : '';
      const canDelete = (v.status || 'pending') === 'pending';
      row.innerHTML = `
        <div class="mini-video-top">
          <a class="mini-video-link" href="${encodeURI(v.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(v.url)}</a>
          <span class="mini-badge" style="color:${st.color};">${st.label}</span>
        </div>
        <div class="mini-video-meta">
          <span>${escapeHtml((v.platform || 'otro').toUpperCase())}</span>
          <span>${num(v.views_declared)} vistas</span>
          ${reward}
          ${note}
          ${canDelete ? `<button class="mini-video-del" type="button" data-id="${v.id}">Quitar</button>` : ''}
        </div>
      `;
      miniVideoList.appendChild(row);
    });
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  async function fetchMiniVideos() {
    if (!IS_MINI || !miniVideoList) return;
    try {
      const res = await fetch('/mini/videos');
      const data = await res.json();
      renderMiniVideos((data && data.items) || []);
    } catch (_) {
      renderMiniVideos([]);
    }
  }

  async function addMiniVideo() {
    if (!IS_MINI) return;
    const url = miniVideoUrl ? miniVideoUrl.value.trim() : '';
    const views = miniVideoViews ? miniVideoViews.value : '';
    if (!url) { miniAlert('Pega el link de tu video', 'error'); return; }
    try {
      if (btnMiniVideoAdd) btnMiniVideoAdd.disabled = true;
      miniAlert('Enviando...');
      const res = await fetch('/mini/videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, views })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo agregar');
      if (miniVideoUrl) miniVideoUrl.value = '';
      if (miniVideoViews) miniVideoViews.value = '';
      miniAlert('Video enviado a revisión', 'ok');
      await fetchMiniVideos();
      await loadMiniSummary();
    } catch (e) {
      miniAlert(e.message || 'Error', 'error');
    } finally {
      if (btnMiniVideoAdd) btnMiniVideoAdd.disabled = false;
    }
  }

  if (btnMiniVideoAdd) btnMiniVideoAdd.addEventListener('click', addMiniVideo);
  if (miniVideoUrl) {
    miniVideoUrl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); addMiniVideo(); }
    });
  }
  if (miniVideoList) {
    miniVideoList.addEventListener('click', async (e) => {
      const btn = e.target.closest('.mini-video-del');
      if (!btn) return;
      const id = btn.getAttribute('data-id');
      try {
        btn.disabled = true;
        const res = await fetch(`/mini/videos/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || 'No se pudo quitar');
        await fetchMiniVideos();
        await loadMiniSummary();
      } catch (err) {
        miniAlert(err.message || 'Error', 'error');
        btn.disabled = false;
      }
    });
  }

  loadMiniSummary();
  fetchMiniVideos();
});
