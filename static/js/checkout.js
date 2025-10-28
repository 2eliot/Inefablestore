// Standalone checkout page
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('checkout');
  if (!root) return;
  const gid = root.getAttribute('data-gid');
  const coTotal = document.getElementById('co-total');
  const coInfo = document.getElementById('co-info');
  const coTimer = document.getElementById('co-timer');
  const coRef = document.getElementById('co-ref');
  const btnConfirm = document.getElementById('btn-co-confirm');
  const coDiscNote = document.getElementById('co-disc-note');

  let allItems = [];
  let rate = 0;
  let paymentsCfg = null;
  let countdownId = null;

  // Restore selection and currency from URL first, then localStorage
  const qs = new URLSearchParams(window.location.search);
  const qSel = qs.get('sel');
  const qCur = qs.get('cur');
  const qMethod = qs.get('method'); // 'pm' | 'binance'
  const qCid = qs.get('cid');
  const qZid = qs.get('zid');
  const qRefCode = (qs.get('rc') || '').trim();
  const qName = qs.get('n') || '';
  const qEmail = qs.get('e') || '';
  const qPhone = qs.get('p') || '';
  const qQtyRaw = qs.get('q');
  let quantity = 1;
  try {
    const qn = parseInt(qQtyRaw, 10);
    if (!isNaN(qn) && qn > 0) quantity = Math.min(99, qn);
  } catch(_) { quantity = 1; }
  const LS_KEY = 'inefablestore_checkout';
  let state = null;
  try { state = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (_) { state = null; }
  // If method is explicitly provided, it wins
  let currency = (qMethod === 'pm') ? 'BSD' : (qMethod === 'binance') ? 'USD' : ((qCur === 'BSD' || qCur === 'USD') ? qCur : ((state && state.currency === 'BSD') ? 'BSD' : 'USD'));
  let selectedIndex = (qSel !== null && !isNaN(parseInt(qSel, 10))) ? parseInt(qSel, 10) : ((state && typeof state.selectedIndex === 'number') ? state.selectedIndex : -1);

  function formatPriceFor(cur, n){
    const v = Number(n || 0);
    if (cur === 'BSD') {
      return v.toLocaleString('es-VE', { style:'currency', currency:'VES', minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }
    return v.toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 });
  }
  function formatPrice(n){
    // Backwards-compatible helper using current currency
    return formatPriceFor(currency, n);
  }
  // Global delegated copy handler with fallback
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.copy-btn');
    if (!btn) return;
    const text = btn.getAttribute('data-copy') || '';
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = 'Copiado';
      setTimeout(() => { btn.textContent = 'Copiar'; }, 1200);
    } catch (_) {
      // Fallback for environments without Clipboard API permissions
      try {
        const tmp = document.createElement('input');
        tmp.value = text;
        document.body.appendChild(tmp);
        tmp.select();
        document.execCommand('copy');
        document.body.removeChild(tmp);
        btn.textContent = 'Copiado';
        setTimeout(() => { btn.textContent = 'Copiar'; }, 1200);
      } catch (err) {
        alert('No se pudo copiar');
      }
    }
  });



  function computeTotals() {
    // Returns { amount, displayCurrency, usedCurrency, baseBeforeDiscount }
    if (!allItems || selectedIndex < 0 || selectedIndex >= allItems.length) return { amount: 0, displayCurrency: currency, usedCurrency: currency, baseBeforeDiscount: 0 };
    const unitUsd = Number(allItems[selectedIndex].price || 0);
    const qty = Math.max(1, quantity || 1);
    const baseUsd = unitUsd * qty;
    // Apply influencer discount ONLY to 1 unit, not to all quantity
    let totalUsd = baseUsd;
    if (window.__validRef && window.__validRef.discount) {
      const d = Number(window.__validRef.discount || 0);
      totalUsd = (unitUsd * qty) - (unitUsd * d);
    }
    if (currency === 'BSD') {
      if (rate && rate > 0) {
        return { amount: totalUsd * rate, displayCurrency: 'BSD', usedCurrency: 'BSD', baseBeforeDiscount: baseUsd * rate };
      }
      // Fallback to USD if rate is not available to avoid showing 0
      return { amount: totalUsd, displayCurrency: 'USD', usedCurrency: 'USD', baseBeforeDiscount: baseUsd };
    }
    return { amount: totalUsd, displayCurrency: 'USD', usedCurrency: 'USD', baseBeforeDiscount: baseUsd };
  }

  function renderHeader() {
    const t = computeTotals();
    // If discount active, show new price then old price struck-through
    if (allItems && selectedIndex >= 0 && selectedIndex < allItems.length && window.__validRef && window.__validRef.discount) {
      if (t.baseBeforeDiscount > t.amount) {
        coTotal.innerHTML = `Total a pagar: <span class="price-new">${formatPriceFor(t.displayCurrency, t.amount)}</span> <span class="price-old">${formatPriceFor(t.displayCurrency, t.baseBeforeDiscount)}</span>`;
        const pct = Math.round(Number(window.__validRef.discount || 0) * 100);
        if (coDiscNote) { coDiscNote.textContent = `${pct}% de descuento activo`; coDiscNote.removeAttribute('hidden'); }
        return;
      }
    }
    coTotal.textContent = `Total a pagar: ${formatPriceFor(t.displayCurrency, t.amount)}`;
    if (coDiscNote) coDiscNote.setAttribute('hidden', '');
  }

  function renderInfo() {
    if (!coInfo) return;
    coInfo.innerHTML = '';
    const svg = (name) => {
      if (name === 'bank') return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M3 10h18v2H3v-2zm2 3h2v5H5v-5zm4 0h2v5H9v-5zm4 0h2v5h-2v-5zm4 0h2v5h-2v-5zM3 21h18v2H3v-2zM12 2l9 6H3l9-6z"/></svg>';
      if (name === 'email') return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 13L2 6.76V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6.76L12 13zm0-2.4L22 4H2l10 6.6z"/></svg>';
      if (name === 'user') return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5zm0 2c-4.33 0-8 2.17-8 5v1h16v-1c0-2.83-3.67-5-8-5z"/></svg>';
      if (name === 'id') return '<svg viewBox=\"0 0 24 24\" width=\"20\" height=\"20\" fill=\"currentColor\" aria-hidden=\"true\"><path d=\"M3 4h18v16H3z\" opacity=\".3\"/><path d=\"M21 2H3a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1zM4 6h16v12H4zm3 2h6v2H7zm0 4h10v2H7z\"/></svg>';
      return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="10"/></svg>';
    };
    const addItem = (iconName, value) => {
      const row = document.createElement('div');
      row.className = 'co-item';
      const ico = document.createElement('div');
      ico.className = 'co-ico';
      ico.innerHTML = svg(iconName);
      const val = document.createElement('div');
      val.className = 'co-val';
      val.textContent = value || '-';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'copy-btn';
      btn.setAttribute('data-copy', value || '');
      btn.textContent = 'Copiar';
      row.appendChild(ico);
      row.appendChild(val);
      row.appendChild(btn);
      coInfo.appendChild(row);
    };
    // Optional player info lines (kept at top if present)
    // Player ID (qCid) intentionally hidden from checkout UI, but still used internally
    if (qZid) addItem('id', qZid);
    if (currency === 'BSD') {
      // Show PM bank/name/phone/id
      addItem('bank', (paymentsCfg && paymentsCfg.pm_bank) || '');
      addItem('user', (paymentsCfg && paymentsCfg.pm_name) || '');
      addItem('user', (paymentsCfg && paymentsCfg.pm_phone) || '');
      addItem('id', (paymentsCfg && paymentsCfg.pm_id) || '');
    } else {
      // Binance: show provider name, email and Pay ID
      addItem('bank', 'Binance');
      addItem('email', (paymentsCfg && paymentsCfg.binance_email) || '');
      addItem('user', (paymentsCfg && paymentsCfg.binance_phone) || '');
    }
  }

  function startTimer(seconds) {
    if (!coTimer) return;
    let remaining = seconds;
    const render = () => {
      const m = Math.floor(remaining / 60).toString().padStart(2, '0');
      const s = Math.floor(remaining % 60).toString().padStart(2, '0');
      coTimer.textContent = `${m}:${s}`;
    };
    render();
    if (countdownId) clearInterval(countdownId);
    countdownId = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      render();
      if (remaining <= 0) clearInterval(countdownId);
    }, 1000);
  }

  // Fetch data
  Promise.all([
    fetch(`/store/package/${gid}/items`).then(r => r.json()).catch(() => null),
    fetch('/store/rate').then(r => r.json()).catch(() => null),
    fetch('/store/payments').then(r => r.json()).catch(() => null)
  ]).then(([itemsRes, rateRes, payRes]) => {
    allItems = (itemsRes && itemsRes.items) || [];
    if (selectedIndex < 0 && allItems.length > 0) selectedIndex = 0;
    rate = Number((rateRes && rateRes.rate_bsd_per_usd) || 0);
    paymentsCfg = (payRes && payRes.ok && payRes.payments) ? payRes.payments : null;
    renderHeader();
    renderInfo();
    startTimer(30*60);
  });

  // Validate referral code from query if present
  (async function validateRefAtStart(){
    if (!qRefCode) return;
    try {
      const res = await fetch(`/store/special/validate?code=${encodeURIComponent(qRefCode)}&gid=${encodeURIComponent(gid||'')}`);
      const data = await res.json();
      if (res.ok && data && data.ok && data.allowed) {
        window.__validRef = { code: qRefCode, discount: Number(data.discount || 0) };
        renderHeader();
      }
    } catch (_) { /* ignore */ }
  })();

  if (btnConfirm) {
    btnConfirm.addEventListener('click', async () => {
      const ref = coRef ? coRef.value.trim() : '';
      if (!ref) { alert('Ingrese la referencia'); return; }
      // Prepare order payload
      const item = (allItems && selectedIndex >= 0 && selectedIndex < allItems.length) ? allItems[selectedIndex] : null;
      const totals = computeTotals();
      const amount = totals.amount;
      const method = (totals.usedCurrency === 'BSD') ? 'pm' : 'binance';
      // Buyer info: prefer URL params from details, fallback to localStorage
      let state = null;
      try { state = JSON.parse(localStorage.getItem('inefablestore_checkout') || 'null'); } catch (_) { state = null; }
      const name = qName || (state && state.name) || '';
      const email = qEmail || (state && state.email) || '';
      const phone = qPhone || (state && state.phone) || '';
      if (!phone) { alert('Ingresa tu número de teléfono'); return; }
      const customer_id = qs.get('cid') || '';
      const customer_zone = qs.get('zid') || '';
      const payload = {
        store_package_id: gid,
        item_id: item ? item.id : null,
        // Multi-package support: send items with quantity of selected package
        items: (item ? [{ item_id: item.id, qty: Math.max(1, quantity || 1) }] : []),
        amount,
        currency: totals.usedCurrency,
        method,
        reference: ref,
        name,
        email,
        phone,
        customer_id,
        customer_zone,
        special_code: qRefCode || ''
      };
      // UI loading state
      const originalText = btnConfirm.textContent;
      btnConfirm.textContent = 'Procesando...';
      btnConfirm.disabled = true;
      // Abort fetch if it takes too long
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 15000);
      try {
        const res = await fetch('/orders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: controller.signal
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) throw new Error((data && data.error) || 'No se pudo crear la orden');
        const wrap = document.getElementById('checkout');
        if (wrap) {
          wrap.innerHTML = `
            <div style="max-width:720px;margin:40px auto;text-align:center;color:#e5e7eb;">
              <div style="background:#10b981;color:#062a1d;font-weight:900;padding:14px;border-radius:12px;">¡Gracias por tu compra!</div>
              <p style="margin-top:12px;">Tu orden #${data.order_id} ha sido registrada y será procesada por nuestro equipo.</p>
              <p>Te redirigiremos al inicio en unos segundos...</p>
            </div>`;
        }
        setTimeout(() => { window.location.href = '/'; }, 3000);
      } catch (err) {
        const msg = (err && err.name === 'AbortError') ? 'La solicitud tardó demasiado. Intenta de nuevo.' : (err.message || 'No se pudo crear la orden');
        alert(msg);
      } finally {
        clearTimeout(tid);
        btnConfirm.textContent = originalText;
        btnConfirm.disabled = false;
      }
    });
  }
});
